"""Ensure read-only communication labels resolve and unsafe address flow is hidden."""

from homeassistant.helpers.translation import async_get_translations

from custom_components.comwintop.const import DOMAIN


async def test_communication_labels_resolve_in_german_and_english(hass):
    for language in ("de", "en"):
        labels = await async_get_translations(hass, language, "config_subentries", {DOMAIN})
        prefix = f"component.{DOMAIN}.config_subentries.device."
        required = {
            "step.reconfigure.menu_options.communication",
            "step.communication.title",
            "step.communication.description",
            "step.communication.data.address",
            "step.communication.data.configured_address",
            "step.communication.data.raw",
            "step.communication.data.baudrate",
            "step.communication.data.parity",
            "step.communication.data.databits",
            "step.communication.data.stopbits",
            "step.communication.data.status",
        }
        assert all(prefix + key in labels for key in required)
