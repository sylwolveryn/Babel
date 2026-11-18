"""A language change has to reach the windows already on screen.

The overlay builds its chrome once and a widget keeps the string it was
constructed with, so setting the interface language changed nothing already
drawn. The setting appeared to do nothing at all until the next launch, which
is indistinguishable from a broken control.

The interface is Hungarian only for now, so today the refresh relabels in the
same language. It is kept because adding a second interface language is a new
locale module and a line in `app/locales/__init__.py` — and the refresh is the
part that would silently be missing.

Read from the source rather than by driving the widgets. That is weaker, and
it is written down because it is a choice: constructing `ChatOverlay` under
pytest once killed the interpreter outright — no traceback, no failure, the run
just stops. The behaviour was verified by hand instead, off-screen, with the
language switched under a live overlay: all five chrome labels and all
thirteen filter tabs followed, and the ON/OFF badge kept its state.

What the source can still be held to is the thing that actually rots: a label
added to the chrome and forgotten in the refresh.
"""

from __future__ import annotations

import ast
import pathlib
import re

from app.i18n import UI_LANGUAGES

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app"

#: `tr("some.key")` anywhere in a source file.
TR_KEY = re.compile(r'tr\(\s*"([^"]+)"')


def source_of(module: str) -> str:
    return (APP / module).read_text(encoding="utf-8")


def method_source(module: str, name: str) -> str:
    """The text of one method, or "" when the module does not define it."""
    text = source_of(module)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node) or ""
    return ""


# ── the overlay can do it at all ─────────────────────────────────────────────


def test_the_overlay_can_relabel_itself():
    assert method_source("overlay.py", "apply_language"), "overlay.py cannot relabel itself"


def test_the_entry_point_calls_it_when_settings_are_saved():
    """A refresh that exists and is never called is the same bug with more
    code in it."""
    text = source_of("main.py")
    calls = {ast.get_source_segment(text, node) for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Call)}

    assert "overlay.apply_language()" in calls, "main.py never refreshes the overlay"


# ── and neither leaves a label behind ────────────────────────────────────────


def test_every_label_the_qt_chrome_builds_is_refreshed():
    """The failure mode this guards is not today's code, it is next year's: a
    label added to the toolbar and forgotten here shows up as one stale
    word among fresh ones, which nobody reports as a bug."""
    built = set(TR_KEY.findall(source_of("overlay_chrome.py")))
    refreshed = method_source("overlay.py", "apply_language")

    missing = sorted(key for key in built if key not in refreshed)

    assert built, "no translated labels found — has the chrome moved?"
    assert missing == [], f"built by the chrome and never refreshed: {missing}"


def test_the_clipboard_dialog_is_refreshed_too():
    """It is a separate window, created on demand by the hotkey and then kept,
    so it outlives the setting changed after it — and being separate is exactly
    why it was missed."""
    refresh = method_source("overlay.py", "apply_language")

    assert "self._reply_dialog.apply_language()" in refresh
    assert method_source("overlay_reply.py", "apply_language"), "the dialog cannot relabel itself"


def test_the_tray_menu_is_refreshed_too():
    """The tray is the one window a user cannot close and reopen to get the new
    language — it is only ever built once, at startup."""
    text = source_of("main.py")
    calls = {
        ast.get_source_segment(text, node)
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.Call)
    }

    assert "tray.apply_language()" in calls, "the tray menu keeps the old language"
    assert method_source("tray.py", "apply_language"), "the tray cannot relabel itself"


def test_the_qt_refresh_reaches_the_filter_tabs():
    """They are built from the shared FILTER_TABS declaration, so their keys
    are not in the chrome's source to be matched above — the bar relabels
    itself and the overlay has to ask it to."""
    assert "self._filter_bar.apply_language()" in method_source("overlay.py", "apply_language")
    assert method_source("overlay_widgets.py", "apply_language"), "the filter bar cannot relabel"


def test_the_widgets_the_qt_refresh_touches_are_kept_somewhere():
    """Two of them were locals in a builder function, so the refresh could
    name them but never reach them — an AttributeError on every settings
    save."""
    # Assigned by the chrome builder as `overlay._x`, or by the overlay itself
    # as `self._x` — the lazily created clipboard dialog is the second kind.
    assigned = set(re.findall(r"overlay\.(_\w+)\s*=", source_of("overlay_chrome.py")))
    assigned |= set(re.findall(r"self\.(_\w+)\s*=", source_of("overlay.py")))

    refresh = method_source("overlay.py", "apply_language")
    # Widgets only — those the refresh calls a method on. `_translation_enabled`
    # is read as a value, not sent a message.
    attributes = set(re.findall(r"self\.(_\w+)\.", refresh))

    assert attributes, "the refresh touches no widgets at all"
    for attribute in attributes:
        assert attribute in assigned, (
            f"apply_language calls self.{attribute}, which nothing ever assigns"
        )


def test_the_badge_is_refreshed_from_its_state_not_from_the_table_alone():
    """It is the one label whose text depends on more than the language.
    Writing the "on" string unconditionally would show a stopped translation
    as running, or the reverse — the label and the behaviour disagreeing is
    worse than the label being stale."""
    refresh = method_source("overlay.py", "apply_language")

    assert "overlay.badge.on" in refresh and "overlay.badge.off" in refresh
    assert "_translation_enabled" in refresh, "the badge is relabelled without consulting its state"


# ── the wizard offers what the app actually has ──────────────────────────────


def test_the_language_table_has_the_shape_that_call_produces():
    """The language dropdowns unpack (code, label) pairs and look codes up in
    upper case. A table shaped any other way fails at wizard startup."""
    pairs = list(UI_LANGUAGES.items())

    assert pairs, "no interface language at all"
    for code, label in pairs:
        assert code == code.upper(), f"{code!r} is not the upper-case form the lookup uses"
        assert label and label != code, f"{code!r} has no name to show in the dropdown"


# ── what the wizard remembers ────────────────────────────────────────────────


def test_the_qt_wizard_keeps_what_was_typed_across_a_language_change():
    """Changing the language restarts this wizard, and the new one builds its
    fields from the config — so anything not written to the config first is
    gone, like the WoW path browsed for on page two."""
    handler = method_source("setup_wizard.py", "_on_ui_lang_changed")

    assert handler, "the language handler has moved"
    assert "wow_path" in handler, "the entered WoW path is dropped on restart"
