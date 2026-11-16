import asyncio
import logging
from unittest.mock import AsyncMock

import pytest
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTimeoutError,
)

from custom_components.comwintop.coordinator import UnitCoordinator
from custom_components.comwintop.profiles import PROFILES

from .test_ha import make_entry


class FakeUnit:
    connected = True

    def on_connection_lost(self, cb):
        return lambda: None

    def set_message_spacing(self, n):
        pass

    def require_timeout(self, n):
        pass

    def require_connect_delay(self, n):
        pass

    disconnect = AsyncMock()


@pytest.fixture
async def quality(hass):
    class Link:
        port = 15020

    entry = make_entry(Link())
    sub = next(iter(entry.subentries.values()))
    unit = FakeUnit()
    unit.read_holding_registers = AsyncMock(return_value=[220] * 32)
    coordinator = UnitCoordinator(hass, entry, sub, unit, asyncio.Lock(), logging.getLogger("test"))
    yield coordinator, unit
    await coordinator.stop()


async def test_single_timeout_preserves_value_but_three_failures_offline(quality):
    c, u = quality
    g = PROFILES["tm_32ds"][0]
    await c.poll_group(g)
    stamp = c.samples["temperature_1"].received
    u.read_holding_registers.side_effect = ModbusTimeoutError("timeout")
    await c.poll_group(g)
    assert c.status == "SUSPECT" and c.available("temperature_1")
    assert c.samples["temperature_1"].received == stamp
    await c.poll_group(g)
    await c.poll_group(g)
    assert c.status == "OFFLINE" and not c.available("temperature_1")
    u.read_holding_registers.side_effect = None
    await c.poll_group(g)
    assert c.status == "ONLINE" and c.available("temperature_1")


async def test_transport_error_invalidates_every_channel_immediately(quality):
    c, u = quality
    g = PROFILES["tm_32ds"][0]
    await c.poll_group(g)
    u.read_holding_registers.side_effect = ModbusConnectionError("private host should not export")
    await c.poll_group(g)
    assert c.status == "OFFLINE"
    assert all(not c.available(key) for key in c.samples)
    assert all(s.error == "transport_lost" for s in c.samples.values())


async def test_register_exception_splits_once_per_poll(quality):
    c, u = quality
    g = PROFILES["tm_32ds"][0]
    u.read_holding_registers.side_effect = IllegalDataAddressError()
    await c.poll_group(g)
    assert u.read_holding_registers.call_count == 1
    assert [(offset, len(keys)) for _, offset, keys in c._pending] == [(0, 16), (16, 16)]
    assert not c.available("temperature_1")
    # One half succeeds; the other half is still invalid. No full-device failure.
    u.read_holding_registers.side_effect = None
    u.read_holding_registers.return_value = [230] * 16
    await c.poll_group(g)
    assert c.available("temperature_1") and not c.available("temperature_32")


async def test_disabled_group_never_polled(quality):
    c, u = quality
    g = PROFILES["tm_32ds"][0]
    c.settings["channels"] = {key: {"enabled": False} for key in c.samples}
    await c.poll_group(g)
    u.read_holding_registers.assert_not_called()


async def test_short_response_not_accepted(quality):
    c, u = quality
    u.read_holding_registers.return_value = [220]
    await c.poll_group(PROFILES["tm_32ds"][0])
    assert c.status == "SUSPECT" and c.counters["protocol_error"] == 1
    assert all(s.received is None for s in c.samples.values())


async def test_unexpected_error_remains_diagnostic(quality):
    c, u = quality
    u.read_holding_registers.side_effect = RuntimeError("private data")
    await c.poll_group(PROFILES["tm_32ds"][0])
    assert c.samples["temperature_1"].error == "RuntimeError"
    assert c.counters["unexpected_errors"] == 1
