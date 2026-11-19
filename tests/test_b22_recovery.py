"""b22 lifecycle and HA Repairs regression tests."""

import asyncio

import pytest
from homeassistant.components.repairs import repairs_flow_manager
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component

from custom_components.comwintop.const import DOMAIN

from .test_ha import wait_for
from .test_l50 import configured_entry
from .wire import Simulator


@pytest.mark.asyncio
async def test_normal_hass_stop_clears_only_clean_rtu_marker(hass):
    simulator = await Simulator("rtu").start()
    try:
        entry = configured_entry(transport="rtu_tcp", port=simulator.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        assert entry.state.value == "loaded", entry.reason
        guard = entry.runtime_data.rtu_guard
        assert guard._armed
        await wait_for(lambda: any(x.samples["temperature_1"].received for x in entry.runtime_data.units.values()))
        assert (await guard._store.async_load()) == {"active": True}
        await hass.async_stop(force=True)
        assert (await guard._store.async_load()) == {"active": False}
    finally:
        await simulator.close()


@pytest.mark.asyncio
async def test_double_reload_keeps_exactly_one_shutdown_job(hass):
    simulator = await Simulator("rtu").start()
    try:
        entry = configured_entry(transport="rtu_tcp", port=simulator.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        for _ in range(2):
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            jobs = [
                job for job in hass._shutdown_jobs
                if job.job.name == f"comwintop_clean_shutdown_{entry.entry_id}"
            ]
            assert len(jobs) == 1
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await simulator.close()


@pytest.mark.asyncio
async def test_repairs_rejects_partial_confirmation_and_allows_explicit_reset(hass):
    assert await async_setup_component(hass, "repairs", {})
    marker = "comwintop.rtu_session." + ("b" * 32)
    store = Store(hass, 1, marker)
    await store.async_save({"active": True, "reason": "repeated_read_timeout"})
    issue_id = "rtu_" + ("b" * 32)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        is_persistent=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="rtu_recovery",
        data={"marker_key": marker, "reason": "repeated_read_timeout"},
        translation_placeholders={"reason": "repeated_read_timeout", "marker": marker},
    )
    manager = repairs_flow_manager(hass)
    result = await manager.async_init(DOMAIN, context={"issue_id": issue_id})
    assert result["type"] == "form"
    missing = await manager.async_configure(
        result["flow_id"],
        {
            "bus_power_cycled": True,
            "sole_master_confirmed": False,
            "gateway_queues_cleared": True,
        },
    )
    assert missing["type"] == "form"
    assert missing["errors"]["base"] == "incomplete"
    assert (await store.async_load())["active"] is True

    completed = await manager.async_configure(
        result["flow_id"],
        {
            "bus_power_cycled": True,
            "sole_master_confirmed": True,
            "gateway_queues_cleared": True,
        },
    )
    assert completed["type"] == "create_entry"
    assert (await store.async_load()) == {"active": False}


@pytest.mark.asyncio
async def test_config_scan_uses_same_guard_and_rejects_latched_bus(hass):
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.comwintop.config_flow import scan_tm32ds_channels

    simulator = await Simulator("rtu").start()
    try:
        entry = configured_entry(transport="rtu_tcp", port=simulator.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        assert entry.state.value == "loaded", entry.reason
        disabled = await scan_tm32ds_channels(hass, entry.data, 1)
        assert isinstance(disabled, dict)
        guard = entry.runtime_data.rtu_guard
        guard.latch("test_latched")
        count = len(simulator.trace)
        with pytest.raises(HomeAssistantError, match="rtu_bus_unsynchronized"):
            await scan_tm32ds_channels(hass, entry.data, 1)
        assert len(simulator.trace) == count
    finally:
        await hass.config_entries.async_unload(entry.entry_id)
        await simulator.close()
