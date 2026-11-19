"""b22 hardening regressions: signed temperatures, unload, endpoint, build."""

import asyncio
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.comwintop import async_unload_entry
from custom_components.comwintop.config_flow import detected_tm32ds_channels
from custom_components.comwintop.model import validate_device
from custom_components.comwintop.profiles import InvalidValue, decode_channel, decode_temperature
from custom_components.comwintop.transport import endpoint_key
from scripts import build_package

from .test_l50 import configured_entry


@pytest.mark.parametrize(
    "raw,expected",
    [(0xFFFF, -0.1), (0xFFF6, -1.0), (0xFDDA, -55.0), (0, 0), (0x04E2, 125)],
)
def test_negative_temperature_requires_explicit_channel_opt_in(raw, expected):
    if raw >= 0x8000:
        with pytest.raises(InvalidValue):
            decode_temperature(raw)
    assert decode_temperature(raw, allow_negative=True) == expected
    assert decode_channel("temperature", raw, {"allow_negative": True}) == expected


@pytest.mark.parametrize("raw", [0xFDD9, 0xFC18, 0x04E3, 850, 65536])
def test_temperature_boundaries_and_sentinel_remain_invalid(raw):
    with pytest.raises(InvalidValue):
        decode_temperature(raw, allow_negative=True)


def test_temperature_channel_option_type_is_validated():
    entry = configured_entry()
    data = dict(next(iter(entry.subentries.values())).data)
    data["channels"] = {"temperature_1": {"allow_negative": "yes"}}
    with pytest.raises(InvalidValue):
        validate_device(data)


def test_zero_and_85_scan_are_explicitly_ambiguous_not_sensor_fault():
    frames = [[213] * 32 for _ in range(3)]
    frames[1][0] = frames[2][0] = 0
    frames[1][1] = frames[2][1] = 850
    result = detected_tm32ds_channels(frames)
    assert result["temperature_1"]["detection_state"] == "ambiguous"
    assert result["temperature_2"]["detection_state"] == "ambiguous"
    assert result["temperature_1"]["enabled"] is False


async def test_failed_platform_unload_preserves_runtime_and_guard():
    coordinator = SimpleNamespace(stop=AsyncMock())
    guard = SimpleNamespace(close=AsyncMock())
    entry = SimpleNamespace(runtime_data=SimpleNamespace(units={"a": coordinator}, rtu_guard=guard))
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_unload_platforms=AsyncMock(return_value=False))
    )
    assert await async_unload_entry(hass, entry) is False
    coordinator.stop.assert_not_awaited()
    guard.close.assert_not_awaited()


def test_endpoint_hostname_and_ipv6_normalization():
    plain = {"transport": "tcp_gateway", "host": "Example.Local", "port": 1502}
    assert endpoint_key(plain) == endpoint_key(plain | {"host": "example.local."})
    assert endpoint_key(plain | {"host": "[2001:0DB8::1]"}) == endpoint_key(
        plain | {"host": "2001:db8:0:0:0:0:0:1"}
    )


def test_stored_zip_build_is_bytewise_repeatable(tmp_path, monkeypatch):
    from shutil import copytree

    source = Path(__file__).resolve().parents[1] / "custom_components/comwintop"
    component = tmp_path / "custom_components/comwintop"
    copytree(source, component, ignore=lambda _folder, names: {"__pycache__"} & set(names))
    monkeypatch.setattr(build_package, "ROOT", tmp_path)
    monkeypatch.setattr(build_package, "COMPONENT", component)
    build_package.build()
    archive = next((tmp_path / "dist").glob("comwintop-*-install.zip"))
    first = hashlib.sha256(archive.read_bytes()).hexdigest()
    build_package.build()
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == first


async def test_communication_refresh_not_lost_during_read(hass):
    import logging

    from custom_components.comwintop.coordinator import UnitCoordinator

    from .test_l50 import Unit

    entry = configured_entry()
    unit = Unit()
    sub = next(iter(entry.subentries.values()))
    coordinator = UnitCoordinator(
        hass, entry, sub, unit, asyncio.Lock(), logging.getLogger("test")
    )
    coordinator.model = "tm_32ds"

    reads = 0

    async def read_with_racing_refresh():
        nonlocal reads
        reads += 1
        if reads == 1:
            coordinator._communication_refresh.set()
        return {"status": "read_only"}

    coordinator.read_communication = read_with_racing_refresh
    task = asyncio.create_task(coordinator._communication_poll())
    try:
        await asyncio.sleep(5.1)
        # A refresh raised during the first read triggers a second read.
        assert reads >= 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await coordinator.stop()
