"""Local profile validation, recovery and Home Assistant activation."""

from pathlib import Path

import pytest

from custom_components.comwintop.profiles import (
    BUILTIN_NAMES,
    BUILTIN_PROFILES,
    MODEL_NAMES,
    PROFILES,
    InvalidValue,
    install_local_profiles,
    parse_profile,
)

from .test_ha import make_entry, wait_for
from .test_ha import sim as sim

PROFILE = """\
version: 1
model: compatible_test_module
name: Compatible test module
groups:
  - kind: temperature
    method: read_holding_registers
    decoder: tm_32ds_temperature
    start: 32
    count: 2
"""


@pytest.fixture(autouse=True)
def reset_registry():
    yield
    PROFILES.clear()
    PROFILES.update(BUILTIN_PROFILES)
    MODEL_NAMES.clear()
    MODEL_NAMES.update(BUILTIN_NAMES)


def test_local_profile_and_invalid_variants():
    model, name, groups = parse_profile(PROFILE, filename="compatible_test_module.yaml")
    assert model == "compatible_test_module" and name == "Compatible test module"
    assert [(g.start, g.count) for g in groups] == [(32, 2)]
    bad = (
        PROFILE.replace("read_holding_registers", "write_register"),
        PROFILE.replace("tm_32ds_temperature", "arbitrary_python"),
        PROFILE.replace("count: 2", "count: 65"),
        PROFILE.replace("start: 32", "start: 65535"),
        PROFILE.replace("count: 2", "count: true"),
        PROFILE.replace("model: compatible_test_module", "model: tm_32ds"),
        PROFILE.replace("version: 1", "version: 2"),
        PROFILE + "version: 1\n",
        PROFILE.replace("kind: temperature", "kind: [temperature]"),
        PROFILE.replace(
            "count: 2",
            "count: 2\n  - kind: temperature\n    method: read_holding_registers\n    decoder: tm_32ds_temperature\n    start: 34\n    count: 2",
        ),
        "!!python/object/apply:os.system ['touch /tmp/forbidden']",
    )
    for content in bad:
        with pytest.raises(InvalidValue):
            parse_profile(content, filename="compatible_test_module.yaml")


def test_last_valid_profile_on_corrupt_or_missing_active_file(tmp_path: Path):
    active = tmp_path / "profiles"
    active.mkdir()
    path = active / "compatible_test_module.yaml"
    path.write_text(PROFILE)
    assert install_local_profiles(tmp_path) == {}
    assert len(PROFILES["compatible_test_module"]) == 1
    assert (tmp_path / "last_valid" / path.name).read_text() == PROFILE
    path.write_text(PROFILE.replace("count: 2", "count: 3"))
    assert install_local_profiles(tmp_path) == {}
    assert (tmp_path / "last_valid" / "compatible_test_module.previous").read_text() == PROFILE
    path.write_text("version: [invalid")
    assert path.name in install_local_profiles(tmp_path)
    assert PROFILES["compatible_test_module"][0].count == 3
    path.unlink()
    assert path.name in install_local_profiles(tmp_path)
    assert PROFILES["compatible_test_module"][0].count == 3
    assert PROFILES["tm_32ds"] == BUILTIN_PROFILES["tm_32ds"]


async def test_ha_preview_then_read_only_activation(hass, sim):
    active = Path(hass.config.path("comwintop", "profiles"))
    await hass.async_add_executor_job(active.mkdir, 0o777, True, True)
    await hass.async_add_executor_job((active / "compatible_test_module.yaml").write_text, PROFILE)
    entry = make_entry(sim)
    await hass.config_entries.async_add(entry)
    await hass.async_block_till_done()
    manager = hass.config_entries.subentries
    flow = await manager.async_init((entry.entry_id, "device"), context={"source": "user"})
    result = await manager.async_configure(
        flow["flow_id"],
        {
            "name": "Test module",
            "model": "compatible_test_module",
            "unit_id": 2,
            "acknowledge_beta": True,
        },
    )
    assert result["step_id"] == "profile_preview"
    assert "read_holding_registers 32–33" in result["description_placeholders"]["reads"]
    assert len(entry.subentries) == 1
    result = await manager.async_configure(flow["flow_id"], {"confirm": True})
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    coordinator = next(
        c for c in entry.runtime_data.units.values() if c.model == "compatible_test_module"
    )
    await wait_for(lambda: coordinator.samples["temperature_2"].value is not None)
    assert not [record for record in sim.trace if record[1] not in (1, 2, 3, 4)]
