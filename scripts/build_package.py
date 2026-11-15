"""Produce a reproducible installation ZIP and verify every archived byte."""

import hashlib
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from check_package import COMPONENT, ROOT, check


def build():
    check()
    version = json.loads((COMPONENT / "manifest.json").read_text())["version"]
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    output = destination / f"comwintop-{version}-install.zip"
    files = sorted(p for p in COMPONENT.rglob("*") if p.suffix in (".py", ".json"))
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
