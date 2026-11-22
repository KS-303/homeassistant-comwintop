"""b24: timestamped Modbus timeout diagnostics and status debounce."""

import asyncio
import logging
import time
from unittest.mock import AsyncMock

import pytest

from custom_components.comwintop.coordinator import UnitCoordinator

from .test_l50 import Unit, configured_entry


@pytest.fixture
async def unit_pair(hass):
    channels = {f"temperature_{channel}": {"enabled": channel <= 2} for channel in range(1, 33)}
    entry = configured_entry(channels=channels, intervals={"temperature": 30})
    unit = Unit()
    sub = next(iter(entry.subentries.values()))
    coordinator = UnitCoordinator(
        hass,
        entry,
        sub,
        unit,
        asyncio.Lock(),
        logging.getLogger("test"),
    )
    yield coordinator, unit
    await coordinator.stop()


def due(coordinator):
    for key in ("temperature_1", "temperature_2"):
        coordinator._next[key] = 0


async def test_first_timeout_keeps_fresh_temperature_status_online(unit_pair):
    coordinator, unit = unit_pair
    await coordinator._poll_one(time.monotonic())
    assert coordinator.status == "ONLINE"
    assert coordinator.available("temperature_1")
    old = coordinator.samples["temperature_1"].value

    due(coordinator)
    unit.read_holding_registers = AsyncMock(side_effect=TimeoutError())
    await coordinator._poll_one(time.monotonic())
    assert coordinator.counters["timeout"] == 1
    assert coordinator.status == "ONLINE"
    assert coordinator.samples["temperature_1"].value == old
    assert coordinator.available("temperature_1")
    assert coordinator.samples["temperature_1"].consecutive_read_failures == 1
    event = coordinator.timeout_history[0]
    assert event["register_group"] == "temperature"
    assert event["modbus_address"] == coordinator.settings["unit_id"]
    assert event["start_register"] == 32
    assert event["register_count"] == 2
    assert event["state"] == "pending"
    assert event["recovery_seconds"] is None
    assert "_started_monotonic" not in event

    due(coordinator)
    unit.read_holding_registers.side_effect = None
    unit.read_holding_registers.return_value = [231, 232]
    await coordinator._poll_one(time.monotonic())
    event = coordinator.timeout_history[0]
    assert coordinator.status == "ONLINE"
    assert event["state"] == "recovered"
    assert event["recovered_at_utc"] is not None
    assert isinstance(event["recovery_seconds"], float)
    assert event["recovery_seconds"] >= 0
    assert coordinator.counters["timeout"] == 1


async def test_stale_sample_forces_suspect_even_after_single_timeout(unit_pair):
    coordinator, unit = unit_pair
    await coordinator._poll_one(time.monotonic())
    sample = coordinator.samples["temperature_1"]
    sample.received -= 91
    coordinator._refresh_read_status()
    assert coordinator.status == "SUSPECT"
    assert not coordinator.available("temperature_1")


async def test_no_prior_answer_remains_suspect_after_first_timeout(unit_pair):
    coordinator, unit = unit_pair
    unit.read_holding_registers = AsyncMock(side_effect=TimeoutError())
    await coordinator._poll_one(time.monotonic())
    assert coordinator.status == "SUSPECT"
    assert all(sample.received is None for sample in coordinator.samples.values())


async def test_three_failed_reads_still_mark_device_offline(unit_pair):
    coordinator, unit = unit_pair
    await coordinator._poll_one(time.monotonic())
    unit.read_holding_registers = AsyncMock(side_effect=TimeoutError())
    for _ in range(3):
        due(coordinator)
        await coordinator._poll_one(time.monotonic())
    assert coordinator.status == "OFFLINE"
    assert not coordinator.available("temperature_1")
    assert len(coordinator.timeout_history) == 3


async def test_timeout_history_is_bounded_and_has_no_gateway_or_measurements(unit_pair):
    coordinator, unit = unit_pair
    for _ in range(70):
        coordinator.record_timeout("temperature", 32, 2)
    assert len(coordinator.timeout_history) == 64
    event = coordinator.timeout_history[-1]
    assert set(event) == {
        "timestamp_utc",
        "modbus_address",
        "register_group",
        "start_register",
        "register_count",
        "error",
        "recovered_at_utc",
        "recovery_seconds",
        "state",
    }
    assert event["timestamp_utc"].endswith("+00:00")


async def test_timeout_recovery_requires_matching_register_range(unit_pair):
    coordinator, _unit = unit_pair
    coordinator.record_timeout("temperature", 32, 2)
    coordinator.complete_timeouts("communication", 16, 1)
    coordinator.complete_timeouts("temperature", 33, 1)
    assert coordinator.timeout_history[0]["state"] == "pending"
    coordinator.complete_timeouts("temperature", 32, 2)
    assert coordinator.timeout_history[0]["state"] == "recovered"


async def test_communication_register_timeout_and_recovery_are_distinct(unit_pair):
    coordinator, unit = unit_pair
    unit.read_holding_registers = AsyncMock(side_effect=TimeoutError())
    assert await coordinator.read_communication() is None
    event = coordinator.timeout_history[0]
    assert event["register_group"] == "communication"
    assert event["start_register"] == 16
    assert event["state"] == "pending"
    # Address/config register 16: a valid fresh register response.
    unit.read_holding_registers.side_effect = None
    unit.read_holding_registers.return_value = [0x0104]
    await coordinator.read_communication()
    assert coordinator.timeout_history[0]["state"] == "recovered"


async def test_latched_bus_cannot_be_presented_as_recovered(unit_pair):
    coordinator, unit = unit_pair
    coordinator.record_timeout("temperature", 32, 2)
    coordinator.mark_bus_unsafe()
    coordinator.complete_timeouts("temperature", 32, 2)
    assert coordinator.status == "OFFLINE"
    assert coordinator.timeout_history[0]["state"] == "bus_latched"


async def test_poll_supervisor_crash_cannot_be_hidden_by_aging(unit_pair):
    coordinator, _unit = unit_pair
    await coordinator._poll_one(time.monotonic())
    assert coordinator.status == "ONLINE"
    sample = coordinator.samples["temperature_1"]
    sample.fail("poll_task_failed", invalidate=True)
    coordinator._refresh_read_status()
    assert coordinator.status == "OFFLINE"
    sample.accept(22, 220, time.monotonic())
    coordinator._refresh_read_status()
    assert coordinator.status == "ONLINE"
