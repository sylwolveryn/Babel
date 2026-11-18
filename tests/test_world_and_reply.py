"""The World channel, the reply direction and the fixed language pair."""

from __future__ import annotations

import json

import pytest

from app.addon_protocol import classify_public_channel, make_synthetic_log_line
from app.config import AppConfig, enabled_channels
from app.parser import Channel


@pytest.mark.parametrize("name", ["World", "world", "5. World", "World - Dalaran"])
def test_the_world_channel_is_recognised_whatever_the_client_calls_it(name):
    assert classify_public_channel(0, name) == "World"
    assert classify_public_channel(None, name) == "World"


def test_other_player_made_channels_stay_custom():
    assert classify_public_channel(0, "WorldOfGuild") == "Custom"
    assert classify_public_channel(0, "hungary") == "Custom"


def test_a_world_line_reaches_the_parser_as_world():
    from app.parser import parse_line

    line = make_synthetic_log_line("CHANNEL:0:World", "Thrall", "lf tank icc")
    message = parse_line(line)
    assert message is not None
    assert message.channel == Channel.WORLD


def test_world_is_translated_by_default():
    assert AppConfig().channels_world is True
    assert Channel.WORLD in enabled_channels(AppConfig())


def test_the_reply_is_written_in_hungarian_and_sent_in_english():
    from app.overlay_widgets import reply_source_for

    assert AppConfig().reply_language == "EN"
    assert reply_source_for("EN") == "HU"
    assert reply_source_for("HU") == "EN"


def test_the_reply_always_names_its_source_language():
    """The translator has no auto-detect: OPUS-MT picks its model by the pair,
    and a request without a source fails — which is what the reply box used
    to send."""
    from PyQt6.QtWidgets import QApplication

    from app.overlay_widgets import ReplyTranslateWorker

    app = QApplication.instance() or QApplication([])  # noqa: F841  (signals need one)
    seen = {}

    class Recorder:
        def translate(self, text, target_lang, source_lang=None, context=None):
            seen["source"] = source_lang
            seen["target"] = target_lang

            class Result:
                translated = "hello"
                success = True

            return Result()

    worker = ReplyTranslateWorker(Recorder(), "szia", "EN")
    worker.setAutoDelete(False)
    worker.run()
    assert seen == {"source": "HU", "target": "EN"}


def test_a_saved_language_choice_is_ignored_in_favour_of_the_fixed_pair(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"own_language": "EN", "target_language": "EN", "reply_language": "HU"}))
    config = AppConfig.load(str(path))
    assert config.own_language == "HU"
    assert config.reply_language == "EN"


@pytest.mark.parametrize("name", ["6. World", "12. World"])
def test_any_channel_number_in_front_of_world_is_ignored(name):
    assert classify_public_channel(0, name) == "World"
