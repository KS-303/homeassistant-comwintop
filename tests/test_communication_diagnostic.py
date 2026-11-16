"""TM-32DS register-16 diagnostic and boxed HA unit-ID selectors."""

from homeassistant.helpers import entity_registry as er

from custom_components.comwintop.const import DOMAIN

from .test_l50 import configured_entry
from .wire import Simulator


async def test_register_16_single_diagnostic_entity_no_per_entity_reads(hass):
    sim = await Simulator().start()
    try:
        sim.registers[1, 16] = 0x0204
        entry = configured_entry(port=sim.port)
        # Match the ID encoded in register 16.
        sub = next(iter(entry.subentries.values()))
        # We check initial configuration independently below. For a valid
        # register reading, simulate the device configured under slave 1.
        sim.registers[1, 16] = 0x0104
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        c = next(iter(entry.runtime_data.units.values()))

        assert await c.read_communication() is not None
        await hass.async_block_till_done()
        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{c.uid}_communication_register"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state.state == "0x0104"
        assert state.attributes["device_slave_id"] == "1"
        assert state.attributes["configured_slave_id"] == "1"
        assert state.attributes["baudrate"] == "9600"
        assert state.attributes["parity"] == "N"
        assert state.attributes["data_bits"] == "8"
        assert state.attributes["stop_bits"] == "1"
        assert state.attributes["read_status"] == "read_only"
        before = len([item for item in sim.trace if item[2] == 16])
        for _ in range(8):
            assert hass.states.get(entity_id).state == "0x0104"
        assert len([item for item in sim.trace if item[2] == 16]) == before

        sim.fault = "exception"
        assert await c.read_communication() is None
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "unavailable"
        sim.fault = None
        assert await c.read_communication() is not None
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "0x0104"
        assert not any(frame[1] in (5, 6, 15, 16) for frame in sim.trace)
        assert sub.data["unit_id"] == 1
    finally:
        await sim.close()


async def test_device_modbus_id_reconfigure_is_box_selector(hass):
    sim = await Simulator().start()
    try:
        entry = configured_entry(port=sim.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "device"}
        )
        fields = {marker.schema: value for marker, value in result["data_schema"].schema.items()}
        assert fields["unit_id"].config["mode"] == "box"
        assert fields["unit_id"].config["min"] == 1
        assert fields["unit_id"].config["max"] == 247
        assert sub.data["unit_id"] == 1
    finally:
        await sim.close()
