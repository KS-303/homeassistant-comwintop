"""Ensure HA actually resolves new subentry labels and safety descriptions."""

from homeassistant.helpers.translation import async_get_translations

from custom_components.comwintop.const import DOMAIN


async def test_subentry_translation_keys_resolve_for_de_and_en(hass):
    for language, translated in (
        ("de", "Slave-ID ändern"),
        ("en", "Change slave ID"),
    ):
        labels = await async_get_translations(hass, language, "config_subentries", {DOMAIN})
        prefix = f"component.{DOMAIN}.config_subentries.device."
        required = {
            "step.reconfigure.menu_options.communication",
            "step.reconfigure.menu_options.address_test",
            "step.communication.title",
            "step.communication.description",
            "step.communication.data.inspection",
            "step.address_test.title",
            "step.address_test.description",
            "step.address_test.data.target_id",
            "step.address_test.data.lab_notice",
            "step.address_test.data.isolated",
            "step.address_test.data.understand_retry",
            "step.address_test_confirm.title",
            "step.address_test_confirm.description",
            "step.address_test_confirm.data.write_preview",
            "step.address_test_confirm.data.confirm",
        }
        assert all(prefix + field in labels for field in required), [
            key for key in required if prefix + key not in labels
        ]
        assert translated in labels[prefix + "step.reconfigure.menu_options.address_test"]
