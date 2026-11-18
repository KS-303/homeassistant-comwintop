"""L-50: deadlines, read blocks, quality and HA migration."""

import asyncio
import logging
import time
from types import MappingProxyType
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ServerDeviceBusyError,
)

from custom_components.comwintop.config_flow import integral_seconds
from custom_components.comwintop.const import DOMAIN
from custom_components.comwintop.coordinator import UnitCoordinator
from custom_components.comwintop.model import effective_interval, revise_device, validate_device
from custom_components.comwintop.profiles import PROFILES, InvalidValue
from custom_components.comwintop.sensor import RawSensor

from .test_ha import make_entry, wait_for
from .wire import Simulator


class Unit:
    connected = True

    def __init__(self):
        self.calls = []
        self.faults = set()

    def on_connection_lost(self, cb):
        return lambda: None

    def set_message_spacing(self, value):
        pass

    def require_timeout(self, value):
        pass

    def require_connect_delay(self, value):
        pass

    async def disconnect(self):
        pass

    async def read_holding_registers(self, start, count):
        self.calls.append((start, count, time.monotonic()))
        if any(address in self.faults for address in range(start, start + count)):
            raise IllegalDataAddressError()
        return [220] * count


def configured_entry(
    channels=None,
    intervals=None,
    *,
    second=False,
    second_intervals=None,
    port=15020,
    transport="tcp",
):
    original = make_entry(type("Link", (), {"port": port})())
    sub = next(iter(original.subentries.values()))
    data = dict(sub.data) | {"channels": channels or {}, "intervals": intervals or {}}
    subentries = [
        {"subentry_type": "device", "title": "First", "unique_id": "device-id", "data": data}
    ]
    if second:
        second_data = dict(data) | {
            "unit_id": 2,
            "device_uid": "second-device",
            "model": "mb_308n",
            "channels": {},
            "intervals": second_intervals or {},
        }
        subentries.append(
            {
                "subentry_type": "device",
                "title": "Second",
                "unique_id": "second-device",
                "data": second_data,
            }
        )
    return ConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        title="Shared bus",
        data=dict(original.data) | {"transport": transport},
        options={},
        source="user",
        unique_id=f"shared-bus-{port}",
        discovery_keys=MappingProxyType({}),
        subentries_data=subentries,
    )


def coordinator(hass, settings=None):
    entry = configured_entry(settings)
    unit = Unit()
    sub = next(iter(entry.subentries.values()))
    return UnitCoordinator(hass, entry, sub, unit, asyncio.Lock(), logging.getLogger("test")), unit


def force_due(c, keys):
    for key in keys:
        c._next[key] = 0


@pytest.mark.parametrize("bad", [0, 4, 3601, 5.5, "5", True, float("nan")])
def test_override_validation_and_legacy_defaults(bad):
    data = dict(next(iter(configured_entry().subentries.values())).data)
    data["intervals"] = {"temperature": 30}
    assert effective_interval(data, "temperature_1") == 30
    data["channels"] = {"temperature_1": {"poll_interval": bad}}
    with pytest.raises(InvalidValue):
        validate_device(data)


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "5.5"])
def test_ui_rejects_nonfinite_and_fractional_seconds(bad):
    with pytest.raises(vol.Invalid):
        integral_seconds(bad)


def test_group_change_preserves_override_and_write_gate():
    old = dict(
        next(
            iter(
                configured_entry(
                    {"temperature_1": {"poll_interval": 5, "name": "Supply"}}
                ).subentries.values()
            )
        ).data
    )
    updated = revise_device(old, old | {"intervals": {"temperature": 60}})
    assert effective_interval(updated, "temperature_1") == 5
    assert effective_interval(updated, "temperature_2") == 60
    assert updated["channels"]["temperature_1"]["name"] == "Supply"


@pytest.mark.parametrize("key,minimum", [("di_1", 5), ("do_1", 5), ("ai_1", 5), ("ao_1", 5)])
def test_non_temperature_profile_minimums(key, minimum):
    data = dict(next(iter(configured_entry(second=True).subentries.values())).data)
    data["model"] = "mb_308n"
    data["channels"] = {key: {"poll_interval": minimum}}
    validate_device(data)
    data["channels"][key]["poll_interval"] = minimum - 1
    with pytest.raises(InvalidValue):
        validate_device(data)


