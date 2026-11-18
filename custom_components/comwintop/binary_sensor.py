"""Digital readbacks and independent temperature-probe diagnostics."""

import time

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import ChannelEntity
from .profiles import channels


async def async_setup_entry(hass, entry, async_add_entities):
    for sub_id, coordinator in entry.runtime_data.units.items():
        entities = []
        for key, group, index in channels(coordinator.model):
            if not coordinator.enabled(key):
                continue
            if group.kind in ("di", "do"):
                entities.append(DigitalSensor(coordinator, key, group, index))
            elif group.kind == "temperature":
                entities.append(TemperatureProbeFault(coordinator, key, group, index))
        async_add_entities(entities, config_subentry_id=sub_id)


class DigitalSensor(ChannelEntity, BinarySensorEntity):
    @property
    def is_on(self):
        return self.coordinator.samples[self.key].value


class TemperatureProbeFault(ChannelEntity, BinarySensorEntity):
    """Confirmed invalid register value; a missing block is not a probe fault."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, key, group, index):
        super().__init__(coordinator, key, group, index)
        self._attr_unique_id += "_probe_fault"
        language = coordinator.hass.config.language.lower()
        label = coordinator.options(key).get("name") or (
            f"Temperaturkanal {index + 1}"
            if language.startswith("de")
            else f"Temperature channel {index + 1}"
        )
        self._attr_name = (
            f"{label} – Fühlerstörung" if language.startswith("de") else f"{label} – Probe fault"
        )

    @property
    def available(self):
        sample = self.coordinator.samples[self.key]
        return (
            self.coordinator.enabled(self.key)
            and sample.raw_received is not None
            and time.monotonic() - sample.raw_received < 3 * self.coordinator.interval(self.key)
        )

    @property
    def is_on(self):
        return self.coordinator.samples[self.key].consecutive_probe_fault_values >= 3
