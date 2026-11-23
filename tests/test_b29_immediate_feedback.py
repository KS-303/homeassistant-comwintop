"""b29: authenticated readback must publish immediately, no queued relay toggles."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.comwintop.coordinator import UnitCoordinator
from custom_components.comwintop.model import Sample
from custom_components.comwintop.write_manager import WriteManager, WriteRejected


class Guard:
    async def settle(self):
        return None

    def latch(self, _reason):
        raise AssertionError("valid acknowledged FC05/FC01 must not latch bus")


def make_coordinator(*, readback=True):
    coordinator = object.__new__(UnitCoordinator)
    coordinator.bus_lock = asyncio.Lock()
    coordinator.rtu_guard = Guard()
    coordinator.unit = SimpleNamespace(read_coils=AsyncMock(return_value=[readback]))
    coordinator.samples = {"do_1": Sample()}
    coordinator.last_response = None
    coordinator._refresh_read_status = lambda: None
    updates = []
    coordinator.async_set_updated_data = lambda samples: updates.append(samples["do_1"].value)
    return coordinator, updates


async def test_confirmed_fc01_immediately_updates_cached_and_reported_state(monkeypatch):
    recorded = []

    async def send_once(_unit, address, value, guard):
        guard()
        recorded.append((address, value))
        return value

    monkeypatch.setattr("custom_components.comwintop.coordinator.fc05_once", send_once)
    coordinator, updates = make_coordinator(readback=True)

    assert await coordinator._execute_do("do_1", True, lambda: None) is True
    assert recorded == [(0, True)]
    assert coordinator.samples["do_1"].value is True
    assert coordinator.samples["do_1"].received is not None
    assert coordinator.samples["do_1"].raw is True
    assert coordinator.last_response is not None
    assert updates[0] is True
    assert coordinator.last_write_phase == "confirmed"
    assert coordinator.unit.read_coils.await_count == 1


async def test_actual_mismatching_readback_is_published_but_command_rejected(monkeypatch):
    calls = []

    async def send_once(_unit, _address, _value, guard):
        guard()
        calls.append("fc05")

    monkeypatch.setattr("custom_components.comwintop.coordinator.fc05_once", send_once)
    coordinator, updates = make_coordinator(readback=False)
    manager = WriteManager(coordinator._execute_do, lambda _key: True)

    with pytest.raises(WriteRejected, match="readback_mismatch"):
        await manager.submit("do_1", True)
    assert coordinator.samples["do_1"].value is False
    assert updates[0] is False
    assert "do_1" in manager.blocked
    assert calls == ["fc05"]
    assert coordinator.unit.read_coils.await_count == 1
    await manager.close()


async def test_fast_second_click_has_clear_german_home_assistant_error():
    busy = asyncio.Event()
    release = asyncio.Event()

    async def execute(_key, value, guard):
        guard()
        busy.set()
        await release.wait()
        return value

    coordinator = object.__new__(UnitCoordinator)
    coordinator.hass = SimpleNamespace(config=SimpleNamespace(language="de"))
    coordinator._write_manager = WriteManager(execute, lambda _key: True)

    first = asyncio.create_task(coordinator.async_set_output("do_1", True))
    await busy.wait()
    with pytest.raises(HomeAssistantError, match="Schaltvorgang läuft bereits"):
        await coordinator.async_set_output("do_1", False)
    release.set()
    assert await first is True
    await coordinator._write_manager.close()
