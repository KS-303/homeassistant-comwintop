"""Wire checks for an isolated tmodbus RTU quarantine prototype, not production."""

import asyncio
import math
import os
import pty
import struct
import time
import tty

from serialx import create_serial_connection
from tmodbus.exceptions import ModbusConnectionError
from tmodbus.pdu.holding_registers import ReadHoldingRegistersPDU
from tmodbus.transport.async_rtu import ModbusRtuProtocol

from tests.wire import crc


async def scenario(*, continuous=False, cancel=False):
    trace = []
    tasks = []

    async def server(reader, writer):
        async def send(value):
            packet = bytes([1, 3, 2]) + struct.pack(">H", value)
            writer.write(packet + crc(packet))
            await writer.drain()

        async def delayed():
            await asyncio.sleep(0.15)
            await send(111)
            if continuous:
                for _ in range(5):
                    await asyncio.sleep(0.05)
                    await send(111)

        try:
            while True:
                frame = await reader.readexactly(8)
                unit, fc, address, count = struct.unpack(">BBHH", frame[:6])
                assert frame[-2:] == crc(frame[:-2])
                trace.append((unit, fc, address, time.monotonic()))
                if len(trace) == 1:
                    tasks.append(asyncio.create_task(delayed()))
                else:
                    response = bytes([unit, 3, 2]) + struct.pack(">H", 222)
                    writer.write(response + crc(response))
                    await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            writer.close()
            await writer.wait_closed()

    server_obj = await asyncio.start_server(server, "127.0.0.1", 0)
    port = server_obj.sockets[0].getsockname()[1]
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_connection(
        lambda: ModbusRtuProtocol(on_connection_lost=lambda _err: None, timeout=0.10),
        "127.0.0.1",
        port,
    )
    protocol.configure_timeout_quarantine(max_late=0.20, quiet=0.08, max_wait=0.35)
    try:
        first = asyncio.create_task(protocol.send_and_receive(1, ReadHoldingRegistersPDU(32, 1)))
        if cancel:
            await asyncio.sleep(0.03)
            first.cancel()
        try:
            await first
        except (TimeoutError, asyncio.CancelledError):
            pass
        else:
            raise AssertionError("first request should have failed")
        started = time.monotonic()
        second = asyncio.create_task(protocol.send_and_receive(1, ReadHoldingRegistersPDU(33, 1)))
        third = asyncio.create_task(protocol.send_and_receive(2, ReadHoldingRegistersPDU(33, 1)))
        if continuous:
            for task in (second, third):
                try:
                    await task
                except ModbusConnectionError:
                    pass
                else:
                    raise AssertionError("bus must remain locked")
            assert len(trace) == 1
        else:
            assert await second == [222]
            assert await third == [222]
            assert len(trace) == 3
            assert trace[1][3] - started >= 0.19
    finally:
        transport.close()
        server_obj.close()
        await server_obj.wait_closed()


async def main():
    validation = ModbusRtuProtocol(on_connection_lost=lambda _err: None)
    for bad in (0, -1, math.inf, math.nan):
        try:
            validation.configure_timeout_quarantine(max_late=bad, quiet=0.1, max_wait=1)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid quarantine limit accepted")
    for kwargs in ({}, {"cancel": True}, {"continuous": True}):
        await scenario(**kwargs)
    await serial_scenario()
    print("3 RTU/TCP and 1 serial PTY quarantine wire scenarios passed")


async def serial_scenario():
    master, slave = pty.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    os.set_blocking(master, False)
    loop = asyncio.get_running_loop()
    frames = []
    buffer = bytearray()
    delayed = []

    def response(unit, value):
        packet = bytes([unit, 3, 2]) + struct.pack(">H", value)
        os.write(master, packet + crc(packet))

    def receive():
        buffer.extend(os.read(master, 4096))
        while len(buffer) >= 8:
            frame = bytes(buffer[:8])
            del buffer[:8]
            assert frame[-2:] == crc(frame[:-2])
            frames.append((frame[0], time.monotonic()))
            if len(frames) == 1:
                delayed.append(loop.call_later(0.15, response, 1, 111))
            else:
                response(frame[0], 222)

    loop.add_reader(master, receive)
    transport, protocol = await create_serial_connection(
        loop,
        lambda: ModbusRtuProtocol(on_connection_lost=lambda _err: None, timeout=0.10),
        url=os.ttyname(slave),
        baudrate=9600,
    )
    protocol.configure_timeout_quarantine(max_late=0.20, quiet=0.08, max_wait=0.35)
    try:
        try:
            await protocol.send_and_receive(1, ReadHoldingRegistersPDU(32, 1))
        except TimeoutError:
            pass
        else:
            raise AssertionError("expected serial timeout")
        assert await protocol.send_and_receive(1, ReadHoldingRegistersPDU(33, 1)) == [222]
        assert await protocol.send_and_receive(2, ReadHoldingRegistersPDU(33, 1)) == [222]
        assert len(frames) == 3
        assert frames[1][1] - frames[0][1] >= 0.29
    finally:
        for timer in delayed:
            timer.cancel()
        transport.close()
        loop.remove_reader(master)
        os.close(master)
        os.close(slave)


if __name__ == "__main__":
    asyncio.run(main())
