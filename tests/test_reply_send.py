"""Enter in the reply box translates and sends to the channel in the toolbar."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from app.config import AppConfig
from app.game_sender import SendError


class FakeSender:
    def __init__(self, error: str = ""):
        self.calls: list[tuple[str, str, str]] = []
        self.error = error

    def send(self, channel, target, text):
        self.calls.append((channel, target, text))
        if self.error:
            raise SendError(self.error)


@pytest.fixture
def overlay():
    from app.overlay import ChatOverlay

    app = QApplication.instance() or QApplication([])
    assert app is not None
    widget = ChatOverlay(AppConfig(wow_path=""))
    widget.resize(600, 320)
    widget.show()
    QApplication.processEvents()
    yield widget
    widget.deleteLater()


def finish(overlay) -> None:
    overlay._thread_pool.waitForDone(5000)
    for _ in range(5):
        QApplication.processEvents()


def toolbar_order(overlay) -> list:
    layout = overlay._toolbar.layout()
    return [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]


def test_channel_picker_and_whisper_box_sit_between_settings_and_opacity(overlay):
    widgets = toolbar_order(overlay)
    assert widgets[:4] == [
        overlay._settings_btn,
        overlay._channel_combo,
        overlay._whisper_input,
        overlay._opacity_label,
    ]
    assert overlay._whisper_input.placeholderText() == "Suttogás neki"


def test_say_is_the_default_and_every_channel_is_offered(overlay):
    assert overlay._channel_combo.currentData() == "SAY"
    offered = [overlay._channel_combo.itemData(i) for i in range(overlay._channel_combo.count())]
    for channel in ("YELL", "WHISPER", "REPLY", "PARTY", "RAID", "RAID_WARNING", "BATTLEGROUND", "GUILD", "OFFICER"):
        assert channel in offered
    for channel in ("CHANNEL:1", "CHANNEL:2", "CHANNEL:3", "CHANNEL:4", "CHANNEL:World"):
        assert channel in offered


def test_the_copy_button_is_gone(overlay):
    assert not hasattr(overlay, "_reply_copy_btn")


def test_a_translated_reply_goes_to_the_picked_channel(overlay):
    overlay._game_sender = FakeSender()
    overlay._channel_combo.setCurrentIndex(overlay._channel_combo.findData("GUILD"))
    overlay._reply_input.setText("Szia")
    overlay._on_reply_translated("Hi", True)
    finish(overlay)
    assert overlay._game_sender.calls == [("GUILD", "", "Hi")]
    assert overlay._reply_input.text() == ""
    assert "Elküldve" in overlay._reply_status.text()


def test_typing_a_name_picks_whisper_and_sends_to_them(overlay):
    overlay._game_sender = FakeSender()
    overlay._whisper_input.setText("Jaina")
    overlay._on_whisper_name_edited("Jaina")
    assert overlay._channel_combo.currentData() == "WHISPER"
    overlay._on_reply_translated("Hi", True)
    finish(overlay)
    assert overlay._game_sender.calls == [("WHISPER", "Jaina", "Hi")]


def test_reply_ignores_the_whisper_name(overlay):
    overlay._game_sender = FakeSender()
    overlay._whisper_input.setText("Jaina")
    overlay._channel_combo.setCurrentIndex(overlay._channel_combo.findData("REPLY"))
    overlay._on_reply_translated("Hi", True)
    finish(overlay)
    assert overlay._game_sender.calls == [("REPLY", "", "Hi")]


def test_whisper_without_a_name_is_not_sent(overlay):
    overlay._game_sender = FakeSender()
    overlay._channel_combo.setCurrentIndex(overlay._channel_combo.findData("WHISPER"))
    overlay._on_reply_translated("Hi", True)
    finish(overlay)
    assert overlay._game_sender.calls == []
    assert "kinek suttogsz" in overlay._reply_status.text()


def test_a_failed_send_keeps_the_text_and_puts_the_translation_on_the_clipboard(overlay):
    overlay._game_sender = FakeSender(error="A WoW nem fut.")
    overlay._reply_input.setText("Szia")
    overlay._on_reply_translated("Hi", True)
    finish(overlay)
    assert overlay._reply_input.text() == "Szia"
    assert "A WoW nem fut." in overlay._reply_status.text()
    assert QApplication.clipboard().text() == "Hi"
