"""Independent PTY wire tests; run with patched packages on PYTHONPATH."""

import asyncio
import os
import pty
import struct
import tty

from modbus_connection import ModbusSerialParams
from modbus_connection.exceptions import ModbusError
from modbus_connection.pymodbus import ModbusConnection as PymodbusConnection
from modbus_connection.tmodbus import ModbusConnection as TmodbusConnection

from tests.wire import crc


class PtyWire:
    def __init__(self, fault=None):
        self.fault = fault
        self.master, self.slave = pty.openpty()
        tty.setraw(self.master)
        tty.setraw(self.slave)
        os.set_blocking(self.master, False)
        self.path = os.ttyname(self.slave)
        self.buffer = bytearray()
        self.trace = []
        asyncio.get_running_loop().add_reader(self.master, self.readable)

    def readable(self):
        try:
            self.buffer.extend(os.read(self.master, 4096))
        except OSError:
            return
        while len(self.buffer) >= 8:
            fc = self.buffer[1]
            length = 9 + self.buffer[6] if fc in (15, 16) and len(self.buffer) >= 7 else 8
            if len(self.buffer) < length:
                return
            frame = bytes(self.buffer[:length])
            del self.buffer[:length]
            assert crc(frame[:-2]) == frame[-2:], frame
            unit, fc, address, value = struct.unpack(">BBHH", frame[:6])
            self.trace.append((unit, fc, address, value))
            if self.fault == "silent":
                continue
            if self.fault == "disconnect":
                asyncio.get_running_loop().remove_reader(self.master)
                os.close(self.master)
                self.master = None
                return
            if self.fault == "busy":
                reply = bytes((unit, fc | 0x80, 6))
            elif fc == 3:
                reply = bytes((unit, fc, value * 2)) + struct.pack(
                    ">" + "H" * value, *([42] * value)
                )
            else:
                reply = frame[:6]
            os.write(self.master, reply + crc(reply))

    def close(self):
        if self.master is not None:
            asyncio.get_running_loop().remove_reader(self.master)
            os.close(self.master)
        os.close(self.slave)


async def scenario(backend, fc, fault):
    wire = PtyWire(fault)
    cls = TmodbusConnection if backend == "tmodbus" else PymodbusConnection
    conn = cls(ModbusSerialParams(device=wire.path, baudrate=9600), timeout=0.15)
    unit = conn.for_unit(1)
    ops = {
        5: lambda: unit.write_coil(2, True, retry=False),
        6: lambda: unit.write_register(16, 0x0204, retry=False),
        15: lambda: unit.write_coils(2, [True, False], retry=False),
        16: lambda: unit.write_registers(16, [0x0204], retry=False),
    }
    try:
        if fault is None:
            await ops[fc]()
        else:
            try:
                async with asyncio.timeout(1):
                    await ops[fc]()
            except ModbusError, TimeoutError, OSError:
                pass
            else:
                raise AssertionError((backend, fc, fault, "expected failure"))
        assert len([r for r in wire.trace if r[1] == fc]) == 1, (backend, fc, fault, wire.trace)
        if fault != "disconnect":
            wire.fault = None
            assert await unit.read_holding_registers(32, 1) == [42]
            assert len([r for r in wire.trace if r[1] == fc]) == 1
    finally:
        await conn.close()
        wire.close()


async def cancelled_serial_write(backend):
    wire = PtyWire("silent")
    cls = TmodbusConnection if backend == "tmodbus" else PymodbusConnection
    params = ModbusSerialParams(device=wire.path, baudrate=9600)
    conn = cls(params, timeout=1)
    try:
        task = asyncio.create_task(conn.for_unit(1).write_register(16, 0x0204, retry=False))
        async with asyncio.timeout(1):
            while not [r for r in wire.trace if r[1] == 6]:  # noqa: ASYNC110
                await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError, ModbusError:
            pass
        else:
            raise AssertionError("write was not cancelled")
        await conn.close()
        wire.fault = None
        fresh = cls(params, timeout=0.3)
        try:
            assert await fresh.for_unit(1).read_holding_registers(32, 1) == [42]
        finally:
            await fresh.close()
        assert len([r for r in wire.trace if r[1] == 6]) == 1
    finally:
        await conn.close()
        wire.close()


async def main():
    for backend in ("tmodbus", "pymodbus"):
        for fc in (5, 6, 15, 16):
            for fault in (None, "busy", "silent", "disconnect"):
                await scenario(backend, fc, fault)
        await cancelled_serial_write(backend)
    print("34 PTY write wire scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())