def test_old_short_mb_intervals_load_but_new_short_intervals_are_rejected():
    old = dict(next(iter(configured_entry(second=True).subentries.values())).data)
    old["model"] = "mb_308n"
    old["intervals"] = {"di": 1, "do": 2, "ai": 2, "ao": 10}
    old["channels"] = {"di_1": {"poll_interval": 1}}
    validate_device(old, legacy=True)
    revise_device(old, old | {"name": "Retained settings"})
    with pytest.raises(InvalidValue):
        revise_device(old, old | {"intervals": old["intervals"] | {"do": 3}})


async def test_legacy_short_mb_interval_form_remains_editable(hass, sim):
    entry = configured_entry(
        second=True,
        port=sim.port,
        second_intervals={"di": 1, "do": 2, "ai": 10, "ao": 10},
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    mb = next(s for s in entry.subentries.values() if s.data["model"] == "mb_308n")
    assert (
        next(
            c for c in entry.runtime_data.units.values() if c.model == "mb_308n"
        ).minimum_read_rate_hz
        == 1.7
    )
    mgr = hass.config_entries.subentries
    flow = await mgr.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": mb.subentry_id},
    )
    form = await mgr.async_configure(flow["flow_id"], {"next_step_id": "intervals"})
    assert form["step_id"] == "intervals"
    rejected = await mgr.async_configure(flow["flow_id"], {"di": 1, "do": 3, "ai": 10, "ao": 10})
    assert rejected["type"] == "form" and rejected["errors"]["base"] == "invalid_interval"
    accepted = await mgr.async_configure(flow["flow_id"], {"di": 1, "do": 5, "ai": 10, "ao": 10})
    assert accepted["type"] == "abort"
    await hass.async_block_till_done()
    assert entry.subentries[mb.subentry_id].data["intervals"]["di"] == 1


async def test_mixed_due_blocks_and_no_fast_neighbor_refresh(hass):
    c, unit = coordinator(
        hass,
        {
            "temperature_1": {"poll_interval": 5},
            "temperature_2": {"poll_interval": 30},
            "temperature_3": {"poll_interval": 30},
        },
    )
    try:
        await c._poll_one(time.monotonic())
        assert [(a, n) for a, n, _ in unit.calls] == [(32, 32)]
        first_slow = c.samples["temperature_2"].received
        first_fast = c.samples["temperature_1"].received
        force_due(c, ["temperature_1"])
        await c._poll_one(time.monotonic())
        assert [(a, n) for a, n, _ in unit.calls] == [(32, 32), (32, 1)]
        assert c.samples["temperature_2"].received == first_slow
        assert c.samples["temperature_1"].received > first_fast
        force_due(c, ["temperature_2", "temperature_3"])
        await c._poll_one(time.monotonic())
        assert unit.calls[-1][:2] == (33, 2)
    finally:
        await c.stop()


async def test_disabled_channel_not_polled_or_refreshed(hass):
    c, unit = coordinator(hass, {"temperature_1": {"enabled": False}})
    try:
        await c._poll_one(time.monotonic())
        assert unit.calls[0][:2] == (33, 31)
        assert c.samples["temperature_1"].received is None
        assert not c.available("temperature_1")
    finally:
        await c.stop()


async def test_exception_isolates_one_register_and_bounded_splits(hass):
    c, unit = coordinator(hass)
    unit.faults.add(33)
    try:
        for _ in range(64):
            if not c._pending and unit.calls:
                break
            await c._poll_one(time.monotonic())
        assert len(unit.calls) <= 11  # 32 -> 16 -> 8 -> 4 -> 2 -> 1; good halves
        assert not c._pending
        assert c.samples["temperature_2"].error == "register_exception"
        assert c.samples["temperature_1"].available(time.monotonic(), 15)
        assert c.samples["temperature_32"].available(time.monotonic(), 15)
        assert c.counters["register_exceptions"] > 0
        initial_count = len(unit.calls)
        force_due(c, c.samples)
        for _ in range(3):
            await c._poll_one(time.monotonic())
        assert [call[:2] for call in unit.calls[initial_count:]] == [(32, 1), (33, 1), (34, 30)]
        unit.faults.clear()
        force_due(c, ["temperature_2"])
        await c._poll_one(time.monotonic())
        assert "temperature_2" not in c._known_bad
    finally:
        await c.stop()


