"""Stable channel identity independent of host, unit address and display name."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .profiles import MODEL_NAMES


class ChannelEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, key, group, index):
        super().__init__(coordinator)
        self.key, self.group, self.index = key, group, index
        self._attr_unique_id = f"{coordinator.uid}_{key}"
        self._attr_translation_key = group.kind
        self._attr_translation_placeholders = {"channel": str(index + 1)}
        if custom_name := coordinator.options(key).get("name"):
            self._attr_name = custom_name
        self._attr_entity_registry_enabled_default = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.uid)},
            name=coordinator.subentry.title,
            manufacturer="ComWinTop",
            model=MODEL_NAMES[coordinator.model],
        )

    @property
    def available(self):
        return self.coordinator.available(self.key)

    @property
    def extra_state_attributes(self):
        sample = self.coordinator.samples[self.key]
        return {"quality": sample.error or "valid", "hardware_validated": False}
