"""Everything the app writes stays in its own folder (app/paths.py)."""

from __future__ import annotations

import sys
from pathlib import Path

from app import cache, config, single_instance
from app.paths import app_dir


def test_from_source_the_folder_is_the_project():
    assert (app_dir() / "app" / "paths.py").is_file()


def test_built_the_folder_is_the_exe_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "BabelChat.exe"))
    assert app_dir() == tmp_path.resolve()


def test_every_data_file_is_in_the_app_folder():
    root = app_dir()
    for path in (config.CONFIG_FILE, cache.DEFAULT_DB_PATH, single_instance._LOCK_FILE):
        assert Path(path).resolve().parent == root
