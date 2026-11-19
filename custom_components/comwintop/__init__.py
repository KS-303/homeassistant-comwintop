"""ComWinTop: local Modbus I/O, no plant control logic."""

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from modbus_connection.exceptions import ModbusError

from .const import PLATFORMS
from .coordinator import UnitCoordinator
from .model import validate_device
from .profiles import InvalidValue, channels, load_local_profiles, publish_local_profiles
from .rtu_safety import RtuSessionGuard
from .transport import params_from

_LOGGER = logging.getLogger(__name__)


@dataclass
class Runtime:
    units: dict[str, UnitCoordinator]
    bus_lock: asyncio.Lock
    rtu_guard: RtuSessionGuard


async def _sync_disabled_channel_registry(hass, entry, coordinators):
    """Keep old entity IDs and user choices when channels are turned off/on.

    An old b13 entity must be marked disabled by this integration, otherwise
    HA lists the orphan as 'no longer provided'. Only our known channel IDs
    and our own INTEGRATION disabler are ever changed.
    """
    registry = er.async_get(hass)
    store = Store(hass, 1, f"comwintop.channel_registry.{entry.entry_id}")
    saved = await store.async_load() or {}
    owned = set(saved.get("disabled", []))
    entries = {
        (item.domain, item.unique_id): item
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.platform == entry.domain
    }
    disable = []
    enable = []
    for coordinator in coordinators.values():
        for key, group, _ in channels(coordinator.model):
            base = f"{coordinator.uid}_{key}"
            domains = (
                (("binary_sensor", base), ("sensor", f"{base}_raw"))
                if group.kind in ("di", "do")
                else (("sensor", base), ("sensor", f"{base}_raw"))
            )
            if group.kind == "temperature":
                domains += (("binary_sensor", f"{base}_probe_fault"),)
            for identity in domains:
                item = entries.get(identity)
                if item is None:
                    continue
                marker = f"{identity[0]}:{identity[1]}"
                if not coordinator.enabled(key) and item.disabled_by is None:
                    owned.add(marker)
                    disable.append(item.entity_id)
                elif (
                    coordinator.enabled(key)
                    and item.disabled_by == er.RegistryEntryDisabler.INTEGRATION
                    and (marker in owned or not identity[1].endswith("_raw"))
                ):
                    enable.append((item.entity_id, marker))
                elif item.disabled_by not in (None, er.RegistryEntryDisabler.INTEGRATION):
                    owned.discard(marker)
                elif coordinator.enabled(key) and item.disabled_by is None:
                    owned.discard(marker)
    # Persist ownership first: interrupted reloads can safely repeat the change.
    await store.async_save({"disabled": sorted(owned)})
    for entity_id in disable:
        registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    for entity_id, marker in enable:
        registry.async_update_entity(entity_id, disabled_by=None)
        owned.discard(marker)
    await store.async_save({"disabled": sorted(owned)})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Build a read-only runtime; preserve HA retries for temporary failures."""
    coordinators: dict[str, UnitCoordinator] = {}
    forwarding_attempted = False
    rtu_guard = RtuSessionGuard(hass, entry)
    try:
        local, failures = await hass.async_add_executor_job(
            load_local_profiles, hass.config.path("comwintop")
        )
        publish_local_profiles(local)
        for filename, reason in failures.items():
            _LOGGER.warning("Local ComWinTop profile %s rejected: %s", filename, reason)
        params = await hass.async_add_executor_job(params_from, dict(entry.data))
        await rtu_guard.arm()
        lock = asyncio.Lock()
        ids: set[int] = set()

        for sub in entry.subentries.values():
            validate_device(sub.data, legacy=True)
            unit_id = sub.data["unit_id"]
            if unit_id in ids:
                raise ValueError("duplicate_unit")
            ids.add(unit_id)
            unit = async_get_unit(hass, entry, params, unit_id)
            try:
                coordinator = UnitCoordinator(
                    hass, entry, sub, unit, lock, _LOGGER, rtu_guard
                )
            except (Exception, asyncio.CancelledError):
                # The unit is a handle on HA's shared Modbus connection: never
                # disconnect/close it just because this constructor failed.
                # Undo any per-unit requirements set before construction failed.
                with suppress(Exception):
                    unit.set_message_spacing(0)
                with suppress(Exception):
                    unit.require_timeout(None)
                with suppress(Exception):
                    unit.require_connect_delay(None)
                raise
            coordinators[sub.subentry_id] = coordinator
            rtu_guard.attach(coordinator)

        entry.runtime_data = Runtime(coordinators, lock, rtu_guard)
        await _sync_disabled_channel_registry(hass, entry, coordinators)
        forwarding_attempted = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        for coordinator in coordinators.values():
            await coordinator.start()
    except (Exception, asyncio.CancelledError) as err:
        for coordinator in coordinators.values():
            with suppress(Exception):
                await coordinator.stop()
        if forwarding_attempted:
            with suppress(Exception):
                await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        # A failed startup must not strand an armed marker if no transmission
        # was uncertain. close() retains it whenever the RTU guard latched.
        with suppress(Exception):
            await rtu_guard.close()
        entry.runtime_data = None

        if isinstance(err, asyncio.CancelledError):
            raise
        if isinstance(err, (ConfigEntryError, ConfigEntryNotReady)):
            raise
        if isinstance(err, (InvalidValue, ValueError, KeyError, TypeError)):
            raise ConfigEntryError("Invalid ComWinTop configuration") from err
        if isinstance(
            err, (ModbusError, TimeoutError, ConnectionError, OSError, HomeAssistantError)
        ):
            raise ConfigEntryNotReady(
                "ComWinTop Modbus service is temporarily unavailable"
            ) from err
        raise ConfigEntryError("ComWinTop setup failed") from err

    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    return True


async def async_update_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    # Keep polling alive if the platforms cannot be unloaded. A successful
    # platform unload is followed by stopping every coordinator and listener.
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False
    for coordinator in entry.runtime_data.units.values():
        await coordinator.stop()
    await entry.runtime_data.rtu_guard.close()
    return True
