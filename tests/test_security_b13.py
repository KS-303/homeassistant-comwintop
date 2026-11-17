"""b13 security regressions: syntax, transport boundaries and read-only gates."""

import ast
from pathlib import Path

import pytest

from custom_components.comwintop.transport import endpoint_key, params_from


def test_python_313_syntax_in_all_project_sources():
    """No Python 3.14-only syntax may silently slip back into installation files."""
    root = Path(__file__).resolve().parents[1]
    for source in (
        *root.glob("custom_components/comwintop/**/*.py"),
        *root.glob("tests/**/*.py"),
        *root.glob("upstream_patches/**/*.py"),
    ):
        ast.parse(source.read_text(encoding="utf-8"), filename=str(source), feature_version=(3, 13))


@pytest.mark.parametrize("mode", ["tcp", "tcp_gateway"])
def test_tcp_hosts_are_case_insensitive(mode):
    first = {"transport": mode, "host": "Example.Local", "port": 502}
    other = {**first, "host": "example.local"}
    assert endpoint_key(first) == endpoint_key(other)
    assert params_from(first).host == "example.local"


def test_serial_symlink_outside_dev_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "custom_components.comwintop.transport.os.path.realpath",
        lambda _: "/etc/passwd",
    )
    with pytest.raises(ValueError, match="invalid_resolved_serial_path"):
        params_from({"transport": "serial", "device": "/dev/serial/by-id/EXAMPLE"})


def test_unsupported_temperature_format_still_fails_closed():
    from custom_components.comwintop.profiles import InvalidValue, decode_temperature

    for raw in (-1, 850, 65535):
        with pytest.raises(InvalidValue):
            decode_temperature(raw)


def test_audited_version_is_consistent():
    import json

    from custom_components.comwintop.const import VERSION

    manifest = Path(__file__).resolve().parents[1] / "custom_components/comwintop/manifest.json"
    assert VERSION == json.loads(manifest.read_text(encoding="utf-8"))["version"]
