import asyncio
import shutil
from pathlib import Path

import pytest
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame


@pytest.fixture
async def hass(tmp_path):
    shutil.copytree(Path(__file__).parents[1] / "custom_components", tmp_path / "custom_components")
    h = HomeAssistant(str(tmp_path))
    h.config.skip_pip = True
    loader.async_setup(h)
    frame.async_setup(h)
    h.config_entries = ConfigEntries(h, {})
    await async_load_base_functionality(h)
    yield h
    for entry in h.config_entries.async_entries("comwintop"):
        await h.config_entries.async_unload(entry.entry_id)
    async with asyncio.timeout(10):
        await h.async_stop(force=True)
    await h.async_block_till_done()
