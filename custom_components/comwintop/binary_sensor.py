"""Digital inputs and internal output readbacks, never contact proof."""

from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ChannelEntity
from .profiles import channels


async def async_setup_entry(hass, entry, async_add_entities):
    for sub_id, coordinator in entry.runtime_data.units.items():
        async_add_entities(
            [
                DigitalSensor(coordinator, key, group, index)
                for key, group, index in channels(coordinator.model)
                if group.kind in ("di", "do") and coordinator.enabled(key)
            ],
            config_subentry_id=sub_id,
        )


class DigitalSensor(ChannelEntity, BinarySensorEntity):
    @property
    def is_on(self):
        return self.coordinator.samples[self.key].value