async def test_partial_response_and_recovery_refreshes_slow_channels(hass):
    c, unit = coordinator(hass, {"temperature_32": {"poll_interval": 3600}})
    try:
        unit.read_holding_registers = AsyncMock(return_value=[200])
        await c._poll_one(time.monotonic())
        assert not any(c.available(key) for key in c.samples)
        unit.read_holding_registers = AsyncMock(side_effect=ModbusConnectionError("lost"))
        force_due(c, ["temperature_1"])
        await c._poll_one(time.monotonic())
        assert c.status == "OFFLINE" and not c.available("temperature_32")
        assert c._next["temperature_32"] - time.monotonic() < 10
        unit.read_holding_registers = AsyncMock(return_value=[220] * 32)
        for key in c.samples:
            c._next[key] = 0
        await c._poll_one(time.monotonic())
        assert c.available("temperature_32")
    finally:
        await c.stop()


async def test_busy_exception_does_not_trigger_block_split(hass):
    c, unit = coordinator(hass)
    unit.read_holding_registers = AsyncMock(side_effect=ServerDeviceBusyError())
    try:
        await c._poll_one(time.monotonic())
        assert unit.read_holding_registers.await_count == 1
        assert not c._pending and not c._known_bad
        assert c.counters["device_exceptions"] == 1
        assert 14 < min(c._next.values()) - time.monotonic() < 16
    finally:
        await c.stop()


async def test_channel_stale_is_individual_and_raw_follows_same_rule(hass):
    c, _ = coordinator(hass, {"temperature_1": {"poll_interval": 5}})
    try:
        now = time.monotonic()
        c.samples["temperature_1"].accept(22, 220, now - 16)
        c.samples["temperature_2"].accept(22, 220, now - 16)
        assert not c.available("temperature_1")
        assert c.available("temperature_2")
        assert not RawSensor(c, "temperature_1", PROFILES["tm_32ds"][0], 0).available
        assert RawSensor(c, "temperature_2", PROFILES["tm_32ds"][0], 1).available
    finally:
        await c.stop()


@pytest.fixture
async def sim():
    simulator = await Simulator().start()
    yield simulator
    await simulator.close()


async def test_ha_flow_override_and_reset(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1")
    manager = hass.config_entries.subentries

    async def configure(mode, value=None):
        flow = await manager.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
        flow = await manager.async_configure(flow["flow_id"], {"channel": "temperature_1"})
        assert flow["step_id"] == "channel_settings"
        fields = {marker.schema: schema for marker, schema in flow["data_schema"].schema.items()}
        assert fields["poll_interval_mode"].config["options"][0]["value"] == "standard"
        form = {"name": "Puffer Oben", "enabled": True, "poll_interval_mode": mode}
        if value is not None:
            form["poll_interval"] = value
        return await manager.async_configure(flow["flow_id"], form)

    assert (await configure("individual", 5))["type"] == "abort"
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    assert c.interval("temperature_1") == 5
    assert c.interval("temperature_2") == 15
    assert registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1") == entity_id
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    assert c.interval("temperature_1") == 5
    assert c.options("temperature_1")["name"] == "Puffer Oben"
    assert registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1") == entity_id
    assert (await configure("standard"))["type"] == "abort"
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    assert c.interval("temperature_1") == 15
    assert c.options("temperature_1")["name"] == "Puffer Oben"
    assert registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1") == entity_id
    assert not [call for call in sim.trace if call[1] not in (1, 2, 3, 4)]


async def test_real_error_sentinel_isolated(hass, sim):
    sim.registers[1, 33] = 0xFC18
    entry = configured_entry(port=sim.port)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.available("temperature_1"))
    assert not c.available("temperature_2")
    assert c.samples["temperature_2"].raw == 0xFC18
    assert c.available("temperature_3")


