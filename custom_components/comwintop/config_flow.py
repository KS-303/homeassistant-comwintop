"""UI connection entries, individual device subentries and channel settings."""

import asyncio
import math
from copy import deepcopy
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector
from modbus_connection.exceptions import ModbusError

from .communication import PROFILES as COMMUNICATION_PROFILES
from .communication import inspect_tm32ds, plan_tm32ds_address
from .const import DEFAULT_INTERVALS, DOMAIN, MIN_INTERVALS
from .model import revise_device, validate_device
from .profiles import (
    BUILTIN_PROFILES,
    MODEL_NAMES,
    MODES,
    PROFILES,
    channels,
    install_local_profiles,
)
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
PARITY_LABELS = {
    "de": {"N": "Keine Parität", "E": "Gerade Parität", "O": "Ungerade Parität"},
    "en": {"N": "No parity", "E": "Even parity", "O": "Odd parity"},
}


def ui_language(hass):
    return "de" if hass.config.language.lower().startswith("de") else "en"


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


async def probe(hass, connection, device):
    """Known safe read only. Success does NOT identify a model."""
    params = await hass.async_add_executor_job(params_from, dict(connection))
    group = PROFILES[device["model"]][0]
    async with async_get_temporary_unit(hass, params, device["unit_id"]) as unit:
        async with asyncio.timeout(3):
            values = await getattr(unit, group.method)(group.start, 1)
        if len(values) != 1:
            raise ValueError("invalid_length")


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
            except ValueError, KeyError:
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
            except ModbusError, TimeoutError, HomeAssistantError:
                errors["base"] = "cannot_connect"
            except ValueError, KeyError:
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
        await self.hass.async_add_executor_job(
            install_local_profiles, self.hass.config.path("comwintop")
        )
        errors = {}
        if user_input is not None:
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
                except ModbusError, TimeoutError, HomeAssistantError:
                    errors["base"] = "cannot_connect"
                except ValueError, KeyError:
                    errors["base"] = "invalid_device"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("model"): select(
                        [{"value": key, "label": name} for key, name in MODEL_NAMES.items()]
                    ),
                    vol.Required("unit_id", default=1): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=247)
                    ),
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
                except ModbusError, TimeoutError, HomeAssistantError:
                    errors["base"] = "cannot_connect"
                except ValueError, KeyError:
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
            "intervals": dict(DEFAULT_INTERVALS),
            "channels": {},
        }
        validate_device(data)
        await probe(self.hass, entry.data, data)
        return self.async_create_entry(title=data["name"], data=data, unique_id=data["device_uid"])

    async def async_step_reconfigure(self, user_input=None):
        self._sub = self._get_reconfigure_subentry()
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["device", "channel", "intervals", "communication", "address_test"],
        )

    async def async_step_communication(self, user_input=None):
        """Show a fresh bus-serialized read; never expose a write action."""
        sub = self._get_reconfigure_subentry()
        entry = self._get_entry()
        profile = COMMUNICATION_PROFILES.get(sub.data["model"])
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
        if profile is not None and profile.register is not None:
            runtime = getattr(entry, "runtime_data", None)
            coordinator = runtime.units.get(sub.subentry_id) if runtime else None
            if coordinator is not None:
                try:
                    async with runtime.bus_lock, asyncio.timeout(3):
                        words = await getattr(coordinator.unit, profile.read_method)(
                            profile.register, 1
                        )
                    if len(words) != 1:
                        raise ValueError("invalid_length")
                    values = inspect_tm32ds(words[0], sub.data["unit_id"])
                except ModbusError, TimeoutError, ValueError, OSError:
                    values["status"] = "read_failed"
        # A description-only empty form renders as a completely blank dialog
        # if HA/frontend translations are cached. Expose the actual raw data in
        # a visible read-only *workflow*: this displayed text is never persisted
        # or used as a device setting.
        report = (
            f"Modbus-ID (Gerät / HA): {values['address']} / {values['configured_address']}\\n"
            f"Register 16: {values['raw']}\\n"
            f"Baudrate: {values['baudrate']}\\n"
            f"Parität: {values['parity']}\\n"
            f"Datenbits / Stoppbits: {values['databits']} / {values['stopbits']}\\n"
            f"Status: {values['status']}"
        )
        return self.async_show_form(
            step_id="communication",
            data_schema=vol.Schema({vol.Optional("inspection", default=report): str}),
            description_placeholders=values,
        )

    async def async_step_address_test(self, user_input=None):
        """Experimental FC06 on a physically isolated TM-32DS only.

        The pinned HA backend may retransmit on Busy. This is an explicit
        laboratory exception, NOT a no-retry or production write API.
        """
        sub = self._get_reconfigure_subentry()
        entry = self._get_entry()
        if sub.data["model"] != "tm_32ds" or len(entry.subentries) != 1:
            return self.async_abort(reason="address_test_unavailable")
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None or sub.subentry_id not in runtime.units:
            return self.async_abort(reason="address_test_unavailable")

        errors = {}
        if user_input is not None:
            # Number selectors may return integral floats (e.g. 3.0).
            # The register planner deliberately accepts only genuine ints.
            target = int(user_input["target_id"])
            if not user_input["isolated"] or not user_input["understand_retry"]:
                errors["base"] = "test_acknowledgement_required"
            else:
                try:
                    async with runtime.bus_lock:
                        async with asyncio.timeout(3):
                            raw_values = await runtime.units[
                                sub.subentry_id
                            ].unit.read_holding_registers(16, 1)
                        if len(raw_values) != 1:
                            raise ValueError("invalid_length")
                        raw = raw_values[0]
                        proposed = plan_tm32ds_address(
                            raw,
                            sub.data["unit_id"],
                            target,
                            configured_ids=tuple(
                                other.data["unit_id"] for other in entry.subentries.values()
                            ),
                        )
                        # A responding target ID cannot be considered free.
                        params = await self.hass.async_add_executor_job(
                            params_from, dict(entry.data)
                        )
                        target_responded = False
                        async with async_get_temporary_unit(
                            self.hass, params, target
                        ) as target_unit:
                            try:
                                async with asyncio.timeout(1.5):
                                    test = await target_unit.read_holding_registers(16, 1)
                                target_responded = len(test) > 0
                            except ModbusError, TimeoutError, OSError:
                                pass
                        if target_responded:
                            raise ValueError("address_in_use")
                    self._address_test_plan = {
                        "raw": raw,
                        "new": proposed,
                        "old_id": sub.data["unit_id"],
                        "target_id": target,
                        "sub_id": sub.subentry_id,
                    }
                except ValueError:
                    errors["base"] = "address_test_invalid"
                except ModbusError, TimeoutError, OSError, HomeAssistantError:
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_address_test_confirm()
        notice = (
            "ACHTUNG: Ausschließlich EIN physisch isolierter TM-32DS am RS485-Bus! "
            "Der HA-Modbus-Unterbau kann FC06 bei Busy mehrfach senden. "
            "Ohne zwei Bestätigungen wird nicht geschrieben."
        )
        return self.async_show_form(
            step_id="address_test",
            data_schema=vol.Schema(
                {
                    vol.Optional("lab_notice", default=notice): str,
                    vol.Required("target_id"): unit_id_box(),
                    vol.Required("isolated", default=False): bool,
                    vol.Required("understand_retry", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_address_test_confirm(self, user_input=None):
        """Exactly one application write call, then read-only verification."""
        sub = self._get_reconfigure_subentry()
        entry = self._get_entry()
        plan = getattr(self, "_address_test_plan", None)
        runtime = getattr(entry, "runtime_data", None)
        if (
            plan is None
            or runtime is None
            or len(entry.subentries) != 1
            or sub.subentry_id != plan["sub_id"]
            or sub.data["model"] != "tm_32ds"
            or sub.data["unit_id"] != plan["old_id"]
        ):
            return self.async_abort(reason="address_test_unavailable")

        if user_input is not None:
            if not user_input["confirm"]:
                return self.async_abort(reason="address_test_cancelled")
            # Invalidate the confirmation immediately: even an ambiguous
            # response must never permit a second write in the same flow.
            self._address_test_plan = None
            target = plan["target_id"]
            try:
                async with runtime.bus_lock:
                    old_unit = runtime.units[sub.subentry_id].unit
                    async with asyncio.timeout(3):
                        fresh = await old_unit.read_holding_registers(16, 1)
                    if len(fresh) != 1 or fresh[0] != plan["raw"]:
                        return self.async_abort(reason="address_test_changed")
                    params = await self.hass.async_add_executor_job(params_from, dict(entry.data))
                    # The installed upstream API MAY retry internally on Busy.
                    # Never use this path on a populated/multidrop bus.
                    try:
                        async with asyncio.timeout(4):
                            await old_unit.write_register(16, plan["new"])
                    except ModbusError, TimeoutError, OSError:
                        pass  # The device may have changed ID despite lost reply.
                    async with async_get_temporary_unit(self.hass, params, target) as target_unit:
                        async with asyncio.timeout(3):
                            new_raw = await target_unit.read_holding_registers(16, 1)
                        async with asyncio.timeout(3):
                            temperature = await target_unit.read_holding_registers(32, 1)
                    if new_raw != [plan["new"]] or len(temperature) != 1:
                        return self.async_abort(reason="address_test_unconfirmed")
                # Preserve stable subentry/device identifiers and channel options.
                new_data = dict(sub.data) | {"unit_id": target}
                return self.async_update_and_abort(entry, sub, title=sub.title, data=new_data)
            except ModbusError, TimeoutError, OSError, HomeAssistantError, ValueError:
                return self.async_abort(reason="address_test_unconfirmed")

        preview = (
            f"ACHTUNG: Nur isolierter TM-32DS! HA kann FC06 bei Busy mehrfach senden. "
            f"Adresse {plan['old_id']} -> {plan['target_id']}; "
            f"Register 16: 0x{plan['raw']:04X} -> 0x{plan['new']:04X}. "
            "Ein fehlender Reply bedeutet keinen bestätigten Schreibfehler."
        )
        return self.async_show_form(
            step_id="address_test_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional("write_preview", default=preview): str,
                    vol.Required("confirm", default=False): bool,
                }
            ),
            description_placeholders={
                "old_id": str(plan["old_id"]),
                "target_id": str(plan["target_id"]),
                "old_raw": f"0x{plan['raw']:04X}",
                "new_raw": f"0x{plan['new']:04X}",
            },
        )

    async def async_step_device(self, user_input=None):
        sub = self._get_reconfigure_subentry()
        entry = self._get_entry()
        errors = {}
        if user_input is not None:
            if any(
                s.subentry_id != sub.subentry_id and s.data["unit_id"] == user_input["unit_id"]
                for s in entry.subentries.values()
            ):
                errors["base"] = "duplicate_unit"
            else:
                data = revise_device(dict(sub.data), dict(sub.data) | user_input)
                try:
                    await probe(self.hass, entry.data, data)
                except ModbusError, TimeoutError, HomeAssistantError, ValueError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_and_abort(entry, sub, title=data["name"], data=data)
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=sub.title): str,
                    vol.Required("unit_id", default=sub.data["unit_id"]): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=247)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_intervals(self, user_input=None):
        sub = self._get_reconfigure_subentry()
        kinds = [g.kind for g in PROFILES[sub.data["model"]]]
        if user_input is not None:
            data = dict(sub.data) | {"intervals": dict(sub.data.get("intervals", {})) | user_input}
            validate_device(data)
            return self.async_update_and_abort(self._get_entry(), sub, data=data)
        return self.async_show_form(
            step_id="intervals",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        kind,
                        default=sub.data.get("intervals", {}).get(kind, DEFAULT_INTERVALS[kind]),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVALS[kind], max=3600))
                    for kind in kinds
                }
            ),
        )

    async def async_step_channel(self, user_input=None):
        sub = self._get_reconfigure_subentry()
        if user_input is not None:
            self._channel = user_input["channel"]
            return await self.async_step_channel_settings()
        model = sub.data["model"]
        labels = CHANNEL_LABELS[ui_language(self.hass)]
        channel_selector = select(
            [
                {"value": key, "label": f"{labels[group.kind]} {index + 1}"}
                for key, group, index in channels(model)
            ]
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
        errors = {}
        if user_input is not None:
            data = deepcopy(dict(sub.data))
            selected = dict(user_input)
            mode = selected.pop("poll_interval_mode")
            if mode == "standard":
                selected.pop("poll_interval", None)
            elif mode != "individual" or selected.get("poll_interval") is None:
                errors["base"] = "invalid_interval"
            elif type(selected["poll_interval"]) is not int:
                errors["base"] = "invalid_interval"
            channel_options = dict(options) | selected
            if mode == "standard":
                channel_options.pop("poll_interval", None)
            data.setdefault("channels", {})[key] = channel_options
            try:
                data = revise_device(dict(sub.data), data)
            except ValueError, KeyError:
                errors["base"] = (
                    "invalid_interval" if "poll_interval" in selected else "invalid_channel"
                )
            else:
                if not errors:
                    return self.async_update_and_abort(self._get_entry(), sub, data=data)
        labels = {
            "de": {
                "standard": "Standard (Gruppenintervall übernehmen)",
                "individual": "Individuell",
            },
            "en": {"standard": "Default (inherit group interval)", "individual": "Individual"},
        }
        fields = {
            vol.Optional("name", default=options.get("name", "")): str,
            vol.Required("enabled", default=options.get("enabled", True)): bool,
            vol.Required(
                "poll_interval_mode",
                default="individual" if options.get("poll_interval") is not None else "standard",
            ): select(labeled_options(("standard", "individual"), labels[ui_language(self.hass)])),
            vol.Optional(
                "poll_interval",
                **(
                    {"default": options["poll_interval"]}
                    if options.get("poll_interval") is not None
                    else {}
                ),
            ): vol.All(
                integral_seconds,
                vol.Range(min=MIN_INTERVALS[kind], max=3600),
            ),
        }
        if kind == "di":
            fields[vol.Required("nc", default=options.get("nc", False))] = bool
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
