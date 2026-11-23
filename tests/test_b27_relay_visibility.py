"""Real HA entity registration plus RTU-over-TCP FC05 laboratory regression."""

from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.comwintop.const import DOMAIN

from .test_ha import wait_for
from .wire import Simulator


@pytest.fixture
async def mb307_rtu():
    server = await Simulator(mode="rtu").start()
    yield server
    await server.close()


def entry_for_mb307(sim):
    return ConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        title="Lab bus",
        data={
            "transport": "rtu_tcp",
            "host": "127.0.0.1",
            "port": sim.port,
            "name": "Lab bus",
            "connection_uid": "lab-bus",
            "baudrate": 9600,
            "parity": "N",
            "stopbits": 1,
        },
        options={},
        source="user",
        unique_id=f"rtu_tcp|127.0.0.1|{sim.port}",
        discovery_keys=MappingProxyType({}),
        subentries_data=[
            {
                "subentry_type": "device",
                "title": "MB307D",
                "unique_id": "lab-mb307d",
                "data": {
                    "model": "mb_307d_ii_s",
                    "unit_id": 1,
                    "device_uid": "lab-mb307d",
                    "name": "MB307D",
                    "connection_uid": "lab-bus",
                    "channels": {},
                    "intervals": {"di": 8, "do": 8, "ai": 20},
                },
            }
        ],
    )


async def test_all_eight_relay_controls_visible_while_locked_then_fc05_after_permission(
    hass, mb307_rtu
):
    entry = entry_for_mb307(mb307_rtu)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    assert entry.state.value == "loaded", entry.reason

    registry = er.async_get(hass)
    identities = [
        registry.async_get_entity_id("switch", DOMAIN, f"lab-mb307d_do_{i}_control")
        for i in range(1, 9)
    ]
    assert len(identities) == 8 and all(identities)
    assert all(hass.states.get(eid).state == "unavailable" for eid in identities)
    assert not [item for item in mb307_rtu.trace if item[1] == 5]

    sub = next(iter(entry.subentries.values()))
    updated = dict(sub.data) | {"channels": {"do_1": {"write_enabled": True}}}
    hass.config_entries.async_update_subentry(entry, sub, data=updated)
    await hass.async_block_till_done()
    coordinator = next(iter(entry.runtime_data.units.values()))
    await wait_for(lambda: coordinator._can_write("do_1"))
    assert all(
        registry.async_get_entity_id("switch", DOMAIN, f"lab-mb307d_do_{i}_control")
        == identities[i - 1]
        for i in range(1, 9)
    )
    assert hass.states.get(identities[0]).state in ("off", "on")
    assert hass.states.get(identities[1]).state == "unavailable"

    await hass.services.async_call("switch", "turn_on", {"entity_id": identities[0]}, blocking=True)
    assert mb307_rtu.bits.get((1, 0)) is True
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": identities[0]}, blocking=True
    )
    assert mb307_rtu.bits.get((1, 0)) is False
    writes = [item for item in mb307_rtu.trace if item[1] == 5]
    assert len(writes) == 2
    assert [row[3] for row in writes] == [0xFF00, 0x0000]
    assert not [item for item in mb307_rtu.trace if item[1] in (6, 15, 16)]
