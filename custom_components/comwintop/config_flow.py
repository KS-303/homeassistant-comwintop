"""UI connection entries, individual device subentries and channel settings."""

import asyncio
import math
from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector
from modbus_connection.exceptions import ModbusError

from .const import (
    BUS_MESSAGE_SPACING,
    CONFIGURABLE_MIN_INTERVALS,
    DEFAULT_INTERVALS,
    DOMAIN,
    NEW_DEVICE_INTERVALS,
    READ_DEADLINE,
)
from .model import revise_device, set_temperature_range_enabled, validate_device
from .profiles import (
    BUILTIN_PROFILES,
    MODEL_NAMES,
    MODES,
    PROFILES,
    InvalidValue,
    channels,
    decode_temperature,
    load_local_profiles,
    publish_local_profiles,
)
from .rtu_safety import RtuSessionGuard
from .transport import MODES as TRANSPORTS
from .transport import endpoint_key, params_from

CHANNEL_LABELS = {
    "de": {
        "temperature": "Temperaturkanal",
        "di": "Digitaler Eingang",
        "do": "Digitaler Ausgang – Rückmeldung",
        "ai": "Analoger Eingang",
        "ao": "Analoger Ausgang – Rückmeldung",
    },
    "en": {
        "temperature": "Temperature channel",
        "di": "Digital input",
        "do": "Digital output – readback",
        "ai": "Analog input",
        "ao": "Analog output – readback",
    },
}
TRANSPORT_LABELS = {
    "de": {
        "tcp": "Modbus über Netzwerk",
        "tcp_gateway": "Modbus über Netzwerk-Seriell-Gateway",
        "rtu_tcp": "Transparente serielle Verbindung über Netzwerk",
        "serial": "Direkte serielle Verbindung",
    },
    "en": {
        "tcp": "Modbus over network",
        "tcp_gateway": "Modbus through network-to-serial gateway",
        "rtu_tcp": "Transparent serial connection over network",
        "serial": "Direct serial connection",
    },
}
SIGNAL_LABELS = {
    "de": {
        "0_10v": "0 bis 10 Volt",
        "0_5v": "0 bis 5 Volt",
        "0_20ma": "0 bis 20 Milliampere",
        "4_20ma": "4 bis 20 Milliampere",
    },
    "en": {
        "0_10v": "0 to 10 volts",
        "0_5v": "0 to 5 volts",
        "0_20ma": "0 to 20 milliamperes",
        "4_20ma": "4 to 20 milliamperes",
    },
}
DISPLAY_LABELS = {
    "de": {
        "physical": "Physikalischer Messwert",
        "percent": "Prozentwert",
        "scaled": "Skalierter Messwert",
    },
    "en": {
        "physical": "Physical measurement",
        "percent": "Percentage",
        "scaled": "Scaled measurement",
    },
}
DEVICE_MENU_LABELS = {
    "de": {
        "device": "Name / Modbus-Adresse",
        "channel": "Kanal konfigurieren",
        "intervals": "Abfrageintervalle",
        "disable_temperature_range": "Temperaturkanäle gesammelt deaktivieren",
        "enable_temperature_range": "Temperaturkanäle gesammelt aktivieren",
        "communication": "Modbus-Kommunikation anzeigen",
        "relay_permissions": "Relais-Schreibfreigaben (DO1–DO8)",
    },
    "en": {
        "device": "Name / unit address",
        "channel": "Configure channel",
        "intervals": "Polling intervals",
        "disable_temperature_range": "Disable temperature channels in bulk",
        "enable_temperature_range": "Enable temperature channels in bulk",
        "communication": "Show Modbus communication",
        "relay_permissions": "Relay write permissions (DO1–DO8)",
    },
}
PARITY_LABELS = {
    "de": {"N": "Keine Parität", "E": "Gerade Parität", "O": "Ungerade Parität"},
    "en": {"N": "No parity", "E": "Even parity", "O": "Odd parity"},
}


def ui_language(hass):
    return "de" if hass.config.language.lower().startswith("de") else "en"


