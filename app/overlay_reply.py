"""The reply box: type in your own language, and Enter translates and sends it.

The translation goes to the addon (app/game_sender.py), which says it on the
channel picked in the toolbar — one message for each Enter the player
presses, nothing sent on its own. When it cannot be sent (WoW is not running,
the addon is off), it lands on the clipboard instead, to paste by hand.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThreadPool, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.game_sender import CHANNELS, GameSender
from app.i18n import tr
from app.overlay_chrome import _EDGE_MARGIN
from app.overlay_widgets import ReplySendWorker, ReplyTranslateWorker
from app.translator import TranslatorService

#: How long the 'copied' confirmation stays on screen.
_COPIED_FLASH_MS = 2000
#: How long 'sent' stays on screen; an error stays until the next message.
_SENT_FLASH_MS = 3000
_CHANNEL_LABELS = dict(CHANNELS)
_OK_STYLE = "color: #40FF40; font-size: 10px; font-weight: bold;"
_ERROR_STYLE = "color: #FF6060; font-size: 10px; font-weight: bold;"


class ReplyDialog(QWidget):
    """Floating reply translator panel — separate window for Linux keyboard input.

    On Linux with X11BypassWindowManagerHint, child QLineEdit widgets don't
    receive keyboard events. This panel lives in a separate normal window
    that does receive keyboard input, positioned to float below the overlay.
    """

    translate_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        # A normal (non-Tool) window is required on Wayland: Qt.Tool windows are
        # treated as auxiliary surfaces that the compositor will not grant
        # keyboard focus to, so the input field could never be typed into.
        # A frameless, stays-on-top normal Window can be activated and focused.
        super().__init__(
            parent, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Must NOT show-without-activating: the dialog needs to be activatable so
        # it can receive keyboard focus when the user interacts with it.
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self._translator: TranslatorService | None = None
        self._target_lang: str = "EN"
        self._thread_pool = QThreadPool.globalInstance()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        panel.setStyleSheet(
            "background: rgba(0, 0, 0, 180); border-top: 1px solid #333; border-radius: 0px 0px 4px 4px;"
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(4, 4, 4, 4)
        panel_layout.setSpacing(3)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(4)
        self._reply_input = QLineEdit()
        self._reply_input.setPlaceholderText(tr("overlay.reply.input_hint"))
        self._reply_input.setMaxLength(255)
        self._reply_input.setStyleSheet(
            "QLineEdit { background: #111; color: #e0e0e0; border: 1px solid #555; "
            "border-radius: 3px; padding: 4px 6px; font-size: 11px; }"
            "QLineEdit:focus { border-color: #FFD200; }"
        )
        self._reply_input.returnPressed.connect(self._do_translate)
        input_row.addWidget(self._reply_input)

        enter_btn = QPushButton("\u23ce")
        enter_btn.setFixedSize(24, 24)
        enter_btn.setStyleSheet(
            "QPushButton { color: #555; font-size: 14px; background: transparent; "
            "border: 1px solid transparent; border-radius: 3px; }"
            "QPushButton:hover { color: #FFD200; border-color: #FFD200; }"
        )
        enter_btn.clicked.connect(self._do_translate)
        input_row.addWidget(enter_btn)

        panel_layout.addLayout(input_row)

        # Result row
        result_row = QHBoxLayout()
        result_row.setSpacing(4)
        self._reply_output = QLineEdit()
        self._reply_output.setReadOnly(True)
        self._reply_output.setStyleSheet(
            "QLineEdit { background: #0a0a0a; color: #FFD200; border: 1px solid #444; "
            "border-radius: 3px; padding: 4px 6px; font-size: 11px; }"
        )
        result_row.addWidget(self._reply_output)

        self._copy_btn = QPushButton(tr("overlay.reply.copy"))
        self._copy_btn.setFixedHeight(24)
        self._copy_btn.setStyleSheet(
            "QPushButton { background: rgba(60,60,60,200); color: #ccc; "
            "border: 1px solid #555; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { color: #FFD200; border-color: #FFD200; }"
        )
        self._copy_btn.clicked.connect(self._copy_result)
        result_row.addWidget(self._copy_btn)

        panel_layout.addLayout(result_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color: #40FF40; font-size: 10px; font-weight: bold;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignRight)
        panel_layout.addWidget(self._status)

        layout.addWidget(panel)

    def apply_language(self) -> None:
        """Relabel what this window was built with, after a language change.

        It is created lazily — by the clipboard hotkey, or the first time the
        reply panel is opened — and then kept, so it outlives the setting that
        was changed after it. Only the two labels built here: the status line
        and the output field are written on every action and arrive in the new
        language by themselves.
        """
        self._reply_input.setPlaceholderText(tr("overlay.reply.input_hint"))
        self._copy_btn.setText(tr("overlay.reply.copy"))

    def set_translator(self, translator: TranslatorService, target_lang: str) -> None:
        self._translator = translator
        self._target_lang = target_lang

    def activate_input(self) -> None:
        """Bring the dialog forward and grab keyboard focus for the input.

        On Wayland the compositor only grants keyboard focus on an explicit
        activation request, so showing the window is not enough — we must
        raise + activate + focus the field together.
        """
        self.show()
        self.raise_()
        self.activateWindow()
        self._reply_input.setFocus(Qt.FocusReason.MouseFocusReason)

    def mousePressEvent(self, event: object) -> None:
        # Clicking anywhere in the dialog should activate it so the user can
        # type — Wayland will not focus a window the user hasn't interacted with.
        self.activateWindow()
        self._reply_input.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)  # type: ignore[misc]

    def _do_translate(self) -> None:
        text = self._reply_input.text().strip()
        if not text or self._translator is None:
            return
        self._reply_output.setText(tr("overlay.reply.translating"))
        self._reply_input.setEnabled(False)
        worker = ReplyTranslateWorker(self._translator, text, self._target_lang)
        worker.signals.finished.connect(self._on_translated)
        self._thread_pool.start(worker)

    @pyqtSlot(str, bool)
    def _on_translated(self, translated: str, success: bool) -> None:
        self._reply_input.setEnabled(True)
        if success:
            self._reply_output.setText(translated)
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(translated)
            self._status.setText(tr("overlay.reply.copied"))
            QTimer.singleShot(_COPIED_FLASH_MS, lambda: self._status.setText(""))
        else:
            self._reply_output.setText(tr("overlay.reply.error"))

    def translate_clipboard(self) -> None:
        """Translate whatever is on the clipboard and put the result back.

        The hotkey for this has been configurable, saved and shown with a hint
        describing exactly this since the setting was added — and nothing ever
        registered it. A key combination a user assigned and pressed, that did
        nothing, with no error.
        """
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        text = clipboard.text().strip()
        if not text or self._translator is None:
            self._status.setText(tr("overlay.clipboard.empty"))
            QTimer.singleShot(_COPIED_FLASH_MS, lambda: self._status.setText(""))
            return

        self._status.setText(tr("overlay.reply.translating"))
        worker = ReplyTranslateWorker(self._translator, text, self._target_lang)
        worker.signals.finished.connect(self._on_clipboard_translated)
        self._thread_pool.start(worker)

    @pyqtSlot(str, bool)
    def _on_clipboard_translated(self, translated: str, success: bool) -> None:
        if not success:
            self._status.setText(tr("overlay.reply.error"))
            return
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(translated)
        self._status.setText(tr("overlay.clipboard.done"))
        QTimer.singleShot(_COPIED_FLASH_MS, lambda: self._status.setText(""))

    def _copy_result(self) -> None:
        text = self._reply_output.text()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
            self._status.setText(tr("overlay.reply.copied"))
            QTimer.singleShot(_COPIED_FLASH_MS, lambda: self._status.setText(""))


class ReplyPanelMixin:
    """The outgoing half of the overlay: type here, Enter translates and sends.

    Split out of ChatOverlay because it is a different job from showing the
    chat — everything above this line is about what other people said, and
    everything below is about what you are about to say. The overlay module had
    grown past the size the project caps files at, and this was the seam.

    The attributes it uses (`_translator`, `_reply_input`, `_reply_output` and
    the rest) are built by app/overlay_chrome.py and set up in ChatOverlay's
    constructor; the mixin is not usable on its own.
    """

    def set_translator(self, translator: TranslatorService, target_lang: str) -> None:
        """Provide the translator service and target language for reply translation."""
        self._translator = translator
        self._target_lang = target_lang
        if self._reply_dialog is not None:
            self._reply_dialog.set_translator(translator, target_lang)

    def _on_reply_focus_in(self, event: object) -> None:
        """Temporarily remove X11BypassWindowManagerHint so keyboard input works."""
        pos = self.pos()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.move(pos)
        self.show()
        self._reply_input.setFocus()

    def _on_reply_focus_out(self, event: object) -> None:
        """Restore X11BypassWindowManagerHint when input loses focus."""
        pos = self.pos()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.X11BypassWindowManagerHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.move(pos)
        self.show()

    def _do_reply_translate(self) -> None:
        text = self._reply_input.text().strip()
        if not text or self._translator is None:
            return
        self._reply_output.setText(tr("overlay.reply.translating"))
        self._reply_input.setEnabled(False)
        worker = ReplyTranslateWorker(self._translator, text, self._target_lang)
        worker.signals.finished.connect(self._on_reply_translated)
        self._thread_pool.start(worker)

    def _send_target(self) -> tuple[str, str]:
        """The channel picked in the toolbar, and the whisper name if any."""
        channel = self._channel_combo.currentData() or "SAY"
        name = self._whisper_input.text().strip() if channel == "WHISPER" else ""
        return channel, name

    def _on_whisper_name_edited(self, text: str) -> None:
        # Typing a name means "whisper them": pick Whisper so the name is used.
        if text.strip():
            self._channel_combo.setCurrentIndex(self._channel_combo.findData("WHISPER"))

    def _show_reply_status(self, text: str, ok: bool) -> None:
        self._reply_status.setStyleSheet(_OK_STYLE if ok else _ERROR_STYLE)
        self._reply_status.setText(text)
        if ok:
            QTimer.singleShot(
                _SENT_FLASH_MS, lambda: self._reply_status.text() == text and self._reply_status.setText("")
            )

    @pyqtSlot(str, bool)
    def _on_reply_translated(self, translated: str, success: bool) -> None:
        if not success:
            self._reply_input.setEnabled(True)
            self._reply_output.setText(tr("overlay.reply.error"))
            return
        self._reply_output.setText(translated)
        channel, name = self._send_target()
        if channel == "WHISPER" and not name:
            self._reply_input.setEnabled(True)
            self._copy_to_clipboard(translated)
            self._show_reply_status(tr("overlay.reply.need_name"), ok=False)
            return
        label = _CHANNEL_LABELS.get(channel, channel) + (f" → {name}" if name else "")
        self._show_reply_status(tr("overlay.reply.sending", channel=label), ok=True)
        if self._game_sender is None:
            self._game_sender = GameSender()
        worker = ReplySendWorker(self._game_sender, channel, name, translated, label)
        worker.signals.finished.connect(self._on_reply_sent)
        self._thread_pool.start(worker)

    @pyqtSlot(str, str, str)
    def _on_reply_sent(self, translated: str, label: str, error: str) -> None:
        self._reply_input.setEnabled(True)
        self._reply_input.setFocus()
        if error:
            self._copy_to_clipboard(translated)
            self._show_reply_status(tr("overlay.reply.send_failed", error=error), ok=False)
            return
        self._reply_input.clear()
        self._show_reply_status(tr("overlay.reply.sent", channel=label), ok=True)

    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    # -- Drag & resize support --

    _EDGE_CURSORS: dict[str, Qt.CursorShape] = {
        "br": Qt.CursorShape.SizeFDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "b": Qt.CursorShape.SizeVerCursor,
        "t": Qt.CursorShape.SizeVerCursor,
        "r": Qt.CursorShape.SizeHorCursor,
        "l": Qt.CursorShape.SizeHorCursor,
    }

    # -- Settings persistence --

    def _position_reply_dialog(self) -> None:
        """Position the reply dialog flush below the overlay's visible content."""
        if self._reply_dialog is None:
            return
        geo = self.geometry()
        # Subtract edge margin so dialog sits flush against the visible container
        self._reply_dialog.move(geo.left() + _EDGE_MARGIN, geo.bottom() - _EDGE_MARGIN)
        self._reply_dialog.resize(geo.width() - _EDGE_MARGIN * 2, self._reply_dialog.sizeHint().height())
