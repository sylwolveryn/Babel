"""Guard: every addon dictionary entry must define both supported locales.

The in-game dictionary (addon/BabelChat/Data/*.lua) glosses WoW terms in
English (enUS) and Hungarian (huHU) — the two languages this 3.3.5 build
supports. A missing huHU silently falls back to English in game, so this test
fails loudly if any entry drops one, and also if a third locale creeps back in
as dead weight nobody can select.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

LOCALES = ("enUS", "huHU")

_DATA_DIR = Path(__file__).resolve().parent.parent / "addon" / "BabelChat" / "Data"
# ["key"] = { ... }  — locale tables contain no nested braces, so a non-greedy
# match up to the first closing brace captures the full entry body.
_ENTRY_RE = re.compile(r'\["([^"]+)"\]\s*=\s*\{(.*?)\}', re.S)
_LOCALE_KEY_RE = re.compile(r'(\w+)\s*=\s*"')


def _entries(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return _ENTRY_RE.findall(text)


def _data_files():
    return sorted(_DATA_DIR.glob("*.lua"))


def test_data_dir_present():
    files = _data_files()
    assert files, f"no dictionary Data files found in {_DATA_DIR}"


@pytest.mark.parametrize("path", _data_files(), ids=lambda p: p.name)
def test_every_entry_has_both_locales(path: Path):
    missing: list[str] = []
    for key, body in _entries(path):
        present = set(_LOCALE_KEY_RE.findall(body))
        gaps = [loc for loc in LOCALES if loc not in present]
        if gaps:
            missing.append(f"{key}: missing {gaps}")
    assert not missing, f"{path.name} has entries missing locales:\n" + "\n".join(missing)


@pytest.mark.parametrize("path", _data_files(), ids=lambda p: p.name)
def test_no_entry_carries_a_locale_nobody_can_select(path: Path):
    """The options panel offers English and Magyar. Any other column is never
    read and only costs memory on every login."""
    extra: list[str] = []
    for key, body in _entries(path):
        others = set(_LOCALE_KEY_RE.findall(body)) - set(LOCALES)
        if others:
            extra.append(f"{key}: {sorted(others)}")
    assert not extra, f"{path.name} carries unsupported locales:\n" + "\n".join(extra)


@pytest.mark.parametrize("path", _data_files(), ids=lambda p: p.name)
def test_every_category_file_holds_at_least_one_term(path: Path):
    """An empty category would be a checkbox in the panel that switches nothing."""
    assert _entries(path), f"{path.name} defines no terms"
