"""AO writes are intentionally unavailable in the hardware-unvalidated beta."""


async def async_setup_entry(hass, entry, async_add_entities):
    return None
