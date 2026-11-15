"""Exercise the real serial backend over a Linux PTY (not USB hardware proof)."""

import asyncio
import os
import pty
import struct
import tty

from modbus_connection import ModbusSerialParams
from modbus_connection.tmodbus import ModbusConnection

from .wire import crc


async def test_real_serial_backend_on_pty():
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    os.set_blocking(master, False)
    device = os.ttyname(slave)
    received = bytearray()
    trace = []
    loop = asyncio.get_running_loop()

    def readable():
        try:
            data = os.read(master, 4096)
        except BlockingIOError:
            return
        received.extend(data)
        while len(received) >= 8:
            frame = bytes(received[:8])
            del received[:8]
            assert crc(frame[:-2]) == frame[-2:]
            unit, fc, address, count = struct.unpack(">BBHH", frame[:-2])
            trace.append((unit, fc, address, count))
            response = bytes([unit, fc, count * 2]) + struct.pack(
                ">" + "H" * count, *range(220, 220 + count)
            )
            os.write(master, response + crc(response))

    loop.add_reader(master, readable)
    c = ModbusConnection(ModbusSerialParams(device=device, baudrate=9600), timeout=0.5)
    try:
        assert await c.for_unit(1).read_holding_registers(32, 32) == list(range(220, 252))
        assert trace == [(1, 3, 32, 32)]
    finally:
        await c.close()
        loop.remove_reader(master)
        os.close(master)
        os.close(slave)