async def test_actual_tcp_scheduler_measured_intervals_and_shared_gateway(hass, sim):
    entry = configured_entry(
        {"temperature_1": {"poll_interval": 5}}, {"temperature": 15}, port=sim.port
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.available("temperature_32"))
    started = time.monotonic()
    async with asyncio.timeout(8):
        while len([r for r in sim.trace if r[1] == 3 and r[2] == 32]) < 2:  # noqa: ASYNC110
            await asyncio.sleep(0.02)
    assert time.monotonic() - started >= 4.5
    assert sim.trace[0] == (1, 3, 32, 32)
    assert (1, 3, 32, 1) in sim.trace
    timestamps = [
        t for call, t in zip(sim.trace, sim.trace_times, strict=True) if call == (1, 3, 32, 1)
    ]
    # The register-16 diagnostic can become due at five seconds as well;
    # the shared one-second gap may delay this channel by one bus slot.
    assert 4.7 <= timestamps[0] - sim.trace_times[0] <= 6.25
    assert not [r for r in sim.trace if r[1] in (5, 6, 15, 16)]


async def test_rtu_gateway_multiple_units_and_read_only(hass):
    sim = await Simulator("rtu").start()
    try:
        entry = configured_entry(
            {"temperature_1": {"poll_interval": 5}}, second=True, port=sim.port, transport="rtu_tcp"
        )
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        units = entry.runtime_data.units.values()
        await wait_for(
            lambda: all(any(s.received is not None for s in c.samples.values()) for c in units)
        )
        assert (1, 3, 32, 32) in sim.trace
        assert any(call[0] == 2 for call in sim.trace)
        assert len({id(c.bus_lock) for c in units}) == 1
        async with asyncio.timeout(7):
            while not (  # noqa: ASYNC110 - observe actual serial transactions
                sum(call[0] == 1 for call in sim.trace) >= 2
                and sum(call[0] == 2 for call in sim.trace) >= 2
            ):
                await asyncio.sleep(0.02)
        assert all(call[1] in (1, 2, 3, 4) for call in sim.trace)
    finally:
        await sim.close()


async def test_opt_in_raw_sensor_reports_actual_poll_timing(hass):
    """Live read cadence is measurable without HA history or permanent entity noise."""
    c, unit = coordinator(
        hass,
        {
            "temperature_1": {"poll_interval": 30},
            "temperature_2": {"poll_interval": 60},
        },
    )
    try:
        await c._poll_one(time.monotonic())
        diagnostic_fast = RawSensor(c, "temperature_1", PROFILES["tm_32ds"][0], 0)
        diagnostic_slow = RawSensor(c, "temperature_2", PROFILES["tm_32ds"][0], 1)
        fast = diagnostic_fast.extra_state_attributes
        slow = diagnostic_slow.extra_state_attributes
        assert fast["poll_interval_seconds"] == 30
        assert slow["poll_interval_seconds"] == 60
        assert fast["successful_read_count_since_reload"] == 1
        assert slow["successful_read_count_since_reload"] == 1
        assert fast["last_successful_read_utc"] is not None
        assert fast["seconds_between_successful_reads"] is None

        old_slow = slow["last_successful_read_utc"]
        old_slow_count = slow["successful_read_count_since_reload"]
        c._next["temperature_1"] = 0
        await c._poll_one(time.monotonic())
        fast = diagnostic_fast.extra_state_attributes
        slow = diagnostic_slow.extra_state_attributes
        assert fast["successful_read_count_since_reload"] == 2
        assert fast["seconds_between_successful_reads"] is not None
        assert slow["successful_read_count_since_reload"] == old_slow_count
        assert slow["last_successful_read_utc"] == old_slow
        assert [(start, count) for start, count, _ in unit.calls] == [(32, 32), (32, 1)]
    finally:
        await c.stop()


