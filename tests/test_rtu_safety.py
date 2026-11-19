"""RTU uncertain-read gate: pure lifecycle and read-safety regression tests."""

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.comwintop import rtu_safety
from custom_components.comwintop.rtu_safety import RtuBusUnsafe, RtuSessionGuard


class FakeStore:
    persisted = None

    def __init__(self, hass, version, key):
        self.key = key

    async def async_load(self):
        return self.persisted

    async def async_save(self, data):
        type(self).persisted = data


class FakeUnit:
    def __init__(self):
        self.unsafe_calls = 0

    def mark_bus_unsafe(self):
        self.unsafe_calls += 1


@pytest.fixture(autouse=True)
def reset_store(monkeypatch):
    FakeStore.persisted = None
    monkeypatch.setattr(rtu_safety, "Store", FakeStore)


def guard():
    return RtuSessionGuard(None, SimpleNamespace(data={"transport": "rtu_tcp"}, entry_id="test"))


async def test_clean_session_reloads_without_manual_reset():
    first = guard()
    await first.arm()
    assert FakeStore.persisted == {"active": True}
    with first.reading():
        pass
    await first.close()
    assert FakeStore.persisted == {"active": False}
    second = guard()
    await second.arm()
    await second.close()


async def test_timeout_latches_bus_and_survives_unload_and_restart():
    first = guard()
    await first.arm()
    unit = FakeUnit()
    first.attach(unit)
    with pytest.raises(TimeoutError):
        with first.reading():
            raise TimeoutError
    assert first.unsafe and unit.unsafe_calls == 1
    with pytest.raises(RtuBusUnsafe):
        with first.reading():
            raise AssertionError("never sent")
    await first.close()
    assert FakeStore.persisted == {"active": True}
    with pytest.raises(Exception, match="Unclean or uncertain"):
        await guard().arm()


async def test_read_cancellation_latches_bus():
    first = guard()
    await first.arm()
    with pytest.raises(asyncio.CancelledError):
        with first.reading():
            raise asyncio.CancelledError
    assert first.unsafe
    await first.close()


async def test_failed_save_does_not_arm_or_transmit(monkeypatch):
    original = FakeStore.async_save

    async def broken(self, data):
        raise OSError("disk failed")

    monkeypatch.setattr(FakeStore, "async_save", broken)
    first = guard()
    with pytest.raises(OSError):
        await first.arm()
    assert not first._armed
    monkeypatch.setattr(FakeStore, "async_save", original)


async def test_inflight_session_marker_survives_simulated_process_crash():
    first = guard()
    await first.arm()
    assert FakeStore.persisted == {"active": True}
    with pytest.raises(Exception, match="Unclean or uncertain"):
        await guard().arm()


def test_tcp_transport_has_no_rtu_guard():
    first = RtuSessionGuard(None, SimpleNamespace(data={"transport": "tcp"}, entry_id="test"))
    assert not first.enabled


async def test_known_modbus_exception_does_not_latch_bus():
    from modbus_connection.exceptions import IllegalDataAddressError

    first = guard()
    await first.arm()
    with pytest.raises(IllegalDataAddressError):
        with first.reading():
            raise IllegalDataAddressError
    assert not first.unsafe
    await first.close()


async def test_real_coordinator_stops_polling_after_rtu_timeout(hass):
    """After an ambiguous timeout even a forced poll cannot emit another frame."""
    import logging
    import time
    from unittest.mock import AsyncMock

    from custom_components.comwintop.coordinator import UnitCoordinator

    from .test_l50 import Unit, configured_entry

    entry = configured_entry(transport="rtu_tcp")
    gate = RtuSessionGuard(hass, entry)
    await gate.arm()
    unit = Unit()
    sub = next(iter(entry.subentries.values()))
    c = UnitCoordinator(hass, entry, sub, unit, asyncio.Lock(), logging.getLogger("test"), gate)
    gate.attach(c)
    unit.read_holding_registers = AsyncMock(side_effect=TimeoutError())
    await c._poll_one(time.monotonic())
    assert gate.unsafe
    assert c.status == "OFFLINE"
    assert not c.available("temperature_1")
    assert all(value == float("inf") for value in c._next.values())
    await c._poll_one(time.monotonic())
    assert unit.read_holding_registers.await_count == 1
    await c.stop()
    await gate.close()
