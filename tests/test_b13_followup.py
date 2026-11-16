"""Regression tests for review findings A-F on the read-only b13 branch."""

import asyncio
import importlib
import json
from pathlib import Path

import pytest
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady, HomeAssistantError

from custom_components.comwintop.coordinator import failed_poll_delay

from .test_ha import make_entry
from .wire import Simulator


@pytest.mark.parametrize(
    ("interval", "failures", "expected"),
    [
        (2, 0, 2),
        (2, 1, 4),
        (2, 5, 30),
        (15, 1, 30),
        (15, 5, 30),
        (30, 1, 30),
        (60, 1, 60),
        (300, 1, 300),
        (3600, 1, 3600),
        (3600, 5, 3600),
    ],
)
def test_transient_retry_never_accelerates_slow_channel(interval, failures, expected):
    assert failed_poll_delay(interval, failures) == expected


async def test_modbus_backend_not_ready_causes_ha_retry(hass, monkeypatch):
    module = importlib.import_module("custom_components.comwintop")
    sim = await Simulator().start()
    try:
        entry = make_entry(sim)

        def temporarily_missing(*args):
            raise HomeAssistantError("Backend starting")

        monkeypatch.setattr(module, "async_get_unit", temporarily_missing)
        with pytest.raises(ConfigEntryNotReady):
            await module.async_setup_entry(hass, entry)
        assert getattr(entry, "runtime_data", None) is None
    finally:
        await sim.close()


async def test_invalid_configuration_is_not_retried(hass):
    module = importlib.import_module("custom_components.comwintop")
    sim = await Simulator().start()
    try:
        entry = make_entry(sim)
        # Fail validation explicitly without mutating immutable subentry data.
        from custom_components.comwintop.profiles import InvalidValue

        original = module.validate_device

        def invalid(_):
            raise InvalidValue("invalid_scale")

        module.validate_device = invalid
        try:
            with pytest.raises(ConfigEntryError):
                await module.async_setup_entry(hass, entry)
        finally:
            module.validate_device = original
    finally:
        await sim.close()


async def test_cancelled_setup_restores_resources(hass, monkeypatch):
    module = importlib.import_module("custom_components.comwintop")
    sim = await Simulator().start()
    try:
        entry = make_entry(sim)
        created = []

        class CancelDuringConstructor:
            def __init__(self, *args, **kwargs):
                created.append(args[3])
                raise asyncio.CancelledError

        monkeypatch.setattr(module, "UnitCoordinator", CancelDuringConstructor)
        with pytest.raises(asyncio.CancelledError):
            await module.async_setup_entry(hass, entry)
        assert len(created) == 1
        assert getattr(entry, "runtime_data", None) is None
    finally:
        await sim.close()


def test_scale_key_and_removed_address_forms():
    root = Path(__file__).resolve().parents[1] / "custom_components/comwintop"
    for location in ("strings.json", "translations/de.json", "translations/en.json"):
        content = json.loads((root / location).read_text(encoding="utf-8"))
        device = content["config_subentries"]["device"]
        assert device["error"]["invalid_scale"]
        assert "address_test" not in device["step"]
        assert "address_test_confirm" not in device["step"]
        assert "address_test" not in device["step"]["reconfigure"]["menu_options"]


def test_retired_slave_id_preview_is_pure_and_has_no_write_gate():
    from custom_components.comwintop.communication import PROFILES, plan_tm32ds_address

    assert plan_tm32ds_address(0x0104, 1, 2) == 0x0204
    assert not PROFILES["tm_32ds"].write_enabled
