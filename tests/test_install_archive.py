"""The HA archive must not collect local or dormant development files."""

from pathlib import Path
from shutil import copytree
from zipfile import ZipFile

import pytest

from scripts import build_package


def test_install_archive_excludes_extra_files_in_lab_release(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "custom_components/comwintop"
    component = tmp_path / "custom_components/comwintop"
    copytree(source, component, ignore=lambda _folder, names: {"__pycache__"} & set(names))
    (component / "private-notes.json").write_text('{"token": "should-stay-local"}')
    (component / "private-notes.py").write_text("PRIVATE = True\n")
    monkeypatch.setattr(build_package, "ROOT", tmp_path)
    monkeypatch.setattr(build_package, "COMPONENT", component)

    build_package.build()
    archive = next((tmp_path / "dist").glob("comwintop-*-install.zip"))
    with ZipFile(archive) as zipped:
        names = set(zipped.namelist())
        assert names == {
            f"custom_components/comwintop/{name}" for name in build_package.INSTALL_FILES
        }
        assert "custom_components/comwintop/write_manager.py" in names
        assert "custom_components/comwintop/single_attempt.py" in names
        assert not any("private-notes" in name for name in names)
        assert zipped.testzip() is None


def test_install_archive_rejects_symlinked_component_file(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[1] / "custom_components/comwintop"
    component = tmp_path / "custom_components/comwintop"
    copytree(source, component, ignore=lambda _folder, names: {"__pycache__"} & set(names))
    icon = component / "brand/icon.png"
    icon.unlink()
    icon.symlink_to(tmp_path / "local-image.png")
    monkeypatch.setattr(build_package, "ROOT", tmp_path)
    monkeypatch.setattr(build_package, "COMPONENT", component)

    with pytest.raises(AssertionError, match="icon.png"):
        build_package.build()
