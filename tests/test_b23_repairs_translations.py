"""Validate Home Assistant Repairs translation paths, not just language parity."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/comwintop"
CHECKS = ("bus_power_cycled", "sole_master_confirmed", "gateway_queues_cleared")


@pytest.mark.parametrize("language", ["strings", "de", "en"])
def test_rtu_repair_labels_are_at_ha_issues_fix_flow_paths(language):
    path = ROOT / ("strings.json" if language == "strings" else f"translations/{language}.json")
    contents = json.loads(path.read_text(encoding="utf-8"))
    assert "repairs" not in contents, "HA repair translations must be placed under issues"
    issue = contents["issues"]["rtu_recovery"]
    assert issue["title"].strip()
    assert "description" not in issue, "A fixable issue must use fix_flow instead"
    flow = issue["fix_flow"]
    step = flow["step"]["confirm"]
    assert step["title"].strip()
    assert step["description"].strip()
    assert set(step["data"]) == set(CHECKS)
    assert all(step["data"][key].strip() for key in CHECKS)
    assert flow["error"]["incomplete"].strip()
    exhausted = contents["issues"]["poll_exhausted"]
    assert exhausted["title"].strip()
    assert exhausted["description"].strip()


def test_german_rtu_repair_dialog_contains_three_unambiguous_physical_checks():
    value = json.loads((ROOT / "translations/de.json").read_text(encoding="utf-8"))
    dialog = value["issues"]["rtu_recovery"]["fix_flow"]["step"]["confirm"]
    assert "RTU" in dialog["title"]
    for word in ("Waveshare", "RS485", "Gateway"):
        assert any(word in label for label in dialog["data"].values())
    assert all(dialog["data"][key] != key for key in CHECKS)


def test_repair_form_fields_match_translated_field_keys():
    """Ensure a later field rename cannot silently blank all UI checkboxes."""
    import ast

    tree = ast.parse((ROOT / "repairs.py").read_text(encoding="utf-8"))
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_step_confirm"
    )
    required = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "Required" or not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            required.add(arg.value)
    assert required == set(CHECKS)
