"""Validate local package metadata, translations and the beta write boundary."""

import ast
import json
import re
import struct
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/comwintop"


def leaves(value, prefix=""):
    if isinstance(value, dict):
        return set().union(*(leaves(v, f"{prefix}/{k}") for k, v in value.items()))
    assert isinstance(value, str), prefix
    return {prefix}


def check():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert manifest["domain"] == "comwintop"
    assert manifest["version"] == project["project"]["version"]
    constants = ast.parse((COMPONENT / "const.py").read_text())
    versions = [
        node.value.value
        for node in constants.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets)
        and isinstance(node.value, ast.Constant)
    ]
    assert versions == [manifest["version"]]
    assert manifest["dependencies"] == ["modbus"]
    assert manifest["requirements"] == []
    expected = leaves(json.loads((COMPONENT / "strings.json").read_text()))
    for name in ("de", "en"):
        assert leaves(json.loads((COMPONENT / f"translations/{name}.json").read_text())) == expected
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        image = (COMPONENT / "brand" / name).read_bytes()
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", image[16:24]) == (size, size)
    # Writing is deliberately confined to the bounded lab executor, which
    # uses the shared HA RTU connection and calls no write_* API with retries.
    from_site = (COMPONENT / "coordinator.py").read_text(encoding="utf-8")
    transport_site = (COMPONENT / "single_attempt.py").read_text(encoding="utf-8")
    assert "fc05_once(self.unit, address, bool(value), guard)" in from_site
    assert "base.send_and_receive(" in transport_site
    assert "transport.send_and_receive(" not in transport_site
    assert "unit.write_coil(" not in from_site
    assert "write_enabled" in (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    for path in COMPONENT.glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
    for path in [ROOT / "README.md", *list((ROOT / "docs").glob("*.md"))]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
    print("Package metadata, translations, link and laboratory write boundary: PASS")


if __name__ == "__main__":
    check()
