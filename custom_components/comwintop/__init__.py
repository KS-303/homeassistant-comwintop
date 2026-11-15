"""ComWinTop: local Modbus I/O, no plant control logic."""

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import PLATFORMS
from .coordinator import UnitCoordinator
from .model import validate_device
from .transport import params_from

_LOGGER = logging.getLogger(__name__)


@dataclass
class Runtime:
    units: dict[str, UnitCoordinator]
    bus_lock: asyncio.Lock


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    params = await hass.async_add_executor_job(params_from, dict(entry.data))
    lock = asyncio.Lock()
    coordinators = {}
    ids = set()
    try:
        for sub in entry.subentries.values():
            validate_device(sub.data)
            unit_id = sub.data["unit_id"]
            if unit_id in ids:
                raise ValueError("duplicate_unit")
            ids.add(unit_id)
            unit = async_get_unit(hass, entry, params, unit_id)
            coordinators[sub.subentry_id] = UnitCoordinator(hass, entry, sub, unit, lock, _LOGGER)
    except (KeyError, ValueError) as err:
        for coordinator in coordinators.values():
            await coordinator.stop()
        raise ConfigEntryError("Invalid ComWinTop device configuration") from err
    entry.runtime_data = Runtime(coordinators, lock)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    for coordinator in coordinators.values():
        await coordinator.start()
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    return True


async def async_update_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    # Stop tasks BEFORE unloading entities/releasing shared unit holds.
    for coordinator in entry.runtime_data.units.values():
        await coordinator.stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
