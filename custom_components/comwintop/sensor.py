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
        for key, group, index in channels(coordinator.model):
            if group.kind not in ("di", "do"):
                entities.append(ValueSensor(coordinator, key, group, index))
            entities.append(RawSensor(coordinator, key, group, index))
        async_add_entities(entities, config_subentry_id=sub_id)


class ValueSensor(ChannelEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, key, group, index):
        super().__init__(coordinator, key, group, index)
        options = coordinator.options(key)
        if group.kind == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_suggested_display_precision = 1
        elif options.get("mode") in MODES:
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
        self._attr_name += " raw"
        self._attr_entity_registry_enabled_default = False

    @property
    def available(self):
        sample = self.coordinator.samples[self.key]
        # Raw diagnostic can show a sentinel/unknown encoding received NOW.
        timestamp = getattr(sample, "raw_received", None)
        return (
            self.coordinator.enabled(self.key)
            and timestamp is not None
            and time.monotonic() - timestamp < 3 * self.coordinator.intervals[self.group.kind]
        )

    @property
    def native_value(self):
        value = self.coordinator.samples[self.key].raw
        return int(value) if isinstance(value, bool) else value


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
            "latency_ms": self.coordinator.latency_ms,
            **self.coordinator.counters,
        }
