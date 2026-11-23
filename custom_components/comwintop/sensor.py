"""Temperature/analog readbacks and opt-in raw diagnostics."""

import time

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import ChannelEntity
from .profiles import MODEL_NAMES, MODES, channels


async def async_setup_entry(hass, entry, async_add_entities):
    for sub_id, coordinator in entry.runtime_data.units.items():
        entities = [UnitStatus(coordinator)]
        if coordinator.model == "tm_32ds":
            entities.append(CommunicationRegister(coordinator))
        for key, group, index in channels(coordinator.model):
            if not coordinator.enabled(key):
                continue
            if group.kind not in ("di", "do"):
                entities.append(ValueSensor(coordinator, key, group, index))
            entities.append(RawSensor(coordinator, key, group, index))
        async_add_entities(entities, config_subentry_id=sub_id)


class ValueSensor(ChannelEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, key, group, index):
        super().__init__(coordinator, key, group, index)
        options = coordinator.options(key)
        if coordinator.model == "mb_307d_ii_s" and group.kind == "ai":
            # The hardware signal modes are not validated; show only integer
            # register counts and make the uncertainty explicit in the name.
            self._attr_translation_key = None
            self._attr_name = (
                f"{options.get('name') or f'Analoger Eingang {index + 1}'} – Rohwert"
            )
            self._attr_native_unit_of_measurement = None
            self._attr_suggested_display_precision = 0
        if group.kind == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_suggested_display_precision = 1
        elif options.get("mode") in MODES and not (
            coordinator.model == "mb_307d_ii_s" and group.kind == "ai"
        ):
            # AO readback always stays in physical V/mA, independent of setpoint display.
            display = options.get("display", "physical") if group.kind == "ai" else "physical"
            self._attr_native_unit_of_measurement = (
                "%"
                if display == "percent"
                else options.get("unit")
                if display == "scaled"
                else MODES[options["mode"]][4]
            )
            if display == "physical":
                self._attr_device_class = (
                    SensorDeviceClass.VOLTAGE
                    if MODES[options["mode"]][4] == "V"
                    else SensorDeviceClass.CURRENT
                )

    @property
    def native_value(self):
        return self.coordinator.samples[self.key].value


class RawSensor(ChannelEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, key, group, index):
        super().__init__(coordinator, key, group, index)
        self._attr_unique_id += "_raw"
        self._attr_translation_key = f"{group.kind}_raw"
        if custom_name := coordinator.options(key).get("name"):
            language = coordinator.hass.config.language.lower()
            suffix = "Rohwert" if language.startswith("de") else "Raw value"
            self._attr_name = f"{custom_name} – {suffix}"
        self._attr_entity_registry_enabled_default = False

    @property
    def available(self):
        sample = self.coordinator.samples[self.key]
        # Raw diagnostic can show a sentinel/unknown encoding received NOW.
        timestamp = getattr(sample, "raw_received", None)
        return (
            self.coordinator.enabled(self.key)
            and timestamp is not None
            and time.monotonic() - timestamp < 3 * self.coordinator.interval(self.key)
        )

    @property
    def native_value(self):
        value = self.coordinator.samples[self.key].raw
        return int(value) if isinstance(value, bool) else value

    @property
    def extra_state_attributes(self):
        """Opt-in polling diagnostics live on the disabled-by-default raw sensor."""
        sample = self.coordinator.samples[self.key]
        return {
            "poll_interval_seconds": self.coordinator.interval(self.key),
            "successful_read_count_since_reload": sample.successful_reads,
            "last_successful_read_utc": sample.last_successful_read_utc,
            "seconds_between_successful_reads": sample.last_successful_read_delta_seconds,
            "quality": sample.error or "valid",
        }


class CommunicationRegister(CoordinatorEntity, SensorEntity):
    """Expose the device Modbus address; keep raw register 16 as a diagnostic."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "communication_register"
    _attr_should_poll = False

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.uid}_communication_register"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.uid)},
            name=coordinator.subentry.title,
            manufacturer="ComWinTop",
            model=MODEL_NAMES[coordinator.model],
        )

    @property
    def available(self):
        return self.coordinator.communication_values is not None

    @property
    def native_value(self):
        details = self.coordinator.communication_values
        return int(details["address"]) if details is not None else None

    @property
    def extra_state_attributes(self):
        details = self.coordinator.communication_values
        if details is None:
            return {"read_error": self.coordinator.communication_error}
        return {
            "device_slave_id": details["address"],
            "register_16_raw": details["raw"],
            "address_matches_configuration": details["address"] == details["configured_address"],
            "configured_slave_id": details["configured_address"],
            "baudrate": details["baudrate"],
            "parity": details["parity"],
            "data_bits": details["databits"],
            "stop_bits": details["stopbits"],
            "read_status": details["status"],
            "age_seconds": round(time.monotonic() - self.coordinator.communication_received)
            if self.coordinator.communication_received is not None
            else None,
        }


class UnitStatus(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "communication"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.uid}_communication"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.uid)},
            name=coordinator.subentry.title,
            manufacturer="ComWinTop",
            model=MODEL_NAMES[coordinator.model],
        )

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return self.coordinator.status.lower()

    @property
    def extra_state_attributes(self):
        return {
            "write_release": "hardware_validation_required",
            "transport_connected": self.coordinator.unit.connected,
            "bus_lock_wait_ms": self.coordinator.bus_lock_wait_ms,
            "read_call_ms": self.coordinator.read_call_ms,
            "minimum_read_rate_hz": self.coordinator.minimum_read_rate_hz,
            "poll_task_running": self.coordinator.poll_running,
            "seconds_since_last_response": (
                round(time.monotonic() - self.coordinator.last_response, 1)
                if self.coordinator.last_response is not None
                else None
            ),
            **self.coordinator.counters,
        }
