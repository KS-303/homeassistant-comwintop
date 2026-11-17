import asyncio
import json
from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.translation import async_get_translations

from custom_components.comwintop.const import DOMAIN
from custom_components.comwintop.diagnostics import async_get_config_entry_diagnostics

from .wire import Simulator


@pytest.fixture
async def sim():
    s = await Simulator().start()
    yield s
    await s.close()


def make_entry(sim):
    return ConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        title="Private test bus",
        data={
            "transport": "tcp",
            "host": "127.0.0.1",
            "port": sim.port,
            "name": "Private test bus",
            "connection_uid": "bus-id",
        },
        options={},
        source="user",
        unique_id=f"tcp|127.0.0.1|{sim.port}",
        discovery_keys=MappingProxyType({}),
        subentries_data=[
            {
                "subentry_type": "device",
                "title": "Temperature module",
                "unique_id": "device-id",
                "data": {
                    "model": "tm_32ds",
                    "unit_id": 1,
                    "device_uid": "device-id",
                    "name": "Temperature module",
                    "connection_uid": "bus-id",
                    "channels": {},
                    "intervals": {},
                },
            }
        ],
    )


async def wait_for(predicate):
    async with asyncio.timeout(5):
        while not predicate():  # noqa: ASYNC110 - observe HA-owned asynchronous state
            await asyncio.sleep(0.02)


async def test_real_ha_setup_poll_reload_registry_no_writes(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded", entry.reason
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.samples["temperature_32"].value is not None)
    registry = er.async_get(hass)
    uid = "device-id_temperature_32"
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, uid)
    assert entity_id is not None
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "23.1"
    assert hass.states.get(entity_id).attributes["friendly_name"].endswith("Temperature channel 32")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_entity_id("sensor", DOMAIN, uid) == entity_id
    assert not [r for r in sim.trace if r[1] not in (1, 2, 3, 4)]
    assert not [
        x
        for x in registry.entities.values()
        if x.platform == DOMAIN and x.domain in ("switch", "number")
    ]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert c._poll_task.done() and c._age_task.done()


async def test_config_flow_and_duplicate(hass, sim):
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert flow["step_id"] == "user"
    flow = await hass.config_entries.flow.async_configure(flow["flow_id"], {"transport": "tcp"})
    assert flow["step_id"] == "connection"
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"name": "Test", "host": "127.0.0.1", "port": sim.port}
    )
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"transport": "tcp_gateway"}
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"name": "duplicate", "host": "127.0.0.1", "port": sim.port}
    )
    assert result["type"] == "abort" and result["reason"] == "already_configured"


async def test_german_channel_name_without_ch_abbreviation(hass, sim):
    hass.config.language = "de"
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1")
    assert hass.states.get(entity_id).attributes["friendly_name"].endswith("Temperaturkanal 1")


async def test_translated_connection_and_channel_choices(hass):
    texts = await async_get_translations(hass, "de", "selector", {DOMAIN}, config_flow=True)
    assert texts["component.comwintop.selector.transport.options.rtu_tcp"] == (
        "Transparente serielle Verbindung über Netzwerk"
    )
    assert texts["component.comwintop.selector.channel.options.di_1"] == "Digitaler Eingang 1"


async def test_setup_dropdown_contains_visible_german_labels(hass):
    """Frontend must receive labels directly, independent of selector translations."""
    hass.config.language = "de"
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    fields = {key.schema: value for key, value in flow["data_schema"].schema.items()}
    options = fields["transport"].config["options"]
    assert options == [
        {"value": "tcp", "label": "Modbus über Netzwerk"},
        {"value": "tcp_gateway", "label": "Modbus über Netzwerk-Seriell-Gateway"},
        {"value": "rtu_tcp", "label": "Transparente serielle Verbindung über Netzwerk"},
        {"value": "serial", "label": "Direkte serielle Verbindung"},
    ]
    form = await hass.config_entries.flow.async_configure(flow["flow_id"], {"transport": "rtu_tcp"})
    fields = {key.schema: value for key, value in form["data_schema"].schema.items()}
    assert fields["parity"].config["options"] == [
        {"value": "N", "label": "Keine Parität"},
        {"value": "E", "label": "Gerade Parität"},
        {"value": "O", "label": "Ungerade Parität"},
    ]


