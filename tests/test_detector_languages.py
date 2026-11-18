"""The detector tells English from Hungarian, and nothing more.

The app translates between English and Hungarian, so the only question the
pipeline asks is "English or Hungarian?". The detector answers it with letters,
common words and letter pairs (app/detector.py) instead of a 75-language
library that was over half the size of the built app.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.detector import SUPPORTED_LANGUAGES, ChatLanguageDetector, Language, detect_language

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from detector_corpus import ENGLISH, HUNGARIAN  # noqa: E402


def test_every_language_the_app_translates_is_detected():
    from app.languages import LANGUAGES
    from app.main import _LANG_CODE_TO_LANGUAGE

    assert set(LANGUAGES) == set(_LANG_CODE_TO_LANGUAGE) == {"EN", "HU"}
    assert set(_LANG_CODE_TO_LANGUAGE.values()) == set(SUPPORTED_LANGUAGES)
    assert set(SUPPORTED_LANGUAGES) == {Language.ENGLISH, Language.HUNGARIAN}


def test_no_language_detection_library_is_needed():
    import app.detector

    source = Path(app.detector.__file__).read_text(encoding="utf-8")
    assert "lingua" not in source.split('"""', 2)[2]


@pytest.mark.parametrize("text", ENGLISH)
def test_english_chat_is_english(text):
    assert detect_language(text) == Language.ENGLISH


@pytest.mark.parametrize("text", HUNGARIAN)
def test_hungarian_chat_is_hungarian(text):
    assert detect_language(text) == Language.HUNGARIAN


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("hello everyone looking for two more damage dealers", Language.ENGLISH),
        ("lf tank for naxx 25, whisper me", Language.ENGLISH),
        ("még két sebzőt keresünk a raidre, írjatok", None),  # own language — nothing to do
    ],
    ids=["english", "english_chat_speak", "hungarian_is_own"],
)
def test_the_pipeline_is_told_what_to_translate(text, expected):
    assert ChatLanguageDetector(Language.HUNGARIAN).detect(text) == expected


def test_a_short_line_with_hungarian_only_letters_is_hungarian():
    """ő and ű occur in no English word, so even two letters are enough."""
    assert ChatLanguageDetector(Language.HUNGARIAN).detect("jő") is None


def test_english_is_detected_when_english_is_the_own_language_too():
    """own_language decides what is skipped, not what is recognised."""
    detector = ChatLanguageDetector(Language.ENGLISH)

    assert detector.detect("hello everyone looking for two more damage dealers") is None
    assert detector.detect("még két sebzőt keresünk a raidre, írjatok") == Language.HUNGARIAN


def test_an_undecidable_line_is_handed_on_rather_than_dropped():
    """No evidence either way must not silence the line: the pipeline assumes
    English for it and translates."""
    assert ChatLanguageDetector(Language.HUNGARIAN).detect("xqzv bmp") == ChatLanguageDetector.UNKNOWN


@pytest.mark.parametrize("text", ["need a tank", "lf dps for icc", "gg wp", "tank pls"])
def test_gaming_words_hungarians_use_too_do_not_make_a_line_hungarian(text):
    assert detect_language(text) != Language.HUNGARIAN
