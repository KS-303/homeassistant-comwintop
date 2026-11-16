"""L-51 safe inspection: no configuration write is reachable."""

import asyncio

import pytest
from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.exceptions import ModbusError
from modbus_connection.tmodbus import ModbusConnection

from custom_components.comwintop.communication import (
    PROFILES,
    inspect_tm32ds,
    plan_tm32ds_address,
)

from .test_l50 import configured_entry
from .wire import Simulator


def test_profile_is_read_only_and_undocumented_model_is_locked():
    assert PROFILES["tm_32ds"].register == 16
    assert PROFILES["tm_32ds"].write_function == 6
    assert not PROFILES["tm_32ds"].write_enabled
    assert PROFILES["mb_308n"].register is None
    assert not PROFILES["mb_308n"].write_enabled


@pytest.mark.parametrize("raw,address", [(0x0104, "1"), (0x0204, "2")])
def test_observed_register_decode(raw, address):
    result = inspect_tm32ds(raw, 1)
    assert result["address"] == address
    assert result["raw"] == f"0x{raw:04X}"
    assert (result["baudrate"], result["parity"], result["databits"], result["stopbits"]) == (
        "9600",
        "N",
        "8",
        "1",
    )


def test_unknown_bits_not_guessed():
    assert inspect_tm32ds(0x0266, 1)["baudrate"] == "?"


def test_address_preview_preserves_every_low_bit():
    for low in range(256):
        assert plan_tm32ds_address(0x0100 | low, 1, 2) == 0x0200 | low


@pytest.mark.parametrize(
    "raw,current,target,others",
    [
        (0x0104, 1, 0, ()),
        (0x0104, 1, 248, ()),
        (0x0104, 2, 3, ()),
        (0x0104, 1, 2, (2,)),
        (0x0104, 1, 1, ()),
        (0x0104, 1, True, ()),
    ],
)
def test_address_preview_rejects_invalid_or_known_conflict(raw, current, target, others):
    with pytest.raises(ValueError):
        plan_tm32ds_address(raw, current, target, others)


@pytest.mark.parametrize("mode", ["tcp", "rtu"])
async def test_upstream_fc06_busy_retransmits_and_cannot_be_used_for_l51a(mode):
    """Wire evidence from pinned backend; deliberately NOT a production write."""
    sim = await Simulator(mode).start()
    sim.fault = "busy"
    params = (
        ModbusTcpParams(host="127.0.0.1", port=sim.port)
        if mode == "tcp"
        else ModbusSerialParams(device=f"socket://127.0.0.1:{sim.port}", baudrate=9600)
    )
    conn = ModbusConnection(params, timeout=0.1)
    try:
        with pytest.raises((TimeoutError, ModbusError)):
            async with asyncio.timeout(1.3):
                await conn.for_unit(1).write_register(16, 0x0204)
        assert len([call for call in sim.trace if call[1] == 6]) >= 2
        assert not PROFILES["tm_32ds"].write_enabled
    finally:
        await conn.close()
        await sim.close()


@pytest.mark.parametrize("mode", ["tcp", "rtu"])
@pytest.mark.parametrize("fault", ["silent", "truncated"])
async def test_fc06_timeout_or_disconnect_does_not_queue_later_write(mode, fault):
    sim = await Simulator(mode).start()
    sim.fault = fault
    params = (
        ModbusTcpParams(host="127.0.0.1", port=sim.port)
        if mode == "tcp"
        else ModbusSerialParams(device=f"socket://127.0.0.1:{sim.port}", baudrate=9600)
    )
    conn = ModbusConnection(params, timeout=0.1)
    try:
        with pytest.raises((TimeoutError, ModbusError)):
            async with asyncio.timeout(0.7):
                await conn.for_unit(1).write_register(16, 0x0204)
        initial = len([call for call in sim.trace if call[1] == 6])
        assert initial == 1
        sim.fault = None
        await conn.for_unit(1).read_holding_registers(32, 1)
        assert len([call for call in sim.trace if call[1] == 6]) == initial
    finally:
        await conn.close()
        await sim.close()