async def test_subentry_create_no_write_probe(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    manager = hass.config_entries.subentries
    result = await manager.async_init((entry.entry_id, "device"), context={"source": "user"})
    result = await manager.async_configure(
        result["flow_id"],
        {"name": "IO", "model": "mb_308n", "unit_id": 2, "acknowledge_beta": True},
    )
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    assert len(entry.subentries) == 2
    assert not [r for r in sim.trace if r[1] not in (1, 2, 3, 4)]


async def test_diagnostics_redacts_endpoint_and_names(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    text = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    assert (
        "127.0.0.1" not in text
        and "Private test bus" not in text
        and "Temperature module" not in text
    )
    assert "device-id" not in text and "registers" not in text


async def test_invalid_sensor_only_affects_one_channel(hass, sim):
    sim.registers[1, 32] = 65535
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.last_response is not None)
    assert not c.available("temperature_1")
    assert c.available("temperature_32")
    assert c.samples["temperature_1"].raw == 65535


async def test_connection_loss_immediate_unavailable(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.available("temperature_1"))
    for writer in tuple(sim.writers):
        writer.close()
    await wait_for(lambda: c.status == "OFFLINE")
    assert not c.available("temperature_1")


async def test_channel_configuration_deactivate_reactivate_preserves_id(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    registry = er.async_get(hass)
    eid = registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1")

    async def configure_channel(enabled):
        manager = hass.config_entries.subentries
        result = await manager.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        result = await manager.async_configure(result["flow_id"], {"next_step_id": "channel"})
        result = await manager.async_configure(result["flow_id"], {"channel": "temperature_1"})
        result = await manager.async_configure(
            result["flow_id"], {"name": "Test sensor", "enabled": enabled}
        )
        assert result["type"] == "abort"
        await hass.async_block_till_done()

    await configure_channel(False)
    c = next(iter(entry.runtime_data.units.values()))
    assert not c.enabled("temperature_1")
    assert hass.states.get(eid).state == "unavailable"
    await configure_channel(True)
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.available("temperature_1"))
    assert registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1") == eid
    assert not [r for r in sim.trace if r[1] > 4]


async def test_reconfigure_address_preserves_entities(hass, sim):
    sim.registers.update({(3, i): 400 for i in range(32, 64)})
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    registry = er.async_get(hass)
    eid = registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1")
    manager = hass.config_entries.subentries
    result = await manager.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    result = await manager.async_configure(result["flow_id"], {"next_step_id": "device"})
    result = await manager.async_configure(
        result["flow_id"], {"name": "Moved address", "unit_id": 3}
    )
    assert result["type"] == "abort"
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.samples["temperature_1"].value == 40)
    assert registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1") == eid
    assert hass.states.get(eid).state == "40.0"


async def test_stale_timer_expires_without_a_new_poll(hass, sim):
    import time

    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: c.available("temperature_1"))
    registry = er.async_get(hass)
    eid = registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1")
    c.samples["temperature_1"].received = time.monotonic() - 44.8
    c._last_available = None
    c.samples["temperature_1"].fail("timeout")
    await wait_for(lambda: hass.states.get(eid).state == "unavailable")
    assert c.samples["temperature_1"].value == 20


