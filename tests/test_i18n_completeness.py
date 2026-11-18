"""The string table: complete, reachable, and actually used.

The interface is Hungarian only (app/locales/hu.py). Three failure modes, all
of which shipped in some form. A key the code asks for and the table lacks
renders as its own name — `tr` returns the key on a miss, so
`settings_tab_general` appears on screen looking almost like a label. A
placeholder the code does not supply raises when the string is rendered. And a
string written straight into a widget never reaches the table at all, which is
how the settings dialog once ended up half in English.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.i18n import _STRINGS, tr

LANGUAGES = ("HU",)
APP = Path(__file__).resolve().parent.parent / "app"

# The Qt surfaces a player actually reads.
LOCALISED_MODULES = (
    "settings_dialog.py",
    "setup_wizard.py",
    "wizard_pages_qt.py",
)


def source(name: str) -> str:
    return (APP / name).read_text(encoding="utf-8")


# ── completeness ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_key_exists_in_every_language(language):
    missing = sorted(key for key, values in _STRINGS.items() if language not in values)
    assert missing == [], f"{language} is missing: {missing}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_translation_is_blank(language):
    blank = sorted(key for key, values in _STRINGS.items() if not values.get(language, "").strip())
    assert blank == [], f"{language} has empty strings: {blank}"


def _tr_calls() -> list[tuple[str, str, set[str]]]:
    """Every `tr("key", name=...)` and `tr("key").format(name=...)` in the app,
    as (file, key, the keyword names it supplies)."""
    found = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call = node
            # tr("key").format(...)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
                call = node.func.value
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "tr"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str)
            ):
                continue
            names = {kw.arg for kw in node.keywords if kw.arg}
            if names:
                found.append((path.name, call.args[0].value, names))
    return found


def test_the_scan_finds_the_calls_that_pass_placeholders():
    """An empty scan would pass the test below on any table."""
    keys = {key for _file, key, _names in _tr_calls()}

    assert "wizard.step_of" in keys, "the scan no longer sees tr(key, name=...) calls"


def test_every_placeholder_a_string_needs_is_supplied_by_the_code():
    """With one language there is nothing to compare a translation against, so
    the reference is the code: a `{field}` the caller does not pass raises
    KeyError the moment that string is rendered."""
    unsupplied = []
    for module, key, names in _tr_calls():
        for language, text in _STRINGS.get(key, {}).items():
            needed = set(re.findall(r"\{(\w+)\}", text))
            if not needed <= names:
                unsupplied.append((module, key, language, sorted(needed - names)))
    assert unsupplied == [], f"placeholders the code never passes: {unsupplied}"


def test_every_key_is_declared_once_in_its_file():
    """A dict literal keeps the last of two equal keys without a word, so a
    second copy added further down silently replaces the first."""
    from app.locales import LANGUAGE_MODULES

    for language, module in LANGUAGE_MODULES.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        keys = [
            node.value
            for table in ast.walk(tree)
            if isinstance(table, ast.Dict)
            for node in table.keys
            if isinstance(node, ast.Constant)
        ]
        duplicated = sorted({key for key in keys if keys.count(key) > 1})
        assert duplicated == [], f"{language} declares these twice: {duplicated}"


# ── reachability ─────────────────────────────────────────────────────────────


def referenced_keys() -> set[str]:
    keys: set[str] = set()
    for path in APP.rglob("*.py"):
        # i18n.py defines tr; its docstrings show `tr("key")` as an example.
        if path.name == "i18n.py":
            continue
        keys.update(re.findall(r'tr\(\s*"([a-z0-9_.]+)"', path.read_text(encoding="utf-8")))
    return keys


def test_every_key_the_code_asks_for_exists():
    """`tr` returns the key itself on a miss, so a typo reaches the screen as a
    plausible-looking label rather than as an error."""
    unknown = sorted(referenced_keys() - set(_STRINGS))
    assert unknown == [], f"asked for but not defined: {unknown}"


def test_a_missing_key_is_visible_rather_than_silent():
    """Pinning the current behaviour: it returns the key. That is survivable
    only because the test above exists."""
    assert tr("no.such.key.exists") == "no.such.key.exists"


def test_a_string_with_a_placeholder_renders():
    assert "7" in tr("settings.privacy.cleared", n=7)


def test_a_missing_placeholder_argument_does_not_crash_the_interface():
    """A caller that forgets an argument should lose the substitution, not the
    window."""
    rendered = tr("settings.privacy.cleared")
    assert isinstance(rendered, str) and rendered


# ── strings that never reached the table ─────────────────────────────────────

# Text that is not language: a brand name, a URL, a placeholder shown as an
# example, or styling. Anything else in a widget constructor is a missed string.
_NOT_LANGUAGE = re.compile(
    r"^(?:"
    r"\s*|[\W\d_]+|"  # punctuation, digits, symbols, icons
    r"(?:\{[^}]*\}|[^A-Za-z]|[A-Za-z]?%)+|"  # f-string composition, not copy
    r"https?://\S+|"  # links
    r"[A-Za-z-]+\.(?:py|json|log|pem|ico|png|exe)|"  # filenames
    r"[A-Za-z]:[/\\].*|"  # example paths shown as placeholders
    r"(?:Ctrl|Alt|Shift|Win)[+]\S+|"  # hotkey combinations
    r"[#][0-9a-fA-F]{3,8}|"  # colour codes
    r"WoW:.*|"  # the connection badge: a brand name and a symbol
    r"(?:Enter|Esc|Tab|Space)|"  # key names, which WoW does not translate
    r"(?:xx?-)?(?:small|medium|large)|"  # Pango size keywords
    r"\S*[/]World of Warcraft\S*|"  # the path shown as an example
    r"(?:BTC|TON|USDT(?: TRC20)?)[:]?|"  # currency tickers on the About tab
    r"GitHub[:] \S+|"  # a repository path
    r"(?:Andrey Yumashev|Pirson|WoW Translator|Buy Me a Coffee[^|]*)|"  # names and projects
    r"[A-Za-z0-9_+/=:-]{20,}|"  # opaque tokens: wallet addresses, key examples
    r"(?:DeepL|GigaChat|MyMemory|OPUS-MT|Microsoft Translator|BabelChat|WoW|Azure|Sber)"
    r"(?: [0-9]+(?:[.][0-9]+)*)?"  # ...optionally with a version number
    r")$"
)

# A string literal handed to something that draws it. The negative lookbehind
# matters: every one of these calls is *supposed* to receive tr("some.key"), and
# without it the key itself reads as hardcoded copy.
_WIDGET_TEXT = re.compile(
    r"(?:QCheckBox|QLabel|QPushButton|QGroupBox"
    r"|Gtk\.CheckButton|Gtk\.Label|Gtk\.Button|Gtk\.Expander|Gtk\.FileDialog"
    r"|setText|setToolTip|setPlaceholderText|addItem"
    # The GTK wizard builds every string through these, and leaving them out is
    # why it stayed entirely in English while the test was green.
    r"|set_label|set_markup|set_placeholder_text"
    r"|set_title|_section|_combo_row|_color_row|_scale_row|key_row|_title|_body)"
    # Either quote. The GTK modules use single quotes for anything containing
    # Pango markup, which is most of their status messages — reading only
    # double-quoted literals left every one of them invisible.
    r"\((?:[^()]{0,40}?)(?<!tr\()(['\"])((?:(?!\1).){4,}?)\1"
)


def _only_the_words(text: str) -> str:
    """What is left of a literal once composition is removed.

    An f-string is a template, not copy: `BabelChat {VERSION}` and
    `{tr('about.developer')} <b>Andrey Yumashev</b>` are assembling translated
    pieces and proper nouns, and reading them whole reports the whole template
    as untranslated English.
    """
    # The scan reads source, so "→" is six characters here — three of them
    # letters. Left in, an arrow glyph reads as untranslated English.
    # A literal backslash, escaped for the pattern: bare "\u" is read by re as
    # the start of a unicode escape and rejected for want of four hex digits.
    backslash = re.escape(chr(92))
    without_escapes = re.sub(backslash + r"(?:u[0-9a-fA-F]{4}|[nrt])", " ", text)
    without_fields = re.sub(r"\{[^{}]*\}", " ", without_escapes)
    without_markup = re.sub(r"<[^>]*>", " ", without_fields)
    # A literal split across source lines can end mid-tag; what is left is
    # an attribute list, not a sentence.
    without_markup = re.sub(r"<[^>]*$", " ", without_markup)
    return without_markup.strip()


@pytest.mark.parametrize("module", LOCALISED_MODULES)
def test_no_user_facing_string_is_written_straight_into_a_widget(module):
    """Seven of these shipped in the settings dialog — "Priority:", "Get key",
    "(other acts as fallback)" — and produced an interface half in English for
    every Russian-speaking user.

    A source scan only catches the literal-in-a-constructor shape. The test
    below walks the built interface, which is what actually reaches the user.
    """
    hardcoded = [
        text for _quote, text in _WIDGET_TEXT.findall(source(module)) if not _NOT_LANGUAGE.match(_only_the_words(text))
    ]
    assert hardcoded == [], f"{module} writes these past i18n: {hardcoded}"


# ── what the built interface actually says ───────────────────────────────────


def _vocabulary(language: str = "HU") -> set[str]:
    """Every string the table can render, including substitutions, plus the
    language names, which are shown in themselves on purpose."""
    from app.i18n import UI_LANGUAGES
    from app.languages import LANGUAGES as TRANSLATION_LANGUAGES

    rendered = set(UI_LANGUAGES.values()) | set(TRANSLATION_LANGUAGES.values())
    for values in _STRINGS.values():
        text = values.get(language, "")
        if not text:
            continue
        rendered.add(text)
        # A string with a placeholder reaches the screen already substituted, so
        # compare against its prefix rather than the template.
        head = re.split(r"\{\w+\}", text)[0].strip()
        if len(head) >= 4:
            rendered.add(head)
    return rendered


def _visible_texts(widget) -> list[str]:
    from PyQt6.QtWidgets import QWidget

    found = []
    for child in widget.findChildren(QWidget):
        for getter in ("text", "placeholderText", "title", "toolTip"):
            method = getattr(child, getter, None)
            if method is None:
                continue
            try:
                value = method()
            except TypeError:
                continue
            if isinstance(value, str) and value.strip():
                found.append(value.strip())
    return found


def _phrases(text: str) -> list[str]:
    """A rich-text label is several labels: `<b>Перевод:</b> MyMemory` holds a
    translated one and a brand name, and reading it whole hides either."""
    return [part.strip() for part in _strip_markup(text).split("  ") if part.strip()]


def _strip_markup(text: str) -> str:
    """Qt labels carry rich text, and exempting anything starting with a tag let
    `<b>Translation:</b> …` through — the one hardcoded English label on the
    wizard's final screen."""
    return re.sub(r"<[^>]+>", " ", text)


