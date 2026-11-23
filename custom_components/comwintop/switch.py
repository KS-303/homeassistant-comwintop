"""Visible MB307D relay controls; each actual write requires separate permission."""

from homeassistant.components.switch import SwitchEntity

from .entity import ChannelEntity
from .profiles import channels


async def async_setup_entry(hass, entry, async_add_entities):
    for sub_id, coordinator in entry.runtime_data.units.items():
        # Always register control entities for the MB307D, even if per-channel
        # permission has not yet been granted. Locked controls are unavailable.
        # The low-level hardware release gate remains enforced by the coordinator.
        if coordinator.model != "mb_307d_ii_s":
            continue
        entities = [
            RelaySwitch(coordinator, key, group, index)
            for key, group, index in channels(coordinator.model)
            if group.kind == "do" and coordinator.enabled(key)
        ]
        if entities:
            async_add_entities(entities, config_subentry_id=sub_id)


class RelaySwitch(ChannelEntity, SwitchEntity):
    """Report FC01 state; FC05 is only possible with explicit permission."""

    _attr_assumed_state = False

    def __init__(self, coordinator, key, group, index):
        super().__init__(coordinator, key, group, index)
        self._attr_unique_id = f"{coordinator.uid}_{key}_control"
        self._attr_translation_key = None
        self._attr_name = (
            f"{coordinator.options(key).get('name') or f'Digitaler Ausgang {index + 1}'} – Schalten"
        )

    @property
    def available(self):
        return self.coordinator._write_manager is not None and self.coordinator._can_write(self.key)

    @property
    def is_on(self):
        return self.coordinator.samples[self.key].value

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_output(self.key, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_output(self.key, False)
