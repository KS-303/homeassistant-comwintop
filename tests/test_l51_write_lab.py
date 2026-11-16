"""Security regression: no FC06 access through legacy address-test flow URLs."""

import pytest
from homeassistant.data_entry_flow import InvalidData

from .test_l50 import configured_entry
from .wire import Simulator


async def test_legacy_address_test_actions_fail_closed_without_writes(hass):
    sim = await Simulator().start()
    try:
        entry = configured_entry(port=sim.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))

        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        assert "address_test" not in flow["menu_options"]
        assert "communication" in flow["menu_options"]

        for step in ("address_test", "address_test_confirm"):
            legacy = await hass.config_entries.subentries.async_init(
                (entry.entry_id, "device"),
                context={"source": "reconfigure", "subentry_id": sub.subentry_id},
            )
            # Home Assistant rejects the removed menu value before invoking
            # the integration at all, which is stronger than reaching FC06.
            with pytest.raises(InvalidData):
                await hass.config_entries.subentries.async_configure(
                    legacy["flow_id"], {"next_step_id": step}
                )
        assert sub.data["unit_id"] == 1
        assert not any(call[1] in (5, 6, 15, 16) for call in sim.trace)
    finally:
        await sim.close()
