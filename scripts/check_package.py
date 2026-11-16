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
    for path in COMPONENT.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not (
                    node.func.attr.startswith("write_") and node.func.attr != "write_text"
                ), (path, node.lineno)
    for name in ("switch", "number"):
        tree = ast.parse((COMPONENT / f"{name}.py").read_text())
        assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    for path in [ROOT / "README.md", *list((ROOT / "docs").glob("*.md"))]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
    print("Package metadata, translation keys, links and read-only boundary: PASS")


if __name__ == "__main__":
    check()