def test_poll_diagnostics_delta_uses_previous_successful_timestamp():
    from custom_components.comwintop.model import Sample

    sample = Sample()
    sample.accept(21.5, 215, 100.0)
    assert sample.successful_reads == 1
    assert sample.last_successful_read_delta_seconds is None
    sample.accept(21.6, 216, 130.25)
    assert sample.successful_reads == 2
    assert sample.last_successful_read_delta_seconds == 30.25
    sample.fail("timeout")
    sample.accept(21.7, 217, 195.0)
    assert sample.successful_reads == 3
    assert sample.last_successful_read_delta_seconds == 64.75


def test_bulk_disable_temperature_range_retains_options_and_identity():
    from custom_components.comwintop.model import disable_temperature_range

    original = dict(next(iter(configured_entry().subentries.values())).data)
    original["channels"] = {
        "temperature_1": {"name": "Room", "poll_interval": 60},
        "temperature_2": {"name": "Supply", "poll_interval": 30},
        "temperature_3": {"name": "Reserved", "poll_interval": 120},
    }
    result = disable_temperature_range(original, 3, 32)
    assert result["device_uid"] == original["device_uid"]
    assert result["channels"]["temperature_1"] == original["channels"]["temperature_1"]
    assert result["channels"]["temperature_2"] == original["channels"]["temperature_2"]
    assert result["channels"]["temperature_3"] == {
        "name": "Reserved",
        "poll_interval": 120,
        "enabled": False,
        "write_enabled": False,
    }
    assert all(not result["channels"][f"temperature_{i}"]["enabled"] for i in range(3, 33))
    assert "temperature_4" not in original["channels"]


@pytest.mark.parametrize("first,last", [(0, 32), (3, 33), (5, 4), (True, 32), (3, 1)])
def test_bulk_disable_rejects_invalid_ranges(first, last):
    from custom_components.comwintop.model import disable_temperature_range

    original = dict(next(iter(configured_entry().subentries.values())).data)
    with pytest.raises(InvalidValue):
        disable_temperature_range(original, first, last)


async def test_bulk_disable_ha_flow_requires_confirmation_and_never_writes(hass, sim):
    from homeassistant.helpers import config_validation as cv
    from probatio.codecs.fields import to_field_list

    entry = configured_entry(
        {"temperature_1": {"poll_interval": 60}, "temperature_2": {"poll_interval": 30}},
        port=sim.port,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    mgr = hass.config_entries.subentries
    flow = await mgr.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    assert "disable_temperature_range" in flow["menu_options"]
    form = await mgr.async_configure(flow["flow_id"], {"next_step_id": "disable_temperature_range"})
    to_field_list(form["data_schema"], custom_serializer=cv.custom_serializer)
    rejected = await mgr.async_configure(
        flow["flow_id"], {"first": 3, "last": 32, "confirm": False}
    )
    assert rejected["type"] == "form"
    assert rejected["errors"]["base"] == "bulk_confirmation_required"
    rejected = await mgr.async_configure(flow["flow_id"], {"first": 32, "last": 3, "confirm": True})
    assert rejected["type"] == "form"
    assert rejected["errors"]["base"] == "invalid_channel_range"
    saved = await mgr.async_configure(flow["flow_id"], {"first": 3, "last": 32, "confirm": True})
    assert saved["type"] == "abort", saved
    await hass.async_block_till_done()
    current = entry.subentries[sub.subentry_id].data
    assert current["channels"]["temperature_1"]["poll_interval"] == 60
    assert current["channels"]["temperature_2"]["poll_interval"] == 30
    assert all(not current["channels"][f"temperature_{i}"]["enabled"] for i in range(3, 33))
    assert not [call for call in sim.trace if call[1] not in (1, 2, 3, 4)]


async def test_actual_wire_cadence_for_three_temperature_intervals(hass, sim):
    """Measure requests and accepted samples on the TCP wire, not only deadlines."""
    entry = configured_entry(
        {
            "temperature_1": {"poll_interval": 5},
            "temperature_2": {"poll_interval": 10},
            "temperature_3": {"poll_interval": 30},
        },
        {"temperature": 15},
        port=sim.port,
    )
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.available("temperature_3"))
    initial = {
        key: c.samples[key].received for key in ("temperature_1", "temperature_2", "temperature_3")
    }
    async with asyncio.timeout(12):
        while c.samples["temperature_1"].successful_reads < 2:  # noqa: ASYNC110
            await asyncio.sleep(0.02)
    assert c.samples["temperature_2"].successful_reads == 1
    assert c.samples["temperature_3"].successful_reads == 1
    assert c.samples["temperature_1"].received - initial["temperature_1"] >= 4.7
    async with asyncio.timeout(8):
        while c.samples["temperature_2"].successful_reads < 2:  # noqa: ASYNC110
            await asyncio.sleep(0.02)
    assert c.samples["temperature_2"].received - initial["temperature_2"] >= 9.7
    assert c.samples["temperature_3"].successful_reads == 1
    assert c.samples["temperature_1"].successful_reads >= 2
    assert not [call for call in sim.trace if call[1] in (5, 6, 15, 16)]


