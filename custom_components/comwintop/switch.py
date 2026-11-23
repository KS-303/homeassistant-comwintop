"""Explicit per-channel DO switches; certified transport required to create any."""

from homeassistant.components.switch import SwitchEntity

from .const import HARDWARE_VALIDATED_WRITES
from .entity import ChannelEntity
from .profiles import channels


async def async_setup_entry(hass, entry, async_add_entities):
    for sub_id, coordinator in entry.runtime_data.units.items():
        # Do not expose misleading or usable controls until FC05 no-retry,
        # atomic send guard and recovery are hardware/transport validated.
        if (
            coordinator.model != "mb_307d_ii_s"
            or (coordinator.model, entry.data["transport"], "fc05") not in HARDWARE_VALIDATED_WRITES
        ):
            continue
        entities = [
            RelaySwitch(coordinator, key, group, index)
            for key, group, index in channels(coordinator.model)
            if group.kind == "do"
            and coordinator.enabled(key)
            and coordinator.options(key).get("write_enabled", False) is True
        ]
        if entities:
            async_add_entities(entities, config_subentry_id=sub_id)


class RelaySwitch(ChannelEntity, SwitchEntity):
    """Read state from FC01; switching (when certified) uses FC05."""

    _attr_assumed_state = False

    def __init__(self, coordinator, key, group, index):
        super().__init__(coordinator, key, group, index)
        self._attr_unique_id = f"{coordinator.uid}_{key}_control"
        self._attr_translation_key = None
        self._attr_name = (
            f"{coordinator.options(key).get('name') or f'Relais {index + 1}'} – Schalten"
        )

    @property
    def available(self):
        return self.coordinator._can_write(self.key)

    @property
    def is_on(self):
        return self.coordinator.samples[self.key].value

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_output(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_output(self.key, False)