def _is_untranslated(text: str, vocabulary: set[str]) -> bool:
    text = _strip_markup(text).strip()
    if not text or _NOT_LANGUAGE.match(text):
        return False
    if text in vocabulary or any(text.startswith(known[:20]) for known in vocabulary if len(known) >= 20):
        return False
    # Accented Hungarian that is not matched verbatim is still Hungarian — a
    # label assembled from table pieces, a substituted placeholder. It is
    # English text that betrays a missed string.
    return not re.search(r"[áéíóöőúüűÁÉÍÓÖŐÚÜŰ]", text)


@pytest.mark.parametrize("dialog_name", ["settings", "wizard"])
def test_the_built_interface_shows_nothing_outside_the_table(dialog_name, monkeypatch):
    """The regression this shipped twice: copy declared as an i18n key and
    then rendered without translating it, so a provider key appeared on screen
    as a field label. A source scan cannot see that — the key IS a string
    constant in the provider file, correctly.

    So build the real dialog and read what it says: everything visible has to
    be a rendered table entry, a language name, or not language at all.
    """
    pytest.importorskip("PyQt6", reason="the Qt frontend is what this checks")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from app.config import AppConfig

    monkeypatch.setattr(tr, "_lang", "HU")

    app = QApplication.instance() or QApplication([])
    assert app is not None

    config = AppConfig(wow_path="")
    if dialog_name == "settings":
        from app.settings_dialog import SettingsDialog

        widget = SettingsDialog(config)
    else:
        from app.setup_wizard import SetupWizard

        widget = SetupWizard(config)

    vocabulary = _vocabulary()
    untranslated = sorted(
        {phrase for text in _visible_texts(widget) for phrase in _phrases(text) if _is_untranslated(phrase, vocabulary)}
    )
    widget.deleteLater()

    assert untranslated == [], f"the {dialog_name} shows: {untranslated}"


