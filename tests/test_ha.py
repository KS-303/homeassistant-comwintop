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
