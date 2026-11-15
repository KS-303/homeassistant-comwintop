"""DO writes are intentionally unavailable in the hardware-unvalidated beta."""


async def async_setup_entry(hass, entry, async_add_entities):
    # No switch services/entities that could bypass the release gate.
    return None
