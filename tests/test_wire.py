import asyncio

import pytest
from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.exceptions import ModbusError
from modbus_connection.tmodbus import ModbusConnection

from custom_components.comwintop.const import BUS_MESSAGE_SPACING

from .wire import Simulator


@pytest.fixture
async def sim():
    s = await Simulator().start()
    yield s
    await s.close()


@pytest.mark.parametrize("fault", [None, "fragmented"])
async def test_real_tcp_stack_reads_full_block(sim, fault):
    sim.fault = fault
    c = ModbusConnection(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.3)
    try:
        assert await c.for_unit(1).read_holding_registers(32, 32) == list(range(200, 232))
    finally:
        await c.close()


@pytest.mark.parametrize(
    "fault",
    ["wrong_tid", "wrong_unit", "wrong_protocol", "wrong_fc", "truncated", "exception", "silent"],
)
async def test_corrupt_or_wrong_reply_never_accepted(sim, fault):
    sim.fault = fault
    c = ModbusConnection(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.1)
    try:
        with pytest.raises(ModbusError):
            await c.for_unit(1).read_holding_registers(32, 1)
    finally:
        await c.close()


@pytest.mark.parametrize("fault", ["silent"])
async def test_actual_backend_never_repeats_write(sim, fault):
    sim.fault = fault
    c = ModbusConnection(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.1)
    try:
        with pytest.raises(ModbusError):
            await c.for_unit(2).write_coil(0, True)
        await asyncio.sleep(0.15)
        assert [r for r in sim.trace if r[1] == 5] == [(2, 5, 0, 0xFF00)]
    finally:
        await c.close()


async def test_unit_failure_does_not_poison_other_unit(sim):
    sim.silent_units.add(2)
    c = ModbusConnection(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.1)
    try:
        with pytest.raises(ModbusError):
            await c.for_unit(2).read_coils(0, 8)
        assert await c.for_unit(1).read_holding_registers(32, 1) == [200]
    finally:
        await c.close()


@pytest.mark.parametrize("mode", ["tcp", "rtu"])
async def test_shared_link_waits_one_second_after_reply_across_units(mode):
    """Measure actual received-to-next-sent gap, not only configured timeout."""
    sim = await Simulator(mode).start()
    params = (
        ModbusTcpParams(host="127.0.0.1", port=sim.port)
        if mode == "tcp"
        else ModbusSerialParams(device=f"socket://127.0.0.1:{sim.port}", baudrate=9600)
    )
    c = ModbusConnection(params, timeout=0.3)
    try:
        first, second = c.for_unit(1), c.for_unit(2)
        first.set_message_spacing(BUS_MESSAGE_SPACING)
        second.set_message_spacing(BUS_MESSAGE_SPACING)
        await first.read_holding_registers(32, 2)
        await second.read_holding_registers(0, 1)
        assert sim.trace_times[1] - sim.reply_times[0] >= BUS_MESSAGE_SPACING - 0.03
        assert len(sim.trace) == 2
    finally:
        await c.close()
        await sim.close()


@pytest.mark.parametrize("mode", ["tcp", "rtu"])
async def test_shared_link_waits_after_unanswered_request(mode):
    sim = await Simulator(mode).start()
    params = (
        ModbusTcpParams(host="127.0.0.1", port=sim.port)
        if mode == "tcp"
        else ModbusSerialParams(device=f"socket://127.0.0.1:{sim.port}", baudrate=9600)
    )
    c = ModbusConnection(params, timeout=0.1)
    try:
        first, second = c.for_unit(1), c.for_unit(2)
        first.set_message_spacing(BUS_MESSAGE_SPACING)
        second.set_message_spacing(BUS_MESSAGE_SPACING)
        sim.silent_units.add(1)
        with pytest.raises(ModbusError):
            await first.read_holding_registers(32, 1)
        returned = asyncio.get_running_loop().time()
        await second.read_holding_registers(0, 1)
        assert sim.trace_times[1] - returned >= BUS_MESSAGE_SPACING - 0.03
        assert len(sim.trace) == 2
    finally:
        await c.close()
        await sim.close()


@pytest.mark.parametrize("fault", [None, "crc"])
async def test_actual_rtu_over_tcp_stack(fault):
    s = await Simulator("rtu").start()
    s.fault = fault
    c = ModbusConnection(
        ModbusSerialParams(device=f"socket://127.0.0.1:{s.port}", baudrate=9600), timeout=0.1
    )
    try:
        if fault:
            with pytest.raises(ModbusError):
                await c.for_unit(1).read_holding_registers(32, 1)
        else:
            assert await c.for_unit(1).read_holding_registers(32, 1) == [200]
    finally:
        await c.close()
        await s.close()


async def test_upstream_busy_retry_hazard_is_blocked_in_beta(sim):
    # Regression evidence: HA's pinned stack repeats FC05 on busy responses.
    # This is intentionally NOT a write-release test; beta exposes no outputs.
    from custom_components.comwintop.const import HARDWARE_VALIDATED_WRITES

    sim.fault = "busy"
    c = ModbusConnection(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.1)
    try:
        with pytest.raises((TimeoutError, ModbusError)):
            async with asyncio.timeout(1.3):
                await c.for_unit(2).write_coil(0, True)
        assert len([r for r in sim.trace if r[1] == 5]) >= 2
        assert not HARDWARE_VALIDATED_WRITES
    finally:
        await c.close()