def channel_label(model, kind, index, language):
    """Label the configured channel, not just its feedback entity."""
    if kind == "do":
        name = "Digitaler Ausgang" if language == "de" else "Digital output"
        suffix = " – Rückmeldung" if language == "de" else " – readback"
        return f"{name} {index + 1}" + ("" if model == "mb_307d_ii_s" else suffix)
    return f"{CHANNEL_LABELS[language][kind]} {index + 1}"


def labeled_options(values, labels):
    return [{"value": value, "label": labels[value]} for value in values]


def integral_seconds(value):
    """Reject fractional values instead of silently truncating them."""
    number = vol.Coerce(float)(value)
    if not math.isfinite(number) or not number.is_integer():
        raise vol.Invalid("invalid_interval")
    return int(number)


def select(options):
    return selector({"select": {"options": options, "mode": "dropdown"}})


def unit_id_box():
    """Display a numeric input instead of a slider with 247 positions."""
    return selector({"number": {"min": 1, "max": 247, "step": 1, "mode": "box"}})


def temperature_channel_box():
    return selector({"number": {"min": 1, "max": 32, "step": 1, "mode": "box"}})


def read_only_text():
    """Display a disabled text selector, not a writable text input."""
    return selector({"text": {"read_only": True}})


def connection_schema(mode, defaults=None, language="en"):
    defaults = defaults or {}
    fields = {vol.Required("name", default=defaults.get("name", "Modbus-Verbindung")): str}
    if mode == "serial":
        fields[vol.Required("device", default=defaults.get("device", "/dev/serial/by-id/"))] = str
    else:
        fields[vol.Required("host", default=defaults.get("host", ""))] = str
        # An explicit port is required: no misleading universal 502 default.
        port = (
            vol.Required("port", default=defaults["port"])
            if "port" in defaults
            else vol.Required("port")
        )
        fields[port] = vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
    if mode in ("serial", "rtu_tcp"):
        fields.update(
            {
                vol.Required("baudrate", default=defaults.get("baudrate", 9600)): vol.In(
                    [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
                ),
                vol.Required("parity", default=defaults.get("parity", "N")): select(
                    labeled_options(["N", "E", "O"], PARITY_LABELS[language])
                ),
                vol.Required("stopbits", default=defaults.get("stopbits", 1)): vol.In([1, 2]),
            }
        )
    return vol.Schema(fields)


@asynccontextmanager
async def guarded_temporary_unit(hass, connection, unit_id):
    """Serialize configuration probes with every loaded ComWinTop poll.

    Temporary units still use HA's common Modbus backend. This guard prevents
    our own probes from bypassing an already-latched bus or interleaving with
    another ComWinTop read. It does not protect independent HA users of the
    same physical RS485 bus (an upstream limitation).
    """
    identity = endpoint_key(connection)
    matches = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if endpoint_key(entry.data) != identity:
            continue
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None:
            matches.append(runtime)
    temporary_guard = None
    if not matches:
        # A connection reconfiguration probes the *new* endpoint before the
        # running entry has been moved. It needs an independent destination
        # marker and the original entry's fairness lock.
        sources = [
            getattr(entry, "runtime_data", None)
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("connection_uid") == connection.get("connection_uid")
        ]
        sources = [source for source in sources if source is not None]
        if len(sources) != 1:
            raise HomeAssistantError("ComWinTop connection must be loaded before probing")
        runtime = sources[0]
        if runtime.rtu_guard.unsafe:
            raise HomeAssistantError("rtu_bus_unsynchronized")
        temporary_guard = RtuSessionGuard(hass, SimpleNamespace(data=connection))
        await temporary_guard.arm()
        guard = temporary_guard
    else:
        if len(matches) != 1:
            raise HomeAssistantError("multiple_comwintop_hubs_on_same_bus")
        runtime = matches[0]
        guard = runtime.rtu_guard
        if guard.unsafe:
            raise HomeAssistantError("rtu_bus_unsynchronized")
    params = await hass.async_add_executor_job(params_from, dict(connection))
    try:
        async with runtime.bus_lock:
            await guard.settle()
            async with async_get_temporary_unit(hass, params, unit_id) as unit:
                yield unit, guard
    finally:
        if temporary_guard is not None:
            await temporary_guard.close()


async def probe(hass, connection, device):
    """Known safe read only. Success does NOT identify a model."""
    group = PROFILES[device["model"]][0]
    async with guarded_temporary_unit(hass, connection, device["unit_id"]) as (unit, guard):
        with guard.reading():
            async with asyncio.timeout(READ_DEADLINE):
                values = await getattr(unit, group.method)(group.start, 1)
            if len(values) != 1:
                raise ValueError("invalid_length")


def detected_tm32ds_channels(frames):
    """Conservatively enable only sensors confirmed by two fresh full-block reads."""
    if len(frames) != 3 or any(len(frame) != 32 for frame in frames):
        raise ValueError("invalid_scan_length")
    disabled = {}
    for index, (second, third) in enumerate(zip(frames[1], frames[2], strict=True), 1):
        # Zero can be a real 0 °C reading but is also a common empty-register
        # value. Leave it for explicit manual activation rather than guessing.
        try:
            if second == 0 or third == 0:
                raise InvalidValue("ambiguous_zero")
            decode_temperature(second)
            decode_temperature(third)
        except InvalidValue as error:
            reason = str(error)
            disabled[f"temperature_{index}"] = {
                "enabled": False,
                "detection_state": (
                    "ambiguous"
                    if reason in ("ambiguous_zero", "temperature_85_ambiguous")
                    else "invalid"
                ),
            }
    return disabled


async def scan_tm32ds_channels(hass, connection, unit_id):
    """Read FC03/32..63 through HA's shared transport; never scan slave IDs."""
    frames = []
    async with guarded_temporary_unit(hass, connection, unit_id) as (unit, guard):
        for attempt in range(3):
            await guard.settle()
            with guard.reading():
                async with asyncio.timeout(READ_DEADLINE):
                    values = await unit.read_holding_registers(32, 32)
                if len(values) != 32:
                    raise HomeAssistantError("incomplete_temperature_scan")
            frames.append(values)
            if attempt < 2:
                await asyncio.sleep(BUS_MESSAGE_SPACING)
    return detected_tm32ds_channels(frames)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry):
        return {"device": DeviceFlow}

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._transport = user_input["transport"]
            return await self.async_step_connection()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("transport"): select(
                        labeled_options(TRANSPORTS, TRANSPORT_LABELS[ui_language(self.hass)])
                    )
                }
            ),
        )

    async def async_step_connection(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = dict(user_input, transport=self._transport)
            try:
                key = await self.hass.async_add_executor_job(endpoint_key, data)
                await self.async_set_unique_id(key)
                self._abort_if_unique_id_configured()
            except (ValueError, KeyError):
                errors["base"] = "invalid_connection"
            else:
                data["connection_uid"] = str(uuid4())
                return self.async_create_entry(title=data["name"], data=data)
        return self.async_show_form(
            step_id="connection",
            data_schema=connection_schema(self._transport, user_input, ui_language(self.hass)),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            data = dict(entry.data) | user_input
            try:
                key = await self.hass.async_add_executor_job(endpoint_key, data)
                for other in self._async_current_entries():
                    if other.entry_id != entry.entry_id and other.unique_id == key:
                        raise ValueError("duplicate_connection")
                # Check each configured unit at the destination BEFORE changing it.
                for sub in entry.subentries.values():
                    await probe(self.hass, data, sub.data)
            except (ModbusError, TimeoutError, HomeAssistantError):
                errors["base"] = "cannot_connect"
            except (ValueError, KeyError):
                errors["base"] = "invalid_connection"
            else:
                for sub in entry.subentries.values():
                    settings = deepcopy(dict(sub.data))
                    for options in settings.get("channels", {}).values():
                        options["write_enabled"] = False
                    self.hass.config_entries.async_update_subentry(entry, sub, data=settings)
                self.hass.config_entries.async_update_entry(
                    entry, data=data, title=data["name"], unique_id=key
                )
                return self.async_abort(reason="reconfigure_successful")
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=connection_schema(
                entry.data["transport"], entry.data, ui_language(self.hass)
            ),
            errors=errors,
        )


class DeviceFlow(config_entries.ConfigSubentryFlow):
    async def async_step_user(self, user_input=None):
        local, _failures = await self.hass.async_add_executor_job(
            load_local_profiles, self.hass.config.path("comwintop")
        )
        publish_local_profiles(local)
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input["unit_id"] = int(user_input["unit_id"])
            entry = self._get_entry()
            if any(s.data["unit_id"] == user_input["unit_id"] for s in entry.subentries.values()):
                errors["base"] = "duplicate_unit"
            elif not user_input.get("acknowledge_beta"):
                errors["base"] = "acknowledge_required"
            elif user_input["model"] not in BUILTIN_PROFILES:
                self._pending_device = {
                    key: value for key, value in user_input.items() if key != "acknowledge_beta"
                }
                self._preview_groups = tuple(PROFILES[self._pending_device["model"]])
                return await self.async_step_profile_preview()
            else:
                data = {
                    key: value for key, value in user_input.items() if key != "acknowledge_beta"
                }
                try:
                    return await self._create_device(data)
                except (ModbusError, TimeoutError, HomeAssistantError):
                    errors["base"] = "cannot_connect"
                except (ValueError, KeyError):
                    errors["base"] = "invalid_device"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("model"): select(
                        [{"value": key, "label": name} for key, name in MODEL_NAMES.items()]
                    ),
                    vol.Required("unit_id", default=1): unit_id_box(),
                    vol.Required("acknowledge_beta", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_profile_preview(self, user_input=None):
        data = self._pending_device
        groups = self._preview_groups
        errors = {}
        if user_input is not None:
            if not user_input["confirm"] or tuple(PROFILES.get(data["model"], ())) != groups:
                errors["base"] = "invalid_device"
            else:
                try:
                    return await self._create_device(data)
                except (ModbusError, TimeoutError, HomeAssistantError):
                    errors["base"] = "cannot_connect"
                except (ValueError, KeyError):
                    errors["base"] = "invalid_device"
        return self.async_show_form(
            step_id="profile_preview",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            errors=errors,
            description_placeholders={
                "model": MODEL_NAMES[data["model"]],
                "reads": "; ".join(
                    f"{group.kind}: {group.method} {group.start}–{group.start + group.count - 1}"
                    for group in groups
                ),
            },
        )

    async def _create_device(self, data):
        entry = self._get_entry()
        if any(s.data["unit_id"] == data["unit_id"] for s in entry.subentries.values()):
            raise ValueError("duplicate_unit")
        data = dict(data)
        data |= {
            "device_uid": str(uuid4()),
            "connection_uid": entry.data["connection_uid"],
            "intervals": {
                group.kind: NEW_DEVICE_INTERVALS[group.kind] for group in PROFILES[data["model"]]
            },
            "channels": {},
        }
        validate_device(data)
        if data["model"] == "tm_32ds":
            data["channels"] = await scan_tm32ds_channels(self.hass, entry.data, data["unit_id"])
        else:
            await probe(self.hass, entry.data, data)
        validate_device(data)
        return self.async_create_entry(title=data["name"], data=data, unique_id=data["device_uid"])

    async def async_step_reconfigure(self, user_input=None):
        self._sub = self._get_reconfigure_subentry()
        options = ["device", "channel", "intervals"]
        if self._sub.data["model"] == "mb_307d_ii_s":
            options.append("relay_permissions")
        if self._sub.data["model"] == "tm_32ds":
            options.extend(("disable_temperature_range", "enable_temperature_range"))
        options.append("communication")
        labels = DEVICE_MENU_LABELS[ui_language(self.hass)]
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options={option: labels[option] for option in options},
        )

    async def async_step_relay_permissions(self, user_input=None):
        """One-screen explicit per-relay enablement; no Modbus write in this flow."""
        sub = self._get_reconfigure_subentry()
        entry = self._get_entry()
        if sub.data["model"] != "mb_307d_ii_s":
            return self.async_abort(reason="write_permissions_unavailable")
        errors = {}
        if user_input is not None:
            language = ui_language(self.hass)
            selected = {
                f"do_{index}": user_input.get(
                    f"Ausgang {index} (DO{index - 1}) – Schalten erlauben"
                    if language == "de"
                    else f"Output {index} (DO{index - 1}) – Allow switching",
                    False,
                )
                is True
                for index in range(1, 9)
            }
            previous = dict(sub.data)
            updated = deepcopy(previous)
            for key, permitted in selected.items():
                updated.setdefault("channels", {}).setdefault(key, {})["write_enabled"] = permitted
            try:
                validated = revise_device(previous, updated)
            except (ValueError, KeyError):
                errors["base"] = "invalid_channel"
            else:
                return self.async_update_and_abort(entry, sub, data=validated)
        # Use localized field IDs for this one-screen permission dialog.
        # Home Assistant sometimes fails to resolve dynamic subentry data
        # translations and otherwise displays raw "do_1" .. "do_8".
        # These IDs are UI-only: persisted channel keys remain stable do_N.
        language = ui_language(self.hass)
        permission_labels = {
            (
                f"Ausgang {index} (DO{index - 1}) – Schalten erlauben"
                if language == "de"
                else f"Output {index} (DO{index - 1}) – Allow switching"
            ): f"do_{index}"
            for index in range(1, 9)
        }
        fields = {
            vol.Required(
                label,
                default=sub.data.get("channels", {}).get(key, {}).get("write_enabled", False),
            ): bool
            for label, key in permission_labels.items()
        }
        return self.async_show_form(
            step_id="relay_permissions",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    async def _temperature_range_form(self, step_id, enabled, user_input):
        """Explicit user selection only; never turn on a channel based on a guess."""
        sub = self._get_reconfigure_subentry()
        if sub.data["model"] != "tm_32ds":
            return self.async_abort(reason="bulk_disable_unavailable")
        errors = {}
        if user_input is not None:
            if not user_input["confirm"]:
                errors["base"] = "bulk_confirmation_required"
            else:
                try:
                    first = integral_seconds(user_input["first"])
                    last = integral_seconds(user_input["last"])
                    updated = set_temperature_range_enabled(dict(sub.data), first, last, enabled)
                except (ValueError, vol.Invalid):
                    errors["base"] = "invalid_channel_range"
                else:
                    return self.async_update_and_abort(self._get_entry(), sub, data=updated)
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required("first", default=3): temperature_channel_box(),
                    vol.Required("last", default=32): temperature_channel_box(),
                    vol.Required("confirm", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_disable_temperature_range(self, user_input=None):
        return await self._temperature_range_form("disable_temperature_range", False, user_input)

    async def async_step_enable_temperature_range(self, user_input=None):
        return await self._temperature_range_form("enable_temperature_range", True, user_input)

    async def async_step_communication(self, user_input=None):
        """Read fresh register 16 and show each value in its own locked field."""
        sub = self._get_reconfigure_subentry()
        entry = self._get_entry()
        values = {
            "address": "?",
            "configured_address": str(sub.data["unit_id"]),
            "baudrate": "?",
            "parity": "?",
            "databits": "?",
            "stopbits": "?",
            "raw": "?",
            "status": "unsupported",
        }
        runtime = getattr(entry, "runtime_data", None)
        coordinator = runtime.units.get(sub.subentry_id) if runtime else None
        if coordinator is not None and sub.data["model"] == "tm_32ds":
            current = await coordinator.read_communication()
            if current is not None:
                values = current
            else:
                values["status"] = "read_failed"

        fields = {
            vol.Optional(key, default=values[key]): read_only_text()
            for key in (
                "address",
                "configured_address",
                "raw",
                "baudrate",
                "parity",
                "databits",
                "stopbits",
                "status",
            )
        }
        return self.async_show_form(
            step_id="communication",
            data_schema=vol.Schema(fields),
        )

    async def async_step_address_test(self, user_input=None):
        """Legacy deep links fail closed; FC06 is not available in this beta."""
        return self.async_abort(reason="address_test_unavailable")

    async def async_step_address_test_confirm(self, user_input=None):
        """Previously opened lab confirmations cannot transmit after an update."""
        return self.async_abort(reason="address_test_unavailable")

    async def async_step_device(self, user_input=None):
        sub = self._get_reconfigure_subentry()
        entry = self._get_entry()
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input["unit_id"] = int(user_input["unit_id"])
            if any(
                s.subentry_id != sub.subentry_id and s.data["unit_id"] == user_input["unit_id"]
                for s in entry.subentries.values()
            ):
                errors["base"] = "duplicate_unit"
            else:
                data = revise_device(dict(sub.data), dict(sub.data) | user_input)
                try:
                    await probe(self.hass, entry.data, data)
                except (ModbusError, TimeoutError, HomeAssistantError, ValueError):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_and_abort(entry, sub, title=data["name"], data=data)
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=sub.title): str,
                    vol.Required("unit_id", default=sub.data["unit_id"]): unit_id_box(),
                }
            ),
            errors=errors,
        )

    async def async_step_intervals(self, user_input=None):
        sub = self._get_reconfigure_subentry()
        kinds = [g.kind for g in PROFILES[sub.data["model"]]]
        old_intervals = sub.data.get("intervals", {})
        legacy = {
            kind: old_intervals.get(kind, DEFAULT_INTERVALS[kind])
            for kind in kinds
            if old_intervals.get(kind, DEFAULT_INTERVALS[kind]) < CONFIGURABLE_MIN_INTERVALS[kind]
        }
        errors = {}
        if user_input is not None:
            selected = dict(user_input)
            for kind, value in legacy.items():
                if selected.pop(f"keep_{kind}", False):
                    selected[kind] = value
            data = dict(sub.data) | {"intervals": dict(old_intervals) | selected}
            try:
                validate_device(data, previous=sub.data)
            except (ValueError, KeyError):
                errors["base"] = "invalid_interval"
            else:
                return self.async_update_and_abort(self._get_entry(), sub, data=data)
        fields = {}
        for kind in kinds:
            if kind in legacy:
                fields[vol.Required(f"keep_{kind}", default=True)] = bool
            fields[
                vol.Required(
                    kind,
                    default=max(
                        CONFIGURABLE_MIN_INTERVALS[kind],
                        old_intervals.get(kind, DEFAULT_INTERVALS[kind]),
                    ),
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=CONFIGURABLE_MIN_INTERVALS[kind], max=3600))
        return self.async_show_form(
            step_id="intervals",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={
                "legacy_intervals": ", ".join(f"{k}: {v} s" for k, v in legacy.items()) or "—"
            },
        )

    async def async_step_channel(self, user_input=None):
        sub = self._get_reconfigure_subentry()
        if user_input is not None:
            self._channel = user_input["channel"]
            return await self.async_step_channel_settings()
        model = sub.data["model"]
        language = ui_language(self.hass)
        # A labeled membership validator serializes to a native HA dropdown.
        # Values remain stable internal IDs (e.g. temperature_3), not labels.
        channel_selector = vol.In(
            {
                key: channel_label(model, group.kind, index, language)
                for key, group, index in channels(model)
            }
        )
        return self.async_show_form(
            step_id="channel",
            data_schema=vol.Schema({vol.Required("channel"): channel_selector}),
        )

    async def async_step_channel_settings(self, user_input=None):
        sub = self._get_reconfigure_subentry()
        key = self._channel
        kind = key.rsplit("_", 1)[0]
        options = sub.data.get("channels", {}).get(key, {})
        old_interval = options.get("poll_interval")
        has_legacy = old_interval is not None and old_interval < CONFIGURABLE_MIN_INTERVALS[kind]
        errors = {}
        if user_input is not None:
            data = deepcopy(dict(sub.data))
            selected = dict(user_input)
            mode = selected.pop(
                "poll_interval_mode",
                "individual" if "poll_interval" in selected else "standard",
            )
            if mode == "legacy" and has_legacy:
                mode = "individual"
                selected["poll_interval"] = old_interval
            if mode == "standard":
                if "poll_interval" in selected and options.get("poll_interval") is None:
                    errors["base"] = "choose_individual_interval"
                selected.pop("poll_interval", None)
            elif mode != "individual" or selected.get("poll_interval") is None:
                errors["base"] = "invalid_interval"
            else:
                try:
                    selected["poll_interval"] = integral_seconds(selected["poll_interval"])
                except vol.Invalid:
                    errors["base"] = "invalid_interval"
            channel_options = dict(options) | selected
            if mode == "standard":
                channel_options.pop("poll_interval", None)
            data.setdefault("channels", {})[key] = channel_options
            try:
                data = revise_device(dict(sub.data), data)
            except (ValueError, KeyError) as err:
                code = str(err)
                if code == "invalid_interval":
                    errors["base"] = code
                elif code == "invalid_scale" or (
                    channel_options.get("display") == "scaled"
                    and code in ("invalid_number", "non_finite")
                ):
                    errors["base"] = "invalid_scale"
                else:
                    errors["base"] = "invalid_channel"
            else:
                if not errors:
                    return self.async_update_and_abort(self._get_entry(), sub, data=data)
        labels = {
            "de": {
                "standard": "Standard (Gruppenintervall übernehmen)",
                "individual": "Individuell",
                "legacy": f"Bisherigen Wert beibehalten ({old_interval} Sekunden)",
            },
            "en": {
                "standard": "Default (inherit group interval)",
                "individual": "Individual",
                "legacy": f"Keep existing value ({old_interval} seconds)",
            },
        }
        fields = {
            vol.Optional("name", default=options.get("name", "")): str,
            vol.Required("enabled", default=options.get("enabled", True)): bool,
            vol.Required(
                "poll_interval_mode",
                default="legacy"
                if has_legacy
                else "individual"
                if old_interval is not None
                else "standard",
            ): select(
                labeled_options(
                    ("standard", "individual", "legacy")
                    if has_legacy
                    else ("standard", "individual"),
                    labels[ui_language(self.hass)],
                )
            ),
            vol.Optional(
                "poll_interval",
                **(
                    {"default": options["poll_interval"]}
                    if options.get("poll_interval") is not None and not has_legacy
                    else {}
                ),
            ): vol.All(
                vol.Coerce(float),
                vol.Range(min=CONFIGURABLE_MIN_INTERVALS[kind], max=3600),
            ),
        }
        if kind == "temperature":
            fields[vol.Required("allow_negative", default=options.get("allow_negative", False))] = (
                bool
            )
        if kind == "di":
            fields[vol.Required("nc", default=options.get("nc", False))] = bool
        if kind == "do" and sub.data["model"] == "mb_307d_ii_s":
            # Permission is explicit, per output, and OFF by default.
            # The transport release gate remains independent.
            fields[vol.Required("write_enabled", default=options.get("write_enabled", False))] = (
                bool
            )
            fields[
                vol.Required("recovery_state", default=options.get("recovery_state", "hold"))
            ] = select(
                labeled_options(
                    ("hold", "off", "on"),
                    {
                        "de": {
                            "hold": "Keine Zustandsvorgabe (Standard)",
                            "off": "Relais AUS",
                            "on": "Relais EIN",
                        },
                        "en": {
                            "hold": "No state override (default)",
                            "off": "Relay OFF",
                            "on": "Relay ON",
                        },
                    }[ui_language(self.hass)],
                )
            )
        if kind in ("ai", "ao"):
            fields[vol.Required("mode", default=options.get("mode", "0_10v"))] = select(
                labeled_options(MODES, SIGNAL_LABELS[ui_language(self.hass)])
            )
            fields[vol.Required("display", default=options.get("display", "physical"))] = select(
                labeled_options(
                    ["physical", "percent", "scaled"] if kind == "ai" else ["physical", "percent"],
                    DISPLAY_LABELS[ui_language(self.hass)],
                )
            )
            if kind == "ai":
                fields[vol.Optional("scale_min", default=options.get("scale_min", 0))] = vol.Coerce(
                    float
                )
                fields[vol.Optional("scale_max", default=options.get("scale_max", 100))] = (
                    vol.Coerce(float)
                )
                fields[vol.Optional("unit", default=options.get("unit", ""))] = str
        return self.async_show_form(
            step_id="channel_settings",
            data_schema=vol.Schema(fields),
            errors=errors,
            description_placeholders={"channel": key},
        )
