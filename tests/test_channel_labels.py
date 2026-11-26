"""Channel labels must distinguish writable and read-only output models."""

import pytest

from custom_components.comwintop.config_flow import channel_label


@pytest.mark.parametrize(
    ("language", "label", "suffix"),
    [
        ("de", "Digitaler Ausgang", " – Rückmeldung"),
        ("en", "Digital output", " – readback"),
    ],
)
def test_output_channel_labels(language, label, suffix):
    for index in range(8):
        expected = f"{label} {index + 1}"
        assert channel_label("mb_307d_ii_s", "do", index, language) == expected
        assert channel_label("mb_308n", "do", index, language) == expected + suffix


def test_other_channel_labels_unchanged():
    assert channel_label("tm_32ds", "temperature", 0, "de") == "Temperaturkanal 1"
    assert channel_label("mb_307d_ii_s", "di", 7, "en") == "Digital input 8"