async def test_first_timeout_retries_before_channel_stale_deadline(hass):
    """A single missed 15 s read must not cause an avoidable availability gap."""
    c, unit = coordinator(hass)
    key = "temperature_1"
    # Simulate the last valid value and the three-second failed request.
    c.samples[key].accept(20.0, 200, time.monotonic() - 18)
    for channel in c._next:
        c._next[channel] = 0 if channel == key else float("inf")
    unit.read_holding_registers = AsyncMock(side_effect=TimeoutError())
    try:
        await c._poll_one(time.monotonic())
        stale_deadline = c.samples[key].received + 3 * c.interval(key)
        assert c._next[key] < stale_deadline
        assert c.status == "ONLINE"  # First miss is diagnostic, not a visible alarm.
        assert c.counters["timeout"] == 1
        assert unit.read_holding_registers.await_count == 1
    finally:
        await c.stop()


async def test_poll_supervisor_restarts_twice_then_stops_and_invalidates(hass):
    """Permanent poll-loop failures cannot spin forever or leave old values online."""
    c, _unit = coordinator(hass)
    attempts = 0
    c.samples["temperature_1"].accept(20, 200, time.monotonic())

    async def broken_poll():
        nonlocal attempts
        attempts += 1
        raise RuntimeError("synthetic_poll_failure")

    c._poll = broken_poll
    task = asyncio.create_task(c._poll_supervised())
    c._poll_task = task
    try:
        async with asyncio.timeout(9):
            await task
        assert attempts == 3
        assert c.counters["poll_task_failures"] == 3
        assert c.counters["poll_task_exhausted"] == 1
        assert c.status == "OFFLINE"
        assert not c.available("temperature_1")
    finally:
        await c.stop()


async def test_new_mb_defaults_fit_measured_one_second_bus_spacing(hass):
    """Observe real TCP frames for all four MB groups, not only a rate formula."""
    from custom_components.comwintop.const import NEW_DEVICE_INTERVALS

    sim = await Simulator().start()
    entry = configured_entry(
        channels={f"temperature_{i}": {"enabled": False} for i in range(1, 33)},
        second=True,
        second_intervals={kind: NEW_DEVICE_INTERVALS[kind] for kind in ("di", "do", "ai", "ao")},
        port=sim.port,
    )
    try:
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        mb = next(c for c in entry.runtime_data.units.values() if c.model == "mb_308n")
        assert mb.minimum_read_rate_hz == 0.35
        async with asyncio.timeout(12):
            while len([f for f in sim.trace if f[0] == 2]) < 5:  # noqa: ASYNC110
                await asyncio.sleep(0.05)
        frames = [
            (frame, when)
            for frame, when in zip(sim.trace, sim.trace_times, strict=True)
            if frame[0] == 2
        ]
        assert {frame[1] for frame, _ in frames[:4]} == {1, 2, 3, 4}
        assert all(b - a >= 0.97 for (_, a), (_, b) in zip(frames, frames[1:], strict=False))
        first_di = next(t for f, t in frames if f[1] == 2)
        second_di = next(t for f, t in frames[1:] if f[1] == 2)
        assert second_di - first_di >= 8
        assert not [f for f in sim.trace if f[1] > 4]
    finally:
        if entry.runtime_data is not None:
            await hass.config_entries.async_unload(entry.entry_id)
        await sim.close()
