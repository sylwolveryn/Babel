"""The settings window has to fit on the screen and show what it renders.

Both defects here were reported by looking at the window, not by anything
failing: a status figure was half cut off, and the dialog could not be made
short enough to fit a laptop screen. Neither raises, so neither had a test.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt6", reason="this is the Qt frontend")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from app.config import AppConfig  # noqa: E402
from app.i18n import tr  # noqa: E402

#: The shortest screen worth supporting, minus a taskbar. A 1366x768 laptop is
#: still the second most common resolution among PC players.
SMALL_SCREEN = (1366, 700)


@pytest.fixture
def dialog(monkeypatch):
    from app.settings_dialog import SettingsDialog

    monkeypatch.setattr(tr, "_lang", "HU")
    app = QApplication.instance() or QApplication([])
    assert app is not None

    widget = SettingsDialog(AppConfig(wow_path=""))
    yield widget
    widget.deleteLater()


def visible_labels(widget: QWidget) -> list[QLabel]:
    return [
        label
        for label in widget.findChildren(QLabel)
        if label.isVisibleTo(widget) and label.text().strip() and not label.text().startswith("<")
    ]


# ── it has to fit ────────────────────────────────────────────────────────────


def test_the_window_can_be_made_small_enough_for_a_laptop(dialog):
    """With four translators to configure the General tab needed 1020px, and the
    dialog had no scroll area — so on any screen below about 1100px the Save
    button sat past the bottom edge with no way to reach it."""
    width, height = SMALL_SCREEN
    minimum = dialog.minimumSizeHint()

    assert minimum.height() <= height, f"the dialog cannot be shorter than {minimum.height()}px"
    assert minimum.width() <= width, f"the dialog cannot be narrower than {minimum.width()}px"


def test_every_tab_scrolls(dialog):
    """A tab that does not scroll is a tab whose contents get squeezed instead,
    which is how an 11px caption ended up in a 9px box."""
    from PyQt6.QtWidgets import QScrollArea, QTabWidget

    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None

    not_scrolling = [
        tabs.tabText(index) for index in range(tabs.count()) if not isinstance(tabs.widget(index), QScrollArea)
    ]

    assert not_scrolling == [], f"these tabs cannot scroll: {not_scrolling}"


# ── and it has to show what it renders ───────────────────────────────────────


def test_no_label_is_shorter_than_the_text_inside_it(dialog):
    """A quota figure was once rendered into a 9px box in an 11px font, so its
    bottom half was cut off — visible to the user, invisible to every test."""
    dialog.resize(*SMALL_SCREEN)
    dialog.show()
    QApplication.processEvents()

    clipped = [
        (label.text()[:40], label.height(), label.fontMetrics().height())
        for label in visible_labels(dialog)
        if label.height() < label.fontMetrics().height()
    ]

    assert clipped == [], f"text taller than the box it is drawn in: {clipped}"


def test_the_translator_status_is_one_read_only_line(dialog):
    """OPUS-MT is the only translator, so the dialog says how it is and offers
    nothing to change."""
    from app.settings_dialog import translator_status_text

    label = dialog._translator_status
    assert label.text() == translator_status_text()
    assert label.text().startswith("Fordító: OPUS-MT")


@pytest.mark.parametrize("build_name", ["SettingsDialog", "SetupWizard"])
def test_there_is_no_provider_selector_or_credential_field(build_name, monkeypatch):
    """The provider list, its credential fields and the "preferred translator"
    combo box are gone; nothing in either window may bring them back."""
    from PyQt6.QtWidgets import QComboBox, QLineEdit

    import app.settings_dialog as settings_module
    import app.setup_wizard as wizard_module

    monkeypatch.setattr(tr, "_lang", "HU")
    app = QApplication.instance() or QApplication([])
    assert app is not None

    build = getattr(settings_module, build_name, None) or getattr(wizard_module, build_name)
    window = build(AppConfig(wow_path=""))
    try:
        assert not hasattr(window, "_provider_group")
        secret = [edit for edit in window.findChildren(QLineEdit) if edit.echoMode() != QLineEdit.EchoMode.Normal]
        assert secret == [], "a password-style field is back"
        combos = [combo.objectName() or combo.currentText() for combo in window.findChildren(QComboBox)]
        offered = [
            combo.itemText(i) for combo in window.findChildren(QComboBox) for i in range(combo.count())
        ]
        assert not any("OPUS-MT" in text or "MyMemory" in text for text in offered), combos
    finally:
        window.deleteLater()


def test_the_provider_settings_module_is_gone():
    from pathlib import Path

    app_dir = Path(__file__).resolve().parent.parent / "app"
    assert not (app_dir / "provider_settings_qt.py").exists()
    assert not (app_dir / "translators" / "mymemory_provider.py").exists()


# ── the wizard, which every fresh install goes through ───────────────────────


@pytest.fixture
def wizard(monkeypatch):
    from app.setup_wizard import SetupWizard

    monkeypatch.setattr(tr, "_lang", "HU")
    app = QApplication.instance() or QApplication([])
    assert app is not None

    widget = SetupWizard(AppConfig(wow_path=""))
    yield widget
    widget.deleteLater()


def test_the_wizard_fits_the_screen_it_declares_it_fits(wizard):
    """It declared a 550x480 minimum while its layout demanded 1241x767 in
    Russian. A Qt layout short of vertical space does not clip, it squeezes —
    so the declared minimum was not a size the window worked at, it was a size
    the window was broken at."""
    minimum = wizard.minimumSizeHint()
    declared = wizard.minimumSize()

    assert minimum.height() <= max(declared.height(), 1), (
        f"the layout needs {minimum.height()}px but the window says it works at {declared.height()}px"
    )
    assert minimum.width() <= max(declared.width(), 1)


def test_the_wizard_has_three_pages(wizard):
    """Welcome, WoW folder, Ready — the translator page went with the choice of
    translator."""
    from app.setup_wizard import PAGE_READY, PAGE_WELCOME, PAGE_WOW_PATH, TOTAL_PAGES

    assert (PAGE_WELCOME, PAGE_WOW_PATH, PAGE_READY, TOTAL_PAGES) == (0, 1, 2, 3)
    assert wizard._stack.count() == TOTAL_PAGES
    assert len(tr("wizard.steps").split("|")) == TOTAL_PAGES


def test_the_ready_page_says_how_the_translator_is(wizard):
    from app.settings_dialog import translator_status_text
    from app.setup_wizard import PAGE_READY

    wizard._stack.setCurrentIndex(PAGE_READY)
    wizard._on_page_entered(PAGE_READY)

    assert translator_status_text() in wizard._summary_label.text()


def test_every_wizard_page_scrolls(wizard):
    """A page that cannot scroll is a page whose contents get squeezed."""
    from PyQt6.QtWidgets import QScrollArea

    not_scrolling = [
        index for index in range(wizard._stack.count()) if not isinstance(wizard._stack.widget(index), QScrollArea)
    ]

    assert not_scrolling == [], f"pages that cannot scroll: {not_scrolling}"


@pytest.mark.parametrize("language", ["HU"])
def test_neither_window_demands_more_room_than_a_laptop_has(language, monkeypatch):
    """Checked in every language, because the longest translation decides."""
    from app.settings_dialog import SettingsDialog
    from app.setup_wizard import SetupWizard

    monkeypatch.setattr(tr, "_lang", language)
    app = QApplication.instance() or QApplication([])
    assert app is not None

    width, height = SMALL_SCREEN
    for build in (SettingsDialog, SetupWizard):
        window = build(AppConfig(wow_path=""))
        minimum = window.minimumSizeHint()
        window.deleteLater()
        assert minimum.height() <= height, f"{build.__name__} in {language} needs {minimum.height()}px"
        assert minimum.width() <= width, f"{build.__name__} in {language} needs {minimum.width()}px"


# ── the window opens wide enough to read ─────────────────────────────────────


@pytest.mark.parametrize("build_name", ["SettingsDialog", "SetupWizard"])
def test_the_window_opens_at_the_width_of_its_content(build_name, monkeypatch):
    """A scroll area reports a small size hint whatever it holds, and horizontal
    scrolling is off on purpose — so a window sized from its own hint opened
    narrower than its rows and clipped their right-hand side with nothing to
    scroll. The first screenshot of the old provider page showed exactly that."""
    from PyQt6.QtWidgets import QScrollArea

    import app.settings_dialog as settings_module
    import app.setup_wizard as wizard_module

    monkeypatch.setattr(tr, "_lang", "HU")
    app = QApplication.instance() or QApplication([])
    assert app is not None

    build = getattr(settings_module, build_name, None) or getattr(wizard_module, build_name)
    window = build(AppConfig(wow_path=""))
    try:
        contents = [area.widget() for area in window.findChildren(QScrollArea) if area.widget() is not None]
        assert contents, "nothing scrollable to measure"
        # What the rows need, not what a word-wrapped paragraph claims it needs
        # on one line — that is twelve hundred pixels, and wrapping is exactly
        # what those labels are for.
        from app.qt_widgets import content_width

        widest = max(content_width(content) for content in contents)

        assert window.width() >= widest, f"opens at {window.width()}px against {widest}px of rows"
    finally:
        window.deleteLater()


def test_no_button_is_narrower_than_the_glyph_on_it(dialog):
    """The reveal button was fixed at 30px against a 42px glyph and rendered as
    an empty box."""
    from PyQt6.QtWidgets import QPushButton

    dialog.resize(*SMALL_SCREEN)
    dialog.show()
    QApplication.processEvents()

    squashed = [
        (button.text(), button.sizeHint().width(), button.width())
        for button in dialog.findChildren(QPushButton)
        if button.isVisible() and button.text() and button.sizeHint().width() > button.width() + 2
    ]

    assert squashed == [], f"buttons narrower than their own labels: {squashed}"
