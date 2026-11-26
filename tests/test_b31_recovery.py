"""Opt-in relay recovery regression tests."""

from collections import Counter
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.comwintop.coordinator import UnitCoordinator
from custom_components.comwintop.model import Sample
from custom_components.comwintop.recovery import RecoveryStore, recovery_targets
from custom_components.comwintop.write_manager import WriteManager


def test_targets_require_transport_and_permission():
    settings = {
        "model": "mb_307d_ii_s",
        "channels": {
            "do_1": {"write_enabled": True, "recovery_state": "off"},
            "do_2": {"write_enabled": True, "recovery_state": "on"},
            "do_3": {"write_enabled": False, "recovery_state": "on"},
            "do_4": {"write_enabled": True},
            "do_5": {"enabled": False, "write_enabled": True, "recovery_state": "off"},
        },
    }
    assert recovery_targets({"transport": "rtu_tcp"}, settings) == {
        "do_1": False,
        "do_2": True,
    }
    assert not recovery_targets({"transport": "tcp"}, settings)
    assert not recovery_targets({"transport": "rtu_tcp"}, settings | {"model": "mb_308n"})


def make_unit(*, readback=False):
    unit = object.__new__(UnitCoordinator)
    unit._recovery_pending = True
    unit._recovery_failed = False
    unit._recovery_since = 10
    unit.status = "ONLINE"
    unit._recovery_targets = lambda: {"do_1": False}
    unit.samples = {"do_1": Sample(value=True, received=11)}
    unit._can_write = lambda _key, **_kwargs: True
    unit._write_manager = WriteManager(AsyncMock(), lambda _key: True)
    unit._write_manager.communication_lost()
    unit._recovery_store = SimpleNamespace(save=AsyncMock())
    unit._execute_do = AsyncMock(return_value=readback)
    unit.rtu_guard = SimpleNamespace(unsafe=False, latch=Mock())
    unit._logger = Mock()
    unit.counters = Counter()
    unit.async_set_updated_data = Mock()
    return unit


async def test_no_write_until_fresh_then_once():
    unit = make_unit()
    unit.samples["do_1"].received = 9
    await unit._maybe_recover_outputs()
    unit._execute_do.assert_not_awaited()
    unit.samples["do_1"].received = 11
    await unit._maybe_recover_outputs()
    await unit._maybe_recover_outputs()
    assert unit._execute_do.await_count == 1
    assert unit._execute_do.await_args.args[:2] == ("do_1", False)
    unit._recovery_store.save.assert_awaited_once_with(False)
    assert not unit._write_manager.uncertain
    assert unit.recovery_phase == "confirmed"


async def test_already_matching_target_no_fc05():
    unit = make_unit()
    unit.samples["do_1"].value = False
    await unit._maybe_recover_outputs()
    unit._execute_do.assert_not_awaited()
    assert unit.recovery_phase == "confirmed"


async def test_mismatch_stays_locked_no_retry():
    unit = make_unit(readback=True)
    await unit._maybe_recover_outputs()
    await unit._maybe_recover_outputs()
    assert unit._execute_do.await_count == 1
    assert unit._write_manager.uncertain
    assert unit.recovery_phase == "failed"
    unit.rtu_guard.latch.assert_called_once_with("relay_recovery_failed")
    unit._recovery_store.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_marker_survives_new_store_instance(hass):
    entry = SimpleNamespace(
        entry_id="test-entry",
        data={"transport": "rtu_tcp", "host": "localhost", "port": 502},
    )
    sub = SimpleNamespace(data={"device_uid": "test-device", "unit_id": 3})
    store = RecoveryStore(hass, entry, sub)
    assert await store.load() is None
    await store.save(True)
    assert await RecoveryStore(hass, entry, sub).load() is True
    await store.save(False)
    assert await RecoveryStore(hass, entry, sub).load() is False
