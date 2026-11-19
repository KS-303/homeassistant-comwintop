"""RTU uncertain-read gate: pure lifecycle and read-safety regression tests."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.comwintop import rtu_safety
from custom_components.comwintop.rtu_safety import RtuBusUnsafe, RtuSessionGuard


class FakeStore:
    persisted = None

    def __init__(self, hass, version, key):
        self.key = key
        self.path = Path(hass.config.path(".storage", key)) if hass is not None else None

    async def async_load(self):
        return self.persisted

    async def async_save(self, data):
        type(self).persisted = data
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"key": self.key, "data": data}), encoding="utf-8")


class FakeUnit:
    def __init__(self):
        self.unsafe_calls = 0

    def mark_bus_unsafe(self):
        self.unsafe_calls += 1


@pytest.fixture(autouse=True)
def reset_store(monkeypatch):
    FakeStore.persisted = None
    monkeypatch.setattr(rtu_safety, "Store", FakeStore)


def guard():
    return RtuSessionGuard(
        None,
        SimpleNamespace(
            data={"transport": "rtu_tcp", "host": "127.0.0.1", "port": 502},
            entry_id="test",
        ),
    )


async def test_clean_session_reloads_without_manual_reset():
    first = guard()
    await first.arm()
    assert FakeStore.persisted == {"active": True}
    with first.reading():
        pass
    await first.close()
    assert FakeStore.persisted == {"active": False}
    second = guard()
    await second.arm()
    await second.close()


async def test_isolated_timeout_is_transient_and_next_read_restores_session():
    first = guard()
    await first.arm()
    unit = FakeUnit()
    first.attach(unit)
    with pytest.raises(TimeoutError):
        with first.reading():
            raise TimeoutError
    assert not first.unsafe and unit.unsafe_calls == 0
    assert first.unverified_after_timeout
    assert first.transient_timeouts == 1
    assert first.quiet_until > 0
    # An HA unload while a timeout is still unresolved cannot erase the
    # persistent marker, even though this was only one missed reply.
    await first.close()
    assert FakeStore.persisted == {"active": True}
    with pytest.raises(Exception, match="Unclean or uncertain"):
        await guard().arm()
    # The existing live session can recover after observing a new reply.
    with first.reading():
        pass
    assert not first.unverified_after_timeout and first.recovered_timeouts == 1
    await first.close()
    assert FakeStore.persisted == {"active": False}


async def test_second_unanswered_read_latches_bus_and_blocks_reconnect():
    first = guard()
    await first.arm()
    unit = FakeUnit()
    first.attach(unit)
    for i in range(2):
        with pytest.raises(TimeoutError):
            with first.reading():
                raise TimeoutError
        assert first.unsafe is (i == 1)
    assert unit.unsafe_calls == 1
    with pytest.raises(RtuBusUnsafe):
        with first.reading():
            raise AssertionError("never sent")
    await first.close()
    assert FakeStore.persisted == {"active": True}
    with pytest.raises(Exception, match="Unclean or uncertain"):
        await guard().arm()


async def test_transient_timeout_enforces_shared_quiet_period(monkeypatch):
    first = guard()
    await first.arm()
    monkeypatch.setattr(rtu_safety, "RTU_READ_QUIET_SECONDS", 0.04)
    with pytest.raises(TimeoutError):
        with first.reading():
            raise TimeoutError
    started = rtu_safety.time.monotonic()
    await first.settle()
    assert rtu_safety.time.monotonic() - started >= 0.035
    with first.reading():
        pass
    await first.close()


async def test_read_cancellation_latches_bus():
    first = guard()
    await first.arm()
    with pytest.raises(asyncio.CancelledError):
        with first.reading():
            raise asyncio.CancelledError
    assert first.unsafe
    await first.close()


async def test_failed_save_does_not_arm_or_transmit(monkeypatch):
    original = FakeStore.async_save

    async def broken(self, data):
        raise OSError("disk failed")

    monkeypatch.setattr(FakeStore, "async_save", broken)
    first = guard()
    with pytest.raises(OSError):
        await first.arm()
    assert not first._armed
    monkeypatch.setattr(FakeStore, "async_save", original)


async def test_inflight_session_marker_survives_simulated_process_crash():
    first = guard()
    await first.arm()
    assert FakeStore.persisted == {"active": True}
    with pytest.raises(Exception, match="Unclean or uncertain"):
        await guard().arm()


def test_tcp_gateway_transport_is_guarded():
    gateway = RtuSessionGuard(
        None,
        SimpleNamespace(
            data={"transport": "tcp_gateway", "host": "127.0.0.1", "port": 502},
            entry_id="gateway",
        ),
    )
    assert gateway.enabled


def test_tcp_transport_has_no_rtu_guard():
    first = RtuSessionGuard(None, SimpleNamespace(data={"transport": "tcp"}, entry_id="test"))
    assert not first.enabled


async def test_known_modbus_exception_does_not_latch_bus():
    from modbus_connection.exceptions import IllegalDataAddressError

    first = guard()
    await first.arm()
    with pytest.raises(IllegalDataAddressError):
        with first.reading():
            raise IllegalDataAddressError
    assert not first.unsafe
    await first.close()


async def test_real_coordinator_stops_polling_after_repeated_rtu_timeouts(
    hass, monkeypatch
):
    """After two ambiguous timeouts even a forced poll cannot emit a new frame."""
    import logging
    import time
    from unittest.mock import AsyncMock

    from custom_components.comwintop.coordinator import UnitCoordinator

    from .test_l50 import Unit, configured_entry

    monkeypatch.setattr(rtu_safety, "RTU_READ_QUIET_SECONDS", 0.001)
    entry = configured_entry(transport="rtu_tcp")
    gate = RtuSessionGuard(hass, entry)
    await gate.arm()
    unit = Unit()
    sub = next(iter(entry.subentries.values()))
    c = UnitCoordinator(hass, entry, sub, unit, asyncio.Lock(), logging.getLogger("test"), gate)
    gate.attach(c)
    unit.read_holding_registers = AsyncMock(side_effect=TimeoutError())
    await c._poll_one(time.monotonic())
    assert not gate.unsafe
    assert gate.transient_timeouts == 1
    assert c.status == "SUSPECT"
    for key in c._next:
        if c.enabled(key):
            c._next[key] = 0
    await c._poll_one(time.monotonic())
    assert gate.unsafe
    assert c.status == "OFFLINE"
    assert not c.available("temperature_1")
    assert all(value == float("inf") for value in c._next.values())
    await c._poll_one(time.monotonic())
    assert unit.read_holding_registers.await_count == 2
    await c.stop()
    await gate.close()


async def test_dropped_storage_write_blocks_first_rtu_request(hass, monkeypatch):
    from homeassistant.exceptions import ConfigEntryError

    from .test_l50 import configured_entry

    gate = RtuSessionGuard(hass, configured_entry(transport="rtu_tcp"))

    async def write_that_does_not_persist(self, data):
        FakeStore.persisted = data

    monkeypatch.setattr(FakeStore, "async_save", write_that_does_not_persist)
    with pytest.raises(ConfigEntryError, match="not durably stored"):
        await gate.arm()
    assert not gate._armed


async def test_existing_corrupt_marker_fails_closed(hass):
    from homeassistant.exceptions import ConfigEntryError

    from .test_l50 import configured_entry

    gate = RtuSessionGuard(hass, configured_entry(transport="rtu_tcp"))
    marker = gate._store.path
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("not valid json", encoding="utf-8")
    with pytest.raises(ConfigEntryError, match="marker corrupt"):
        await gate.arm()
    assert not gate._armed


def test_same_gateway_key_survives_entry_recreation(hass):
    from .test_l50 import configured_entry

    first = configured_entry(transport="rtu_tcp", port=15555)
    second = configured_entry(transport="rtu_tcp", port=15555)
    assert first.entry_id != second.entry_id
    first_gate = RtuSessionGuard(hass, first)
    second_gate = RtuSessionGuard(hass, second)
    assert first_gate._store.key == second_gate._store.key


async def test_b17_single_missing_response_keeps_last_temperature_available(hass, monkeypatch):
    """b17 observed two isolated missed responses without any sensor outage."""
    import logging
    import time
    from unittest.mock import AsyncMock

    from custom_components.comwintop.coordinator import UnitCoordinator

    from .test_l50 import Unit, configured_entry

    monkeypatch.setattr(rtu_safety, "RTU_READ_QUIET_SECONDS", 0.001)
    entry = configured_entry(transport="rtu_tcp")
    gate = RtuSessionGuard(hass, entry)
    await gate.arm()
    unit = Unit()
    sub = next(iter(entry.subentries.values()))
    coordinator = UnitCoordinator(
        hass, entry, sub, unit, asyncio.Lock(), logging.getLogger("test"), gate
    )
    gate.attach(coordinator)
    calls = 0

    async def read(start, count):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise TimeoutError
        return [220] * count

    unit.read_holding_registers = AsyncMock(side_effect=read)
    try:
        await coordinator._poll_one(time.monotonic())
        assert coordinator.available("temperature_1")
        previous = coordinator.samples["temperature_1"].value
        for key in coordinator._next:
            if coordinator.enabled(key):
                coordinator._next[key] = 0
        await coordinator._poll_one(time.monotonic())
        assert coordinator.available("temperature_1")
        assert coordinator.samples["temperature_1"].value == previous
        assert coordinator.status == "SUSPECT"
        assert not gate.unsafe and gate.unverified_after_timeout
        for key in coordinator._next:
            if coordinator.enabled(key):
                coordinator._next[key] = 0
        await coordinator._poll_one(time.monotonic())
        assert coordinator.available("temperature_1")
        assert coordinator.status == "ONLINE"
        assert gate.recovered_timeouts == 1 and gate.consecutive_timeouts == 0
        assert unit.read_holding_registers.await_count == 3
    finally:
        await coordinator.stop()
        await gate.close()
