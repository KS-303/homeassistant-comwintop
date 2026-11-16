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
    # Exactly one experimental write site is allowed in this LAB build:
    # FC06, register 16 in the isolated TM-32DS address-change flow.
    write_sites = []
    for path in COMPONENT.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if not node.func.attr.startswith("write_") or node.func.attr == "write_text":
                    continue
                write_sites.append((path.name, node))
    assert len(write_sites) == 1, [(p, n.lineno) for p, n in write_sites]
    write_file, write_call = write_sites[0]
    assert write_file == "config_flow.py"
    assert write_call.func.attr == "write_register"
    assert len(write_call.args) == 2
    assert isinstance(write_call.args[0], ast.Constant) and write_call.args[0].value == 16
    assert isinstance(write_call.args[1], ast.Subscript)
    assert isinstance(write_call.args[1].value, ast.Name) and write_call.args[1].value.id == "plan"
    for name in ("switch", "number"):
        tree = ast.parse((COMPONENT / f"{name}.py").read_text())
        assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    for path in [ROOT / "README.md", *list((ROOT / "docs").glob("*.md"))]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
    print("Package metadata, translations, links and isolated FC06 laboratory boundary: PASS")


if __name__ == "__main__":
    check()
