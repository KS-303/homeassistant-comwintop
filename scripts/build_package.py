"""Produce a reproducible installation ZIP and verify every archived byte."""

import ast
import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

if __package__:
    from .check_package import COMPONENT, ROOT, check
else:
    from check_package import COMPONENT, ROOT, check

INSTALL_FILES = (
    "__init__.py",
    "binary_sensor.py",
    "communication.py",
    "config_flow.py",
    "const.py",
    "coordinator.py",
    "diagnostics.py",
    "entity.py",
    "manifest.json",
    "model.py",
    "number.py",
    "profiles.py",
    "rtu_safety.py",
    "sensor.py",
    "strings.json",
    "switch.py",
    "transport.py",
    "translations/de.json",
    "translations/en.json",
    "brand/icon.png",
    "brand/icon@2x.png",
)


def build():
    check()
    version = json.loads((COMPONENT / "manifest.json").read_text())["version"]
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    output = destination / f"comwintop-{version}-install.zip"
    # A strict allowlist keeps local profiles, untracked files and the dormant
    # WriteManager prototype out of a read-only HA installation package.
    files = [COMPONENT / relative for relative in INSTALL_FILES]
    for path in files:
        assert path.is_file() and not any(
            candidate.is_symlink() for candidate in (COMPONENT, path.parent, path)
        ), path
    # Any package-local module imported by an installed Python module must be
    # present in the release archive. CI used to pass while rtu_safety.py was
    # accidentally omitted, causing an ImportError only after installation.
    included = set(INSTALL_FILES)
    for path in files:
        if path.suffix != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                dependency = f"{node.module.split('.')[0]}.py"
                if (COMPONENT / dependency).is_file():
                    assert dependency in included, (
                        f"{path.name} imports missing install dependency {dependency}"
                    )
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            info = ZipInfo(path.relative_to(ROOT).as_posix(), (2026, 11, 15, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with ZipFile(output) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(files)
        for path in files:
            assert archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(f"{output.name}: {len(files)} files; SHA-256 {digest}")


if __name__ == "__main__":
    build()