async def test_ha_inspection_reads_once_and_never_writes(hass):
    sim = await Simulator().start()
    try:
        sim.registers[1, 16] = 0x0104
        entry = configured_entry(port=sim.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        assert "communication" in flow["menu_options"]
        flow = await hass.config_entries.subentries.async_configure(
            flow["flow_id"], {"next_step_id": "communication"}
        )
        assert flow["step_id"] == "communication"
        markers = {marker.schema: marker for marker in flow["data_schema"].schema}
        selectors = {marker.schema: value for marker, value in flow["data_schema"].schema.items()}
        assert set(markers) == {
            "address",
            "configured_address",
            "raw",
            "baudrate",
            "parity",
            "databits",
            "stopbits",
            "status",
        }
        expected = {
            "address": "1",
            "configured_address": "1",
            "raw": "0x0104",
            "baudrate": "9600",
            "parity": "N",
            "databits": "8",
            "stopbits": "1",
            "status": "read_only",
        }
        assert {key: marker.default() for key, marker in markers.items()} == expected
        assert all(selector.config["read_only"] is True for selector in selectors.values())
        assert (1, 3, 16, 1) in sim.trace
        assert all(call[1] in (1, 2, 3, 4) for call in sim.trace)
        assert sub.data["unit_id"] == 1
    finally:
        await sim.close()


@pytest.mark.parametrize("fault", ["busy", "silent", "truncated"])
async def test_inspection_fault_and_recovery_never_emit_fc06(hass, fault):
    sim = await Simulator().start()
    try:
        sim.registers[1, 16] = 0x0104
        entry = configured_entry(port=sim.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))

        async def inspect():
            flow = await hass.config_entries.subentries.async_init(
                (entry.entry_id, "device"),
                context={"source": "reconfigure", "subentry_id": sub.subentry_id},
            )
            return await hass.config_entries.subentries.async_configure(
                flow["flow_id"], {"next_step_id": "communication"}
            )

        sim.fault = fault
        result = await inspect()
        fields = {marker.schema: marker.default() for marker in result["data_schema"].schema}
        assert fields["status"] == "read_failed"
        sim.fault = None
        result = await inspect()
        fields = {marker.schema: marker.default() for marker in result["data_schema"].schema}
        assert fields["raw"] == "0x0104"
        assert sub.data["unit_id"] == 1
        assert not [call for call in sim.trace if call[1] == 6]
    finally:
        await sim.close()


async def test_ha_reload_after_inspection_has_no_deferred_write(hass):
    sim = await Simulator().start()
    try:
        sim.registers[1, 16] = 0x0104
        entry = configured_entry(port=sim.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        await hass.config_entries.subentries.async_configure(
            flow["flow_id"], {"next_step_id": "communication"}
        )
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert not [call for call in sim.trace if call[1] in (5, 6, 15, 16)]
        assert sub.data["unit_id"] == 1
    finally:
        await sim.close()


async def test_communication_entity_shows_decoded_address_and_preserves_raw(hass):
    """User-facing entity shows Slave ID 2, not opaque 0x0204; reads only."""
    from homeassistant.helpers import entity_registry as er

    sim = await Simulator().start()
    try:
        sim.registers[1, 16] = 0x0204
        entry = configured_entry(port=sim.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        coordinator = next(iter(entry.runtime_data.units.values()))
        details = await coordinator.read_communication()
        assert details["address"] == "2"
        await hass.async_block_till_done()
        entity_id = er.async_get(hass).async_get_entity_id(
            "sensor", "comwintop", f"{coordinator.uid}_communication_register"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "2"
        assert state.attributes["register_16_raw"] == "0x0204"
        assert state.attributes["address_matches_configuration"] is False
        assert coordinator.settings["unit_id"] == 1
        assert not [call for call in sim.trace if call[1] not in (1, 2, 3, 4)]
    finally:
        await sim.close()
