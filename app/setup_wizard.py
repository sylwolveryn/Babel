"""First-run setup wizard for BabelChat — WoW-themed."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import ADDONS_RELATIVE, AppConfig, detect_wow_path
from app.i18n import tr
from app.qt_widgets import scrollable, size_to_content
from app.settings_dialog import (
    WOW_THEME_STYLESHEET,
    _create_dialog_icon,
    translator_status_text,
)
from app.wizard_pages_qt import build_ready_page, build_welcome_page
from app.wizard_style import GOLD_BTN_STYLE as _GOLD_BTN_STYLE

PAGE_WELCOME = 0
PAGE_WOW_PATH = 1
PAGE_READY = 2
TOTAL_PAGES = 3

# Gold-styled primary action button


class SetupWizard(QDialog):
    """First-run setup wizard with WoW-themed dark UI."""

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle(tr("wizard.title"))
        self.setWindowIcon(_create_dialog_icon())
        # Small enough for any screen; the pages scroll.
        self.setMinimumSize(550, 480)
        self.setStyleSheet(WOW_THEME_STYLESHEET)

        main_layout = QVBoxLayout(self)

        # Step indicator
        main_layout.addWidget(self._create_step_indicator())
        main_layout.addWidget(self._separator())

        # Stacked pages
        self._stack = QStackedWidget()
        # Every page behind a scroll area: a stack page that cannot scroll gets
        # squeezed instead, its fields rendered as slivers on a small screen.
        self._stack.addWidget(scrollable(self._create_welcome_page()))
        self._stack.addWidget(scrollable(self._create_wow_path_page()))
        self._stack.addWidget(scrollable(self._create_ready_page()))
        main_layout.addWidget(self._stack, stretch=1)

        # Navigation
        main_layout.addWidget(self._separator())
        nav = QHBoxLayout()

        self._cancel_btn = QPushButton(tr("wizard.cancel"))
        self._cancel_btn.clicked.connect(self.reject)
        nav.addWidget(self._cancel_btn)
        nav.addStretch()

        self._back_btn = QPushButton(tr("wizard.back"))
        self._back_btn.clicked.connect(self._go_back)
        nav.addWidget(self._back_btn)

        self._next_btn = QPushButton(tr("wizard.next"))
        self._next_btn.setStyleSheet(_GOLD_BTN_STYLE)
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)

        main_layout.addLayout(nav)
        self._update_navigation()
        size_to_content(self)

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _separator() -> QLabel:
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #444;")
        return sep

    # ── Step indicator ────────────────────────────────────────────

    def _create_step_indicator(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 8, 12, 8)

        self._step_dots: list[QLabel] = []
        for _ in range(TOTAL_PAGES):
            dot = QLabel()
            dot.setFixedSize(12, 12)
            layout.addWidget(dot)
            self._step_dots.append(dot)

        layout.addSpacing(8)
        self._step_text = QLabel("")
        self._step_text.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self._step_text)
        layout.addStretch()
        return widget

    def _update_step_indicator(self) -> None:
        current = self._stack.currentIndex()
        for i, dot in enumerate(self._step_dots):
            if i < current:
                dot.setStyleSheet("background: #997D00; border-radius: 6px;")
            elif i == current:
                dot.setStyleSheet("background: #FFD200; border-radius: 6px;")
            else:
                dot.setStyleSheet("background: #555; border-radius: 6px;")

        step_names = tr("wizard.steps").split("|")
        name = step_names[current] if current < len(step_names) else ""
        self._step_text.setText(tr("wizard.step_of", current=current + 1, total=TOTAL_PAGES, name=name))

    # ── Page 1: Welcome ──────────────────────────────────────────

    def _create_welcome_page(self) -> QWidget:
        return build_welcome_page(self)

    def _on_ui_lang_changed(self) -> None:
        lang = self._ui_lang_combo.currentData()
        if lang and lang != tr.get_language():
            tr.set_language(lang)
            self._config.ui_language = lang
            # Everything typed so far goes into the config first. Restarting is
            # how this wizard changes language, and the new one builds its
            # fields from the config — so anything not written here is simply
            # gone, like the WoW path browsed for on the next page. Same as
            # _finish does, for the same reason.
            self._config.wow_path = self._wow_path_input.text().strip()
            # Signal main to restart wizard with new language
            self._restart_requested = True
            self.done(2)  # Custom result code: restart

    # ── Page 2: WoW Path ─────────────────────────────────────────

    def _create_wow_path_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel(tr("wizard.wow.title"))
        title.setStyleSheet("color: #FFD200; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        layout.addSpacing(4)

        explain = QLabel(tr("wizard.wow.explain"))
        explain.setStyleSheet("color: #ccc; font-size: 12px;")
        explain.setWordWrap(True)
        layout.addWidget(explain)

        layout.addSpacing(12)

        # Path input + Browse
        path_row = QHBoxLayout()
        self._wow_path_input = QLineEdit(self._config.wow_path)
        self._wow_path_input.setPlaceholderText("C:/Program Files/World of Warcraft")
        path_row.addWidget(self._wow_path_input, stretch=1)

        browse_btn = QPushButton(tr("wizard.wow.browse"))
        browse_btn.clicked.connect(self._browse_wow_path)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Status
        self._wow_status_label = QLabel("")
        self._wow_status_label.setWordWrap(True)
        layout.addWidget(self._wow_status_label)

        layout.addSpacing(8)

        hint = QLabel(tr("wizard.wow.skip_hint"))
        hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint)

        layout.addStretch()
        return page

    def _auto_detect_wow(self) -> None:
        detected = detect_wow_path()
        if detected:
            self._wow_path_input.setText(detected)
            self._wow_status_label.setText(tr("wizard.wow.found"))
            self._wow_status_label.setStyleSheet("color: #40FF40; font-weight: bold;")
        else:
            self._wow_status_label.setText(tr("wizard.wow.not_found"))
            self._wow_status_label.setStyleSheet("color: #FF7F00; font-weight: bold;")

    def _browse_wow_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("wizard.wow.browse_title"))
        if path:
            self._wow_path_input.setText(path)
            self._wow_status_label.setText(tr("wizard.wow.path_set"))
            self._wow_status_label.setStyleSheet("color: #40FF40; font-weight: bold;")

    def _create_ready_page(self) -> QWidget:
        return build_ready_page(self)

    @staticmethod
    def _addon_source_path() -> Path:
        """Return path to bundled BabelChat addon folder."""
        if getattr(sys, "frozen", False):
            # PyInstaller onefile: data extracted to _MEIPASS temp dir
            base = Path(getattr(sys, "_MEIPASS", ""))
        else:
            base = Path(__file__).resolve().parent.parent
        return base / "addon" / "BabelChat"

    def _install_addon(self) -> None:
        wow = self._wow_path_input.text().strip()
        if not wow:
            self._addon_status_label.setText(tr("wizard.ready.addon_no_path"))
            self._addon_status_label.setStyleSheet("color: #FF4040; font-weight: bold;")
            return

        addons_dir = Path(wow) / ADDONS_RELATIVE
        if not addons_dir.parent.exists():
            self._addon_status_label.setText(tr("wizard.ready.addon_path_not_found", path=addons_dir.parent))
            self._addon_status_label.setStyleSheet("color: #FF4040; font-weight: bold;")
            return

        src = self._addon_source_path()
        if not src.exists():
            self._addon_status_label.setText(tr("wizard.ready.addon_files_missing"))
            self._addon_status_label.setStyleSheet("color: #FF4040; font-weight: bold;")
            return

        dest = addons_dir / "BabelChat"
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            self._addon_status_label.setText(tr("wizard.ready.addon_installed", dest=dest))
            self._addon_status_label.setStyleSheet("color: #40FF40; font-weight: bold;")
            self._install_addon_btn.setText(tr("wizard.ready.reinstall_addon"))
        except OSError as e:
            self._addon_status_label.setText(tr("addon.install_failed", detail=e))
            self._addon_status_label.setStyleSheet("color: #FF4040; font-weight: bold;")

    def _update_summary(self) -> None:
        """Summarise what the wizard is about to save, and the translator's state."""
        wow = self._wow_path_input.text() or tr("wizard.ready.not_configured")
        self._summary_label.setText(
            f"{translator_status_text()}<br>"
            f"<b>{tr('wizard.ready.wow_path')}</b> {wow}<br>"
            f"<b>{tr('wizard.ready.direction')}</b> {tr('wizard.ready.direction_value')}"
        )

    # ── Navigation ────────────────────────────────────────────────

    def _go_next(self) -> None:
        current = self._stack.currentIndex()
        if current == TOTAL_PAGES - 1:
            self._finish()
            return
        self._stack.setCurrentIndex(current + 1)
        self._on_page_entered(current + 1)
        self._update_navigation()

    def _go_back(self) -> None:
        current = self._stack.currentIndex()
        if current > 0:
            self._stack.setCurrentIndex(current - 1)
            self._on_page_entered(current - 1)
            self._update_navigation()

    def _on_page_entered(self, index: int) -> None:
        if index == PAGE_WOW_PATH:
            if not self._wow_path_input.text().strip():
                self._auto_detect_wow()
        elif index == PAGE_READY:
            self._update_summary()

    def _update_navigation(self) -> None:
        current = self._stack.currentIndex()

        self._back_btn.setVisible(current > 0)

        if current == TOTAL_PAGES - 1:
            self._next_btn.setText(tr("wizard.start"))
        else:
            self._next_btn.setText(tr("wizard.next"))

        self._next_btn.setEnabled(True)
        # Update summary on ready page if navigating back
        if current == PAGE_READY:
            self._update_summary()

        self._update_step_indicator()

    # ── Finalization ──────────────────────────────────────────────

    def _finish(self) -> None:
        self._config.wow_path = self._wow_path_input.text().strip()
        self._config.ui_language = tr.get_language()
        self._config.save()
        self.accept()

    def get_config(self) -> AppConfig:
        return self._config