async def test_interval_configuration(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    manager = hass.config_entries.subentries
    result = await manager.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    result = await manager.async_configure(result["flow_id"], {"next_step_id": "intervals"})
    result = await manager.async_configure(result["flow_id"], {"temperature": 30})
    assert result["type"] == "abort"
    await hass.async_block_till_done()
    assert next(iter(entry.runtime_data.units.values())).intervals["temperature"] == 30


async def test_duplicate_unit_is_rejected(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    manager = hass.config_entries.subentries
    result = await manager.async_init((entry.entry_id, "device"), context={"source": "user"})
    result = await manager.async_configure(
        result["flow_id"],
        {"name": "Duplicate", "model": "tm_32ds", "unit_id": 1, "acknowledge_beta": True},
    )
    assert result["type"] == "form" and result["errors"]["base"] == "duplicate_unit"
    assert len(entry.subentries) == 1


async def test_connection_reconfigure_probe_preserves_identity(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    eid = registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1")
    destination = await Simulator().start()
    destination.registers[1, 32] = 345
    try:
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {"name": "Moved connection", "host": "127.0.0.1", "port": destination.port},
        )
        assert result["type"] == "abort", result
        await hass.async_block_till_done()
        c = next(iter(entry.runtime_data.units.values()))
        await wait_for(lambda: c.samples["temperature_1"].value == 34.5)
        assert registry.async_get_entity_id("sensor", DOMAIN, "device-id_temperature_1") == eid
        assert entry.data["connection_uid"] == "bus-id"
        assert all(r[1] <= 4 for r in destination.trace)
    finally:
        await destination.close()


async def test_mb308_channel_ui_and_entities(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    manager = hass.config_entries.subentries
    result = await manager.async_init((entry.entry_id, "device"), context={"source": "user"})
    result = await manager.async_configure(
        result["flow_id"],
        {"name": "IO", "model": "mb_308n", "unit_id": 2, "acknowledge_beta": True},
    )
    await hass.async_block_till_done()
    sub = next(s for s in entry.subentries.values() if s.data["unit_id"] == 2)
    for key, settings in (
        ("ai_1", {"enabled": True, "mode": "0_10v", "display": "percent"}),
        ("di_1", {"enabled": True, "nc": True}),
    ):
        flow = await manager.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
        flow = await manager.async_configure(flow["flow_id"], {"channel": key})
        result = await manager.async_configure(flow["flow_id"], settings)
        assert result["type"] == "abort", result
        await hass.async_block_till_done()
    c = entry.runtime_data.units[sub.subentry_id]
    await wait_for(lambda: c.available("ai_1") and c.available("di_1"))
    registry = er.async_get(hass)
    ai = registry.async_get_entity_id("sensor", DOMAIN, f"{c.uid}_ai_1")
    di = registry.async_get_entity_id("binary_sensor", DOMAIN, f"{c.uid}_di_1")
    assert hass.states.get(ai).state == "50.0"
    assert hass.states.get(ai).attributes["unit_of_measurement"] == "%"
    assert hass.states.get(di).state == "on"
    assert hass.states.get(di).attributes["friendly_name"].endswith("Digital input 1")
    assert not [r for r in sim.trace if r[1] > 4]


async def test_channel_form_serializes_and_accepts_all_32_ids(hass, sim):
    """Real HA flow forms must serialize and accept internal channel IDs."""
    from homeassistant.helpers import config_validation as cv
    from probatio.codecs.fields import to_field_list

    hass.config.language = "de"
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    manager = hass.config_entries.subentries

    # Recreate the actual HTTP serialization path that raised on integral_seconds.
    for channel_no in (1, 3, 16, 32):
        flow = await manager.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
        to_field_list(flow["data_schema"], custom_serializer=cv.custom_serializer)
        result = await manager.async_configure(
            flow["flow_id"], {"channel": f"temperature_{channel_no}"}
        )
        assert result["step_id"] == "channel_settings", result
        to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
        result = await manager.async_configure(
            flow["flow_id"],
            {"name": f"Channel {channel_no}", "enabled": True, "poll_interval_mode": "standard"},
        )
        assert result["type"] == "abort", result
        await hass.async_block_till_done()


async def test_channel_interval_fractional_rejected_without_write(hass, sim):
    from homeassistant.helpers import config_validation as cv
    from probatio.codecs.fields import to_field_list

    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    manager = hass.config_entries.subentries
    flow = await manager.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
    flow = await manager.async_configure(flow["flow_id"], {"channel": "temperature_3"})
    to_field_list(flow["data_schema"], custom_serializer=cv.custom_serializer)
    result = await manager.async_configure(
        flow["flow_id"],
        {"name": "Test", "enabled": True, "poll_interval_mode": "individual", "poll_interval": 5.5},
    )
    assert result["type"] == "form", result
    assert result["errors"]["base"] == "invalid_interval"
    to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    assert not [call for call in sim.trace if call[1] not in (1, 2, 3, 4)]


async def test_mb308n_all_channel_forms_serialize_and_preserve_settings(hass, sim):
    """All 28 MB308N channel forms render in HA and keep read-only I/O gates."""
    from homeassistant.helpers import config_validation as cv
    from probatio.codecs.fields import to_field_list

    hass.config.language = "de"
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    manager = hass.config_entries.subentries
    result = await manager.async_init((entry.entry_id, "device"), context={"source": "user"})
    result = await manager.async_configure(
        result["flow_id"],
        {"name": "MB308N", "model": "mb_308n", "unit_id": 2, "acknowledge_beta": True},
    )
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    sub = next(s for s in entry.subentries.values() if s.data["unit_id"] == 2)

    expected_channels = (
        [f"di_{i}" for i in range(1, 9)]
        + [f"do_{i}" for i in range(1, 9)]
        + [f"ai_{i}" for i in range(1, 9)]
        + [f"ao_{i}" for i in range(1, 5)]
    )
    for key in expected_channels:
        flow = await manager.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
        to_field_list(flow["data_schema"], custom_serializer=cv.custom_serializer)
        form = await manager.async_configure(flow["flow_id"], {"channel": key})
        assert form["step_id"] == "channel_settings", (key, form)
        to_field_list(form["data_schema"], custom_serializer=cv.custom_serializer)
        fields = {marker.schema for marker in form["data_schema"].schema}
        assert {"name", "enabled", "poll_interval_mode", "poll_interval"} <= fields
        assert ("nc" in fields) == key.startswith("di_")
        assert ("mode" in fields) == key.startswith(("ai_", "ao_"))
        assert "write_enabled" not in fields

    cases = (
        ("di_1", {"nc": True}),
        ("di_2", {"nc": False}),
        ("do_1", {}),
        ("ai_1", {"mode": "0_10v", "display": "physical"}),
        ("ai_2", {"mode": "4_20ma", "display": "percent"}),
        ("ao_1", {"mode": "4_20ma", "display": "physical"}),
        ("ao_2", {"mode": "0_10v", "display": "percent"}),
    )
    for key, settings in cases:
        flow = await manager.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
        flow = await manager.async_configure(flow["flow_id"], {"channel": key})
        form = {"name": key, "enabled": True, "poll_interval_mode": "standard"} | settings
        saved = await manager.async_configure(flow["flow_id"], form)
        assert saved["type"] == "abort", (key, saved)
        await hass.async_block_till_done()
        updated = entry.subentries[sub.subentry_id].data["channels"][key]
        assert all(updated[field] == value for field, value in settings.items())

    # UI configuration must never enable or emit unvalidated output writes.
    assert not any(
        setting.get("write_enabled")
        for setting in entry.subentries[sub.subentry_id].data["channels"].values()
    )
    assert not [call for call in sim.trace if call[1] not in (1, 2, 3, 4)]


async def test_tm32ds_creation_scans_registers_and_skips_unplugged_entities(hass, sim):
    """The one-time scan uses FC03 blocks; only confirmed channels get entities."""
    for index in range(32):
        sim.registers[(2, 32 + index)] = 213 if index == 0 else 212 if index == 1 else 0xFC18
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    manager = hass.config_entries.subentries
    flow = await manager.async_init((entry.entry_id, "device"), context={"source": "user"})
    result = await manager.async_configure(
        flow["flow_id"],
        {
            "name": "New temperature module",
            "model": "tm_32ds",
            "unit_id": 2,
            "acknowledge_beta": True,
        },
    )
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    sub = next(s for s in entry.subentries.values() if s.data["unit_id"] == 2)
    assert all(
        sub.data["channels"][f"temperature_{index}"]["enabled"] is False for index in range(3, 33)
    )
    assert "temperature_1" not in sub.data["channels"]
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{sub.data['device_uid']}_temperature_1")
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{sub.data['device_uid']}_temperature_2")
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{sub.data['device_uid']}_temperature_3")
        is None
    )
    assert (
        registry.async_get_entity_id(
            "sensor", DOMAIN, f"{sub.data['device_uid']}_temperature_3_raw"
        )
        is None
    )
    scans = [frame for frame in sim.trace if frame[:3] == (2, 3, 32) and frame[3] == 32]
    assert len(scans) == 3
    assert not [frame for frame in sim.trace if frame[1] not in (1, 2, 3, 4)]
    flow = await manager.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
    flow = await manager.async_configure(flow["flow_id"], {"channel": "temperature_3"})
    result = await manager.async_configure(
        flow["flow_id"],
        {"name": "", "enabled": True, "poll_interval_mode": "standard"},
    )
    assert result["type"] == "abort", result
    await hass.async_block_till_done()
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{sub.data['device_uid']}_temperature_3")


async def test_scan_rejects_ambiguous_and_partial_values():
    from custom_components.comwintop.config_flow import detected_tm32ds_channels

    first = [210] * 32
    second = [210] * 32
    third = [211] * 32
    second[1] = third[1] = 0
    second[2] = third[2] = 850
    second[3] = third[3] = 0xFC18
    third[4] = 0xFC18
    disabled = detected_tm32ds_channels((first, second, third))
    assert "temperature_1" not in disabled
    assert set(disabled) == {f"temperature_{i}" for i in range(2, 6)}
    with pytest.raises(ValueError, match="invalid_scan_length"):
        detected_tm32ds_channels((first, second[:31], third))


async def test_reconfigure_bulk_menu_has_visible_label_and_numeric_boxes(hass, sim):
    from homeassistant.helpers import config_validation as cv
    from probatio.codecs.fields import to_field_list

    hass.config.language = "de"
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    manager = hass.config_entries.subentries
    flow = await manager.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    assert (
        flow["menu_options"]["disable_temperature_range"]
        == "Temperaturkanäle gesammelt deaktivieren"
    )
    translations = await async_get_translations(
        hass, "de", "config_subentries", {DOMAIN}, config_flow=True
    )
    assert (
        translations[
            "component.comwintop.config_subentries.device.step.disable_temperature_range.data.first"
        ]
        == "Erster Kanal (1–32)"
    )
    form = await manager.async_configure(
        flow["flow_id"], {"next_step_id": "disable_temperature_range"}
    )
    fields = {marker.schema: value for marker, value in form["data_schema"].schema.items()}
    assert fields["first"].config["max"] == fields["last"].config["max"] == 32
    to_field_list(form["data_schema"], custom_serializer=cv.custom_serializer)
    assert not [frame for frame in sim.trace if frame[1] not in (1, 2, 3, 4)]


async def test_tm32ds_bulk_activation_preserves_settings_and_never_writes(hass, sim):
    from custom_components.comwintop.model import set_temperature_range_enabled

    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    old = dict(sub.data) | {
        "channels": {"temperature_3": {"name": "Puffer", "poll_interval": 30, "enabled": False}}
    }
    changed = set_temperature_range_enabled(old, 3, 4, True)
    assert changed["device_uid"] == old["device_uid"]
    assert changed["channels"]["temperature_3"]["name"] == "Puffer"
    assert changed["channels"]["temperature_3"]["poll_interval"] == 30
    assert changed["channels"]["temperature_3"]["enabled"] is True
    assert changed["channels"]["temperature_4"]["enabled"] is True
    after_disable = set_temperature_range_enabled(changed, 4, 4, False)
    assert after_disable["channels"]["temperature_3"]["enabled"]
    with pytest.raises(ValueError):
        set_temperature_range_enabled(old, 4, 3, True)
    manager = hass.config_entries.subentries
    flow = await manager.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    assert "enable_temperature_range" in flow["menu_options"]
    form = await manager.async_configure(
        flow["flow_id"], {"next_step_id": "enable_temperature_range"}
    )
    assert form["type"] == "form"
    rejected = await manager.async_configure(
        form["flow_id"], {"first": 3, "last": 4, "confirm": False}
    )
    assert rejected["errors"]["base"] == "bulk_confirmation_required"
    result = await manager.async_configure(
        rejected["flow_id"], {"first": 3, "last": 4, "confirm": True}
    )
    assert result["type"] == "abort", result
    await hass.async_block_till_done()
    assert entry.subentries[sub.subentry_id].data["channels"]["temperature_3"]["enabled"]
    assert not [frame for frame in sim.trace if frame[1] not in (1, 2, 3, 4)]


async def test_channel_interval_value_requires_individual_choice_and_diagnostics(hass, sim):
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    manager = hass.config_entries.subentries
    flow = await manager.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    flow = await manager.async_configure(flow["flow_id"], {"next_step_id": "channel"})
    flow = await manager.async_configure(flow["flow_id"], {"channel": "temperature_1"})
    form = {"name": "", "enabled": True, "poll_interval_mode": "standard", "poll_interval": 5}
    result = await manager.async_configure(flow["flow_id"], form)
    assert result["errors"]["base"] == "choose_individual_interval"
    assert not sub.data["channels"].get("temperature_1", {}).get("poll_interval")
    form["poll_interval_mode"] = "individual"
    result = await manager.async_configure(result["flow_id"], form)
    assert result["type"] == "abort", result
    await hass.async_block_till_done()
    data = await async_get_config_entry_diagnostics(hass, entry)
    channels = data["devices"][0]["channels"]
    assert channels["temperature_1"]["effective_interval"] == 5
    assert channels["temperature_1"]["interval_source"] == "individual"
    assert channels["temperature_2"]["effective_interval"] == 15
    assert channels["temperature_2"]["interval_source"] == "group"
    assert "successful_reads_since_reload" in channels["temperature_1"]
    assert not [frame for frame in sim.trace if frame[1] not in (1, 2, 3, 4)]


async def test_communication_register_refreshes_after_read_recovery(hass, sim):
    """A recovered TM-32DS refreshes register 16 without waiting five minutes."""
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    async with asyncio.timeout(8):
        while c.communication_values is None:  # noqa: ASYNC110
            await asyncio.sleep(0.02)
    initial = sum(frame[:3] == (1, 3, 16) for frame in sim.trace)
    c.connection_lost()
    assert c.communication_values is None
    await wait_for(lambda: c.communication_values is not None)
    assert sum(frame[:3] == (1, 3, 16) for frame in sim.trace) == initial + 1
    assert not [frame for frame in sim.trace if frame[1] not in (1, 2, 3, 4)]


async def test_failed_communication_register_rechecks_after_healthy_temperature(hass, sim):
    """One failed diagnostic read must not leave the address hidden for five minutes."""
    sim.registers[(1, 16)] = 0x0104
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    c = next(iter(entry.runtime_data.units.values()))
    async with asyncio.timeout(8):
        while c.communication_values is None:  # noqa: ASYNC110
            await asyncio.sleep(0.02)
    original = c.unit.read_holding_registers

    async def fail_register_16_once(address, count):
        if address == 16:
            raise TimeoutError
        return await original(address, count)

    c.unit.read_holding_registers = fail_register_16_once
    assert await c.read_communication() is None
    assert c.communication_values is None
    c.unit.read_holding_registers = original
    # Simulate the elapsed, bounded diagnostic retry window; no five-minute wait.
    c._communication_retry_at = 0
    for key in c._next:
        if c.enabled(key):
            c._next[key] = 0
    await wait_for(lambda: c.communication_values is not None)
    assert c.communication_values["address"] == "1"
    assert not [frame for frame in sim.trace if frame[1] not in (1, 2, 3, 4)]
