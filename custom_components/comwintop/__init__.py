"""ComWinTop: local Modbus I/O, no plant control logic."""

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import PLATFORMS
from .coordinator import UnitCoordinator
from .model import validate_device
from .profiles import load_local_profiles, publish_local_profiles
from .transport import params_from

_LOGGER = logging.getLogger(__name__)


@dataclass
class Runtime:
    units: dict[str, UnitCoordinator]
    bus_lock: asyncio.Lock


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    local, failures = await hass.async_add_executor_job(
        load_local_profiles, hass.config.path("comwintop")
    )
    publish_local_profiles(local)
    for filename, reason in failures.items():
        _LOGGER.warning("Local ComWinTop profile %s rejected: %s", filename, reason)
    params = await hass.async_add_executor_job(params_from, dict(entry.data))
    lock = asyncio.Lock()
    coordinators = {}
    ids = set()
    forwarding_attempted = False
    try:
        for sub in entry.subentries.values():
            validate_device(sub.data)
            unit_id = sub.data["unit_id"]
            if unit_id in ids:
                raise ValueError("duplicate_unit")
            ids.add(unit_id)
            unit = async_get_unit(hass, entry, params, unit_id)
            coordinators[sub.subentry_id] = UnitCoordinator(hass, entry, sub, unit, lock, _LOGGER)
        entry.runtime_data = Runtime(coordinators, lock)
        forwarding_attempted = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        for coordinator in coordinators.values():
            await coordinator.start()
    except Exception as err:
        for coordinator in coordinators.values():
            with suppress(Exception):
                await coordinator.stop()
        if forwarding_attempted:
            with suppress(Exception):
                await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        raise ConfigEntryError("ComWinTop setup failed; resources cleaned up") from err
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    return True


async def async_update_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    # A failed platform unload must NOT leave a loaded entry with stopped polling.
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    for coordinator in entry.runtime_data.units.values():
        await coordinator.stop()
    return True
