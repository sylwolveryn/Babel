"""Which language the interface opens in.

The interface is Hungarian only, so there is nothing to guess: the OS-locale
guess that used to run on a first launch is gone. What is left is the rule
that a saved choice is honoured when it is one this build has, and the
question of what counts as a saved config at all — which `load` and the
first-run check must answer from the same files.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.config import AppConfig, saved_config_exists
from app.i18n import DEFAULT_UI_LANGUAGE, UI_LANGUAGES, startup_ui_language, tr


def test_the_default_is_hungarian():
    assert DEFAULT_UI_LANGUAGE == "HU"
    assert DEFAULT_UI_LANGUAGE in UI_LANGUAGES


def test_a_saved_choice_is_honoured():
    assert startup_ui_language(config_exists=True, saved="HU") == "HU"


@pytest.mark.parametrize("saved", ["RU", "ES", "EN", "", "zz"])
def test_a_saved_language_this_build_does_not_have_falls_back(saved):
    """A config from before the conversion says RU; showing a language with no
    locale file would render every label as its key."""
    assert startup_ui_language(config_exists=True, saved=saved) == DEFAULT_UI_LANGUAGE


@pytest.mark.parametrize("saved", ["HU", "RU"])
def test_a_first_run_gets_the_default(saved):
    """No config file: `saved` is only the dataclass default, not a choice."""
    assert startup_ui_language(config_exists=False, saved=saved) == DEFAULT_UI_LANGUAGE


def test_the_entry_point_asks_the_shared_rule():
    """The decision lives in one function, and the entry point asks config.py
    what a first run is rather than statting the config path itself."""
    import ast

    root = pathlib.Path(__file__).resolve().parent.parent
    source = (root / "app" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "startup_ui_language" in called, "main.py decides the startup language by itself"
    assert "saved_config_exists" in called, "main.py decides what a first run is without asking config.py"

    # os.path.exists(CONFIG_FILE) is the wrong question: load() also reads
    # config.json.bak, so the main file's absence is not proof there is no
    # saved language.
    segments = [ast.get_source_segment(source, node) or "" for node in ast.walk(tree)]
    stats = [seg for seg in segments if "CONFIG_FILE" in seg and "exists" in seg]
    assert stats == [], f"main.py still stats the config path: {stats}"


# ── what counts as having run this app before ────────────────────────────────


def _write(path, **fields) -> None:
    path.write_text(json.dumps(fields), encoding="utf-8")


def test_a_config_only_in_the_backup_still_counts(tmp_path):
    """`AppConfig.load` reads config.json.bak when the main file is gone — and
    hands back what is saved in it. Asking `os.path.exists(CONFIG_FILE)`
    instead calls that a first run."""
    main = tmp_path / "config.json"
    _write(main.with_suffix(".json.bak"), overlay_opacity=123)

    assert not main.exists()
    assert saved_config_exists(str(main)) is True
    assert AppConfig.load(str(main)).overlay_opacity == 123


def test_a_corrupt_config_with_no_backup_is_a_first_run(tmp_path):
    """`load` falls back to defaults here, so what it returns is not a choice
    anybody made."""
    main = tmp_path / "config.json"
    main.write_text("{ this is not json", encoding="utf-8")

    assert saved_config_exists(str(main)) is False
    assert AppConfig.load(str(main)).ui_language == "HU"


def test_nothing_on_disk_is_a_first_run(tmp_path):
    assert saved_config_exists(str(tmp_path / "config.json")) is False


def test_the_question_and_the_answer_read_the_same_files(tmp_path):
    """These drifted the moment they were written apart: one stats a filename,
    the other has a fallback list. They share the list now."""
    from app.config import _config_candidates

    main = tmp_path / "config.json"
    candidates = [str(p) for p in _config_candidates(str(main))]

    assert candidates == [str(main), str(main.with_suffix(".json.bak"))]

    for candidate in candidates:
        pathlib.Path(candidate).write_text(json.dumps({"ui_language": "HU"}), encoding="utf-8")
        assert saved_config_exists(str(main)) is True
        pathlib.Path(candidate).unlink()


def test_asking_does_not_rewrite_anything(tmp_path):
    """A question that quietly writes backups is not a question."""
    main = tmp_path / "config.json"
    _write(main, ui_language="RU", providers="not-a-dict")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    assert saved_config_exists(str(main)) is True
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


# ── setting a language ───────────────────────────────────────────────────────


def test_setting_a_language_accepts_every_language_the_interface_has():
    previous = tr.get_language()
    try:
        for code in UI_LANGUAGES:
            tr.set_language(code)

            assert tr.get_language() == code, f"{code} is offered but not accepted"
    finally:
        tr.set_language(previous)


def test_a_language_that_does_not_exist_is_refused():
    """The fallback is what keeps a stale or hand-edited config from blanking
    the interface."""
    previous = tr.get_language()
    try:
        tr.set_language("ZZ")

        assert tr.get_language() == DEFAULT_UI_LANGUAGE
    finally:
        tr.set_language(previous)
