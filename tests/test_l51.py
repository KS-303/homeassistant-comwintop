"""L-51 safe inspection: no configuration write is reachable."""

import pytest

from custom_components.comwintop.communication import PROFILES, inspect_tm32ds

from .test_l50 import configured_entry
from .wire import Simulator


def test_profile_is_read_only_and_undocumented_model_is_locked():
    assert PROFILES["tm_32ds"].register == 16
    assert PROFILES["tm_32ds"].write_function == 6
    assert not PROFILES["tm_32ds"].write_enabled
    assert PROFILES["mb_308n"].register is None
    assert not PROFILES["mb_308n"].write_enabled


@pytest.mark.parametrize("raw,address", [(0x0104, "1"), (0x0204, "2")])
def test_observed_register_decode(raw, address):
    result = inspect_tm32ds(raw, 1)
    assert result["address"] == address
    assert result["raw"] == f"0x{raw:04X}"
    assert (result["baudrate"], result["parity"], result["databits"], result["stopbits"]) == (
        "9600",
        "N",
        "8",
        "1",
    )


def test_unknown_bits_not_guessed():
    assert inspect_tm32ds(0x0266, 1)["baudrate"] == "?"


async def test_ha_inspection_reads_once_and_never_writes(hass):
    sim = await Simulator().start()
    try:
        sim.registers[1, 16] = 0x0104
        entry = configured_entry(port=sim.port)
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        sub = next(iter(entry.subentries.values()))
        flow = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "device"),
            context={"source": "reconfigure", "subentry_id": sub.subentry_id},
        )
        assert "communication" in flow["menu_options"]
        flow = await hass.config_entries.subentries.async_configure(
            flow["flow_id"], {"next_step_id": "communication"}
        )
        assert flow["step_id"] == "communication"
        assert flow["description_placeholders"]["raw"] == "0x0104"
        assert flow["description_placeholders"]["status"] == "read_only"
        assert flow["data_schema"].schema == {}
        assert (1, 3, 16, 1) in sim.trace
        assert all(call[1] in (1, 2, 3, 4) for call in sim.trace)
        assert sub.data["unit_id"] == 1
    finally:
        await sim.close()
