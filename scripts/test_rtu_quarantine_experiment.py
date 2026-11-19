"""Run the RTU experiment against a disposable copy of the pinned dependency."""

import hashlib
import importlib.metadata
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if importlib.metadata.version("tmodbus") != "1.1.0":
        raise RuntimeError("This experiment requires tmodbus 1.1.0")
    spec = importlib.util.find_spec("tmodbus")
    if spec is None or spec.origin is None:
        raise RuntimeError("tmodbus is missing")
    with tempfile.TemporaryDirectory(prefix="comwintop-rtu-test-") as directory:
        work = Path(directory)
        src = work / "src"
        src.mkdir()
        shutil.copytree(Path(spec.origin).parent, src / "tmodbus")
        source = src / "tmodbus/transport/async_rtu.py"
        if hashlib.sha256(source.read_bytes()).hexdigest() != (
            "56a4dc8aa7aff3b837767eda25ba2b3541c0b5585a6a6f09a483931195b69c26"
        ):
            raise RuntimeError("Unexpected RTU source; experiment patch refused")
        patch = ROOT / "upstream_patches/tmodbus-1.1.0-rtu-quarantine-experiment.patch"
        for args in (("--check",), ()):
            subprocess.run(
                ["git", "apply", "--unidiff-zero", *args, str(patch)], cwd=work, check=True
            )
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join((str(src), str(ROOT)))
        subprocess.run(
            [sys.executable, str(ROOT / "upstream_patches/rtu_quarantine_check.py")],
            cwd=ROOT,
            env=env,
            check=True,
            timeout=20,
        )


if __name__ == "__main__":
    main()
