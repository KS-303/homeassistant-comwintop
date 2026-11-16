"""Isolated TM-32DS lab flow: explicit confirmation and readback of FC06."""

import struct

from .test_l50 import configured_entry
from .wire import Simulator


class AddressChangingSimulator(Simulator):
    """One virtual TM-32DS initially at ID 1; ID 2 is silent until FC06."""

    def __init__(self):
        super().__init__()
        self.registers[1, 16] = 0x0104
        self.silent_units.add(2)

    def pdu(self, unit, data):
        fc = data[0]
        if unit == 1 and fc == 6:
            address, value = struct.unpack(">HH", data[1:5])
            if address == 16:
                answer = super().pdu(unit, data)
                if value == 0x0204:
                    self.registers[2, 16] = value
                    self.registers[2, 32] = 216
                    self.silent_units.discard(2)
                return answer
        return super().pdu(unit, data)


async def open_address_flow(hass, entry, sub):
    flow = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "device"),
        context={"source": "reconfigure", "subentry_id": sub.subentry_id},
    )
    assert "address_test" in flow["menu_options"]
    return await hass.config_entries.subentries.async_configure(
        flow["flow_id"], {"next_step_id": "address_test"}
    )


async def test_test_write_requires_both_acknowledgements(hass):
    simulator = await AddressChangingSimulator().start()
    try:
        entry = configured_entry(port=simulator.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))
        flow = await open_address_flow(hass, entry, sub)
        assert flow["step_id"] == "address_test"
        flow = await hass.config_entries.subentries.async_configure(
            flow["flow_id"],
            {"target_id": 2, "isolated": False, "understand_retry": False},
        )
        assert flow["errors"]["base"] == "test_acknowledgement_required"
        assert not [call for call in simulator.trace if call[1] == 6]
        assert sub.data["unit_id"] == 1
    finally:
        await simulator.close()


async def test_tm32ds_lab_write_change_id_and_preserve_subentry(hass):
    simulator = await AddressChangingSimulator().start()
    try:
        entry = configured_entry(port=simulator.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))
        old_unique_id = sub.unique_id
        flow = await open_address_flow(hass, entry, sub)
        flow = await hass.config_entries.subentries.async_configure(
            flow["flow_id"],
            {"target_id": 2, "isolated": True, "understand_retry": True},
        )
        assert flow["step_id"] == "address_test_confirm"
        assert flow["description_placeholders"]["new_raw"] == "0x0204"
        flow = await hass.config_entries.subentries.async_configure(
            flow["flow_id"], {"confirm": True}
        )
        assert flow["type"] == "abort", flow
        assert flow["reason"] == "reconfigure_successful", flow
        assert entry.subentries[sub.subentry_id].unique_id == old_unique_id
        assert entry.subentries[sub.subentry_id].data["unit_id"] == 2
        assert len([call for call in simulator.trace if call[1] == 6]) == 1
        assert (2, 3, 16, 1) in simulator.trace
        assert (2, 3, 32, 1) in simulator.trace
    finally:
        await simulator.close()
