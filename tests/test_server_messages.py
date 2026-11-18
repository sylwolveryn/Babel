"""Server messages (CHAT_MSG_SYSTEM) reach the overlay as their own channel."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from app.addon_protocol import make_synthetic_log_line
from app.config import AppConfig, enabled_channels
from app.parser import Channel, parse_line


def system(text: str):
    return parse_line(make_synthetic_log_line("SYSTEM", "", text))


def test_a_server_announcement_is_a_system_message():
    msg = system("|cffff0000[SERVER]|r Restart in 5 minutes")
    assert msg.channel == Channel.SYSTEM
    assert msg.text == "[SERVER] Restart in 5 minutes"


@pytest.mark.parametrize("text", ["Thrall has come online.", "Jaina has gone offline."])
def test_online_and_offline_noise_is_still_dropped(text):
    assert system(text) is None


def test_server_messages_are_on_by_default():
    assert Channel.SYSTEM in enabled_channels(AppConfig())


def test_server_messages_can_be_switched_off():
    assert Channel.SYSTEM not in enabled_channels(AppConfig(channels_system=False))


def test_the_overlay_shows_it_without_an_author():
    from app.overlay import ChatOverlay
    from app.pipeline import TranslatedMessage

    app = QApplication.instance() or QApplication([])
    assert app is not None
    overlay = ChatOverlay(AppConfig(wow_path=""))
    overlay.add_message(TranslatedMessage(original=system("Welcome to ChromieCraft!"), translation=None))
    shown = overlay._chat_area.toPlainText()
    overlay.deleteLater()
    assert "[Szerver] Welcome to ChromieCraft!" in shown
    assert "Server:" not in shown
