"""Independent Modbus wire simulator: no production codecs reused."""

import asyncio
import struct
import time
from contextlib import suppress


def crc(data):
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ 0xA001 if value & 1 else value >> 1
    return struct.pack("<H", value)


class Simulator:
    def __init__(self, mode="tcp"):
        self.mode = mode
        self.trace = []
        self.trace_times = []
        self.writers = set()
        self.tasks = set()
        self.fault = None
        self.registers = {(1, i): 200 + i - 32 for i in range(32, 64)}
        self.registers.update({(2, i): 25000 for i in range(8)})
        self.bits = {}
        self.silent_units = set()

    async def start(self):
        self.server = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def close(self):
        self.server.close()
        self.server.close_clients()
        for writer in tuple(self.writers):
            writer.close()
        tasks = tuple(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.server.wait_closed()

    def pdu(self, unit, data):
        fc = data[0]
        address, count = struct.unpack(">HH", data[1:5])
        self.trace.append((unit, fc, address, count))
        self.trace_times.append(time.monotonic())
        if fc in (3, 4):
            values = [self.registers.get((unit, i), 0) for i in range(address, address + count)]
            return bytes([fc, count * 2]) + struct.pack(">" + "H" * count, *values)
        if fc in (1, 2):
            out = bytearray((count + 7) // 8)
            for i in range(count):
                if self.bits.get((unit, address + i), False):
                    out[i // 8] |= 1 << (i % 8)
            return bytes([fc, len(out)]) + out
        if fc in (5, 6):
            if fc == 5:
                self.bits[(unit, address)] = count == 0xFF00
            else:
                self.registers[(unit, address)] = count
            return data
        return bytes([fc | 0x80, 1])

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.writers.add(writer)
        try:
            while True:
                if self.mode == "tcp":
                    header = await reader.readexactly(7)
                    tid, protocol, length, unit = struct.unpack(">HHHB", header)
                    data = await reader.readexactly(length - 1)
                else:
                    frame = await reader.readexactly(8)
                    if crc(frame[:-2]) != frame[-2:]:
                        continue
                    unit = frame[0]
                    data = frame[1:-2]
                response = self.pdu(unit, data)
                if unit in self.silent_units or self.fault == "silent":
                    continue
                if self.fault == "exception":
                    response = bytes([data[0] | 0x80, 2])
                if self.fault == "busy":
                    response = bytes([data[0] | 0x80, 6])
                if self.fault == "wrong_fc":
                    response = bytes([4 if data[0] == 3 else 3]) + response[1:]
                if self.mode == "tcp":
                    packet = (
                        struct.pack(
                            ">HHHB",
                            tid + 1 if self.fault == "wrong_tid" else tid,
                            1 if self.fault == "wrong_protocol" else 0,
                            len(response) + 1,
                            unit + 1 if self.fault == "wrong_unit" else unit,
                        )
                        + response
                    )
                else:
                    packet = bytes([unit]) + response
                    packet += crc(packet)
                    if self.fault == "crc":
                        packet = packet[:-1] + bytes([packet[-1] ^ 0xFF])
                if self.fault == "truncated":
                    writer.write(packet[:4])
                    await writer.drain()
                    writer.close()
                    return
                if self.fault == "fragmented":
                    for byte in packet:
                        writer.write(bytes([byte]))
                        await writer.drain()
                        await asyncio.sleep(0.001)
                else:
                    writer.write(packet)
                    await writer.drain()
        except asyncio.IncompleteReadError, ConnectionError, asyncio.CancelledError:
            pass
        finally:
            self.tasks.discard(task)
            self.writers.discard(writer)
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
