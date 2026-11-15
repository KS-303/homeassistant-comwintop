"""Bounded software stress test; deliberately not a hardware endurance claim."""

import asyncio

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

from .wire import Simulator


async def test_thousand_reads_and_twenty_connection_lifecycles():
    sim = await Simulator().start()
    try:
        async with asyncio.timeout(30):
            for _ in range(20):
                connection = ModbusConnection(
                    ModbusTcpParams(host="127.0.0.1", port=sim.port), timeout=0.2
                )
                try:
                    for _ in range(50):
                        assert await connection.for_unit(1).read_holding_registers(32, 32) == list(
                            range(200, 232)
                        )
                finally:
                    await connection.close()
                for _ in range(10):
                    if not sim.writers and not sim.tasks:
                        break
                    await asyncio.sleep(0.001)
                assert not sim.writers and not sim.tasks
        assert len(sim.trace) == 1000
        assert all(request[1] == 3 for request in sim.trace)
    finally:
        await sim.close()
