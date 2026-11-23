"""Regression coverage for localized UI and pre-wire safety behavior."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.comwintop.coordinator import UnitCoordinator
from custom_components.comwintop.single_attempt import SingleAttemptUnavailable
from custom_components.comwintop.write_manager import WriteManager, WriteRejected

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "comwintop"


def _paths(value, prefix=""):
    if isinstance(value, dict):
        result = set()
        for key, part in value.items():
            result |= _paths(part, f"{prefix}.{key}" if prefix else key)
        return result
    return {prefix}


def test_full_translation_coverage_and_label_consistency():
    strings = json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))
    english = json.loads((ROOT / "translations" / "en.json").read_text(encoding="utf-8"))
    german = json.loads((ROOT / "translations" / "de.json").read_text(encoding="utf-8"))
    assert _paths(strings) == _paths(english) == _paths(german)
    for i in range(1, 9):
        key = f"do_{i}"
        assert (
            f"Ausgang {i}"
            in german["config_subentries"]["device"]["step"]["relay_permissions"]["data"][key]
        )
        assert (
            f"output {i}"
            in english["config_subentries"]["device"]["step"]["relay_permissions"]["data"][
                key
            ].lower()
        )


class DummyGuard:
    def __init__(self):
        self.latched = []
        self.settle = AsyncMock()

    def latch(self, reason):
        self.latched.append(reason)


async def test_expired_before_fc05_does_not_latch_bus(monkeypatch):
    async def reject_without_wire(_unit, _addr, _value, guard):
        guard()

    guard = DummyGuard()
    coordinator = object.__new__(UnitCoordinator)
    coordinator.bus_lock = asyncio.Lock()
    coordinator.rtu_guard = guard
    coordinator.unit = object()
    coordinator.samples = {}
    coordinator.async_set_updated_data = lambda _samples: None
    monkeypatch.setattr("custom_components.comwintop.coordinator.fc05_once", reject_without_wire)
    with pytest.raises(WriteRejected, match="expired"):
        await coordinator._execute_do(
            "do_1", True, lambda: (_ for _ in ()).throw(WriteRejected("expired"))
        )
    assert not guard.latched
    assert coordinator.last_write_phase == "rejected_before_send"


async def test_incompatible_transport_does_not_latch_bus(monkeypatch):
    async def reject_before_wire(_unit, _addr, _value, _guard):
        raise SingleAttemptUnavailable("unsupported")

    guard = DummyGuard()
    coordinator = object.__new__(UnitCoordinator)
    coordinator.bus_lock = asyncio.Lock()
    coordinator.rtu_guard = guard
    coordinator.unit = object()
    coordinator.samples = {}
    coordinator.async_set_updated_data = lambda _samples: None
    monkeypatch.setattr("custom_components.comwintop.coordinator.fc05_once", reject_before_wire)
    with pytest.raises(SingleAttemptUnavailable):
        await coordinator._execute_do("do_1", True, lambda: None)
    assert not guard.latched


async def test_unconfirmed_readback_latches_without_write_retry(monkeypatch):
    wire_calls = []

    async def sent_once(_unit, _addr, _value, guard):
        guard()
        wire_calls.append(1)

    guard = DummyGuard()
    coordinator = object.__new__(UnitCoordinator)
    coordinator.bus_lock = asyncio.Lock()
    coordinator.rtu_guard = guard
    coordinator.unit = SimpleNamespace(read_coils=AsyncMock(side_effect=TimeoutError))
    coordinator.samples = {}
    coordinator.async_set_updated_data = lambda _samples: None
    monkeypatch.setattr("custom_components.comwintop.coordinator.fc05_once", sent_once)
    with pytest.raises(TimeoutError):
        await coordinator._execute_do("do_1", True, lambda: None)
    assert wire_calls == [1]
    assert guard.latched == ["write_readback_unconfirmed"]
    assert coordinator.last_write_phase == "fc01_readback"


async def test_manager_preflight_unavailable_keeps_other_channels_usable():
    calls = []

    async def exec_command(key, value, guard):
        if key == "do_1":
            raise SingleAttemptUnavailable("version_not_supported")
        guard()
        calls.append((key, value))
        return value

    manager = WriteManager(exec_command, lambda _key: True)
    with pytest.raises(WriteRejected, match="transport_preflight_unavailable"):
        await manager.submit("do_1", True)
    assert manager.uncertain is False
    assert not manager.blocked
    assert await manager.submit("do_2", True) is True
    assert calls == [("do_2", True)]
    await manager.close()
