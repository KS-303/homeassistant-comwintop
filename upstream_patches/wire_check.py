"""Run explicitly with patched upstream packages on PYTHONPATH, never in HA."""

import asyncio
import struct
from unittest.mock import patch

import modbus_connection.pymodbus as pymodbus_backend
from modbus_connection import ModbusSerialParams, ModbusTcpParams
from modbus_connection.exceptions import ModbusError
from modbus_connection.pymodbus import ModbusConnection as PymodbusConnection
from modbus_connection.tmodbus import ModbusConnection

from tests.wire import Simulator


class Wire(Simulator):
    def pdu(self, unit, data):
        if data[0] in (15, 16):
            address, count = struct.unpack(">HH", data[1:5])
            self.trace.append((unit, data[0], address, count))
            return data[:5]
        return super().pdu(unit, data)


async def exercise(mode, fc, fault):
    sim = await Wire(mode).start()
    sim.fault = fault
    params = (
        ModbusTcpParams(host="127.0.0.1", port=sim.port)
        if mode == "tcp"
        else ModbusSerialParams(device=f"socket://127.0.0.1:{sim.port}", baudrate=9600)
    )
    connection = ModbusConnection(params, timeout=0.1)
    unit = connection.for_unit(1)
    operations = {
        5: lambda: unit.write_coil(2, True, retry=False),
        6: lambda: unit.write_register(16, 0x0204, retry=False),
        15: lambda: unit.write_coils(2, [True, False], retry=False),
        16: lambda: unit.write_registers(16, [0x0204], retry=False),
    }
    try:
        if fault is None:
            await operations[fc]()
        else:
            try:
                await operations[fc]()
            except (ModbusError, TimeoutError):
                pass
            else:
                raise AssertionError((mode, fc, fault, "expected failure"))
        assert len([r for r in sim.trace if r[1] == fc]) == 1, (mode, fc, fault, sim.trace)
        sim.fault = None
        assert await unit.read_holding_registers(32, 1) == [200]
        assert len([r for r in sim.trace if r[1] == fc]) == 1
    finally:
        await connection.close()
        await sim.close()


async def concurrent_read(mode):
    sim = await Wire(mode).start()
    params = (
        ModbusTcpParams(host="127.0.0.1", port=sim.port)
        if mode == "tcp"
        else ModbusSerialParams(device=f"socket://127.0.0.1:{sim.port}", baudrate=9600)
    )
    connection = ModbusConnection(params, timeout=0.1)
    try:
        unit = connection.for_unit(1)
        await asyncio.gather(
            unit.read_holding_registers(32, 1),
            unit.write_register(16, 0x0204, retry=False),
            connection.for_unit(2).read_holding_registers(0, 1),
        )
        assert len([r for r in sim.trace if r[1] == 6]) == 1
        assert len(sim.trace) == 3
    finally:
        await connection.close()
        await sim.close()


async def legacy_busy_retry_still_exists():
    sim = await Wire().start()
    sim.fault = "busy"
    connection = ModbusConnection(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.1)
    try:
        try:
            async with asyncio.timeout(1.4):
                await connection.for_unit(1).write_register(16, 0x0204)
        except (ModbusError, TimeoutError):
            pass
        assert len([r for r in sim.trace if r[1] == 6]) >= 2
    finally:
        await connection.close()
        await sim.close()


async def cancelled_write_never_replays(backend):
    sim = await Wire().start()
    sim.fault = "silent"
    cls = ModbusConnection if backend == "tmodbus" else PymodbusConnection
    connection = cls(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=1)
    try:
        unit = connection.for_unit(1)
        task = asyncio.create_task(unit.write_register(16, 0x0204, retry=False))
        async with asyncio.timeout(1):
            while not [r for r in sim.trace if r[1] == 6]:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, ModbusError):
            pass
        else:
            raise AssertionError("write was not cancelled")
        await connection.close()  # release the HA-owned connection on unload
        sim.fault = None
        fresh = cls(ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.3)
        try:
            assert await fresh.for_unit(1).read_holding_registers(32, 1) == [200]
        finally:
            await fresh.close()
        assert len([r for r in sim.trace if r[1] == 6]) == 1
    finally:
        await connection.close()
        await sim.close()


async def pymodbus_config_change_fails_closed():
    """Simulate a future adapter constructor with retries enabled."""
    sim = await Wire().start()
    real_client = pymodbus_backend.AsyncModbusTcpClient

    def future_client(*args, **kwargs):
        return real_client(*args, **(kwargs | {"retries": 2}))

    try:
        with patch.object(pymodbus_backend, "AsyncModbusTcpClient", side_effect=future_client):
            connection = PymodbusConnection(ModbusTcpParams(host="127.0.0.1", port=sim.port))
            try:
                unit = connection.for_unit(1)
                operations = (
                    unit.write_coil(2, True, retry=False),
                    unit.write_register(16, 0x0204, retry=False),
                    unit.write_coils(2, [True, False], retry=False),
                    unit.write_registers(16, [0x0204], retry=False),
                )
                for operation in operations:
                    try:
                        await operation
                    except ModbusError as err:
                        assert "single-attempt" in str(err)
                    else:
                        raise AssertionError("retrying pymodbus client accepted no-retry write")
                assert not [r for r in sim.trace if r[1] in (5, 6, 15, 16)]
                assert await unit.read_holding_registers(32, 1) == [200]
            finally:
                await connection.close()
    finally:
        await sim.close()


async def main():
    for mode in ("tcp", "rtu"):
        for fc in (5, 6, 15, 16) if mode == "tcp" else (5, 6):
            for fault in (None, "busy", "silent", "truncated"):
                await exercise(mode, fc, fault)
        await concurrent_read(mode)
    await legacy_busy_retry_still_exists()
    for backend in ("tmodbus", "pymodbus"):
        await cancelled_write_never_replays(backend)
    await pymodbus_config_change_fails_closed()
    print("30 wire scenarios passed: no-retry, fail-closed, cancellation and legacy behavior")


if __name__ == "__main__":
    asyncio.run(main())