def test_the_translator_status_lines_are_in_the_table():
    """Settings and the wizard show one line about the local translator; every
    state it can be in has its own string."""
    for key in (
        "translator.status.ready",
        "translator.status.missing",
        "translator.status.will_convert",
        "translator.status.not_installed",
    ):
        assert key in _STRINGS, key
        assert tr(key).startswith("Fordító: OPUS-MT")


# ── the language has to be applied, not just chosen ──────────────────────────


def test_the_entry_point_applies_the_configured_ui_language():
    """Saving a language that never reaches `tr` is a control that does
    nothing — which is how one frontend used to behave.

    Read as whole statements rather than as lines: the argument is long
    enough to wrap, and a line scan would report an entry point that does this
    correctly as one that never does it at all.
    """
    text = (APP / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(text)

    calls = [
        ast.get_source_segment(text, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "set_language"
    ]

    assert calls, "main.py never applies the configured language"
    assert any("ui_language" in call for call in calls), calls


def test_the_overlay_takes_its_words_from_the_table():
    """The remaining literals are symbols and the product name, which are the
    same in every language."""
    text = source("overlay.py")

    assert "from app.i18n import tr" in text, "overlay.py does not use the string table"

    literals = [
        found for _quote, found in _WIDGET_TEXT.findall(text) if not _NOT_LANGUAGE.match(_only_the_words(found))
    ]

    assert literals == [], f"overlay.py draws these without translating them: {literals}"


def test_the_overlay_draws_the_shared_filter_tabs():
    """It once had its own hand-written list that never grew Custom or Emote,
    so messages from either appeared under no tab but All."""
    from app.config import FILTER_TABS

    names = [name for name, _key in FILTER_TABS]

    assert names[0] == "All"
    assert "Custom" in names and "Emote" in names
    assert "LookingForGroup" in names and "LFG" not in names
    assert len(names) == len(set(names)), f"a tab is listed twice: {names}"

    # The Qt filter bar lives in overlay_widgets.py since the overlay was split.
    assert "FILTER_TABS" in source("overlay_widgets.py"), "overlay_widgets.py keeps its own list"


# ── the table lives one file per language ────────────────────────────────────


def test_the_string_table_is_assembled_from_one_file_per_language():
    """It was a thousand-line literal in the middle of the module that renders
    it. One module per language keeps adding a language a matter of adding a
    file."""
    from app.locales import LANGUAGE_MODULES

    assert set(LANGUAGE_MODULES) == set(LANGUAGES)
    for language, module in LANGUAGE_MODULES.items():
        assert module.STRINGS, f"{language} has no strings"
        assert all(isinstance(text, str) for text in module.STRINGS.values())


def test_i18n_holds_the_mechanism_and_not_the_translations():
    """The point of the move. If the table drifts back into this module the
    file grows past the size cap again and the locale directory becomes a
    second copy."""
    text = source("i18n.py")

    assert "from app import locales" in text
    assert text.count('": "') < 5, "translations are being written into i18n.py again"
