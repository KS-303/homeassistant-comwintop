"""Run the upstream wire prototypes against isolated, patched package copies."""

import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    ("tmodbus", "1.1.0", "tmodbus-1.1.0-no-retry.patch"),
    ("modbus_connection", "4.12.7", "modbus-connection-4.12.7-no-retry.patch"),
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="comwintop-upstream-") as directory:
        isolated = Path(directory)
        source = isolated / "src"
        source.mkdir()
        for package, version, patch in PACKAGES:
            distribution = package.replace("_", "-")
            actual = importlib.metadata.version(distribution)
            if actual != version:
                raise RuntimeError(f"{distribution}: expected {version}, found {actual}")
            spec = importlib.util.find_spec(package)
            if not spec or not spec.origin:
                raise RuntimeError(f"Missing installed package: {package}")
            shutil.copytree(Path(spec.origin).parent, source / package)
            patch_file = ROOT / "upstream_patches" / patch
            for args in (("--check",), ()):
                subprocess.run(
                    ["git", "apply", *args, str(patch_file)],
                    cwd=isolated,
                    check=True,
                )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join((str(source), str(ROOT)))
        for script in ("wire_check.py", "pty_check.py"):
            subprocess.run(
                [sys.executable, str(ROOT / "upstream_patches" / script)],
                cwd=ROOT,
                env=environment,
                check=True,
                timeout=180,
            )


if __name__ == "__main__":
    main()
