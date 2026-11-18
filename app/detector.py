"""English or Hungarian? Language detection for chat messages.

The app translates between exactly two languages, so the only question is
"English or Hungarian?". That needs no general-purpose detector — the one this
replaced carried 75 languages in a 300 MB library — just the evidence that
separates these two:

- letters: á é í ó ö ő ú ü ű are everyday Hungarian and almost never English;
  ő and ű are in no English word at all
- words: the most common words of each language, Hungarian also as typed
  without accents ("koszi", "jo", "mar"), which is how a lot of chat is written
- letter pairs: "sz", "gy", "cs", "zs", "ny" are Hungarian; "th", "wh", "ck"
  and any "w" are English

A line with too little of either is reported as UNKNOWN, and the pipeline then
treats it as English. That is the safe side to err on: an English line taken for
Hungarian would be skipped untranslated, while a Hungarian line taken for
English only costs a translation that comes back unchanged.
"""

from __future__ import annotations

import enum
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class Language(enum.Enum):
    ENGLISH = "EN"
    HUNGARIAN = "HU"


#: Every language the app translates between, and nothing else.
SUPPORTED_LANGUAGES = (Language.ENGLISH, Language.HUNGARIAN)

# Gaming phrases that shouldn't trigger language detection.
# NOTE: abbreviations with translations (gg, ty, brb, afk, etc.) are handled
# by the phrasebook module — they are NOT listed here so they can reach the
# phrasebook lookup in the pipeline.
_SKIP_PHRASES = frozenset(
    {
        "kk",
        "ok",
        "lol",
        "lmao",
        "rip",
        "ez",
        "pst",
        "+",
        "++",
        "+++",
        "1",
        "2",
        "3",
        "123",
        "pull",
        "cc",
        "aoe",
        "dps",
        "heal",
        "tank",
        "res",
        "rez",
        "buff",
        "nerf",
        "proc",
        "crit",
        "dodge",
        "miss",
    }
)

MIN_TEXT_LENGTH = 3

_HUNGARIAN_ONLY_LETTERS = frozenset("őű")
_HUNGARIAN_LETTERS = frozenset("áéíóöőúüű")


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# Common words. Hungarian ones are listed without accents: the text is
# compared with its accents stripped, so "köszi" and "koszi" both count.
_HUNGARIAN_WORDS = _words(
    """
    az es nem igen van vagy hogy mit ki ez egy meg mar most csak kell lesz
    volt vagyok vagy vagyunk vagytok vannak nincs sincs leszek jo jol rossz
    koszi koszonom kosz szia sziasztok hali halo udv udvozlet csumi pusz
    puszi bocs bocsi bocsanat persze naja mert akkor amikor ahol itt ott hol
    hova honnan miert mikor mennyi hany kinek kit kivel mivel minek nekem
    neked neki nekunk nektek nekik engem teged minket titeket oket sem
    mindig soha meg ujra mindjart majd tobb kevesebb nagyon kicsit szep jobb
    legjobb gyerunk gyere gyertek menj megyek megyunk jovok tudom tudod
    tudja tudsz tudok szerintem talan biztos kerek kerem keresek keresunk
    kellene lehet lehetne segits segitseg csapat csoport ceh raidre raidbe
    tankot healt helyre varj varjatok jatek jatszom jatszunk karakter szint
    szintet feladat kuldi kuldetes penz arany targy cucc felszereles fegyver
    pancel lada ugye aha oke okes rendben jojjon induljunk mehet kesz keszen
"""
)

_ENGLISH_WORDS = _words(
    """
    the and you your is are was were be been to for of in on at it its that
    this what how why when where who which with from have has had do does
    did not no yes yeah yep nope can could would should will just need needs
    anyone any some someone something lf lfm lfg looking want wants pls
    please thanks thank thx sorry hey hi hello guys all me my mine we our us
    they them he she his her him there here then than but or if so up down
    out get got go going come coming run running buy sell selling wts wtb
    whisper pst know think good bad nice great more much many one two three
    first last time now still only also very really too omg group kill dead
    died an as by about after before again over into like make made take did
"""
)

_HUNGARIAN_PAIRS = ("sz", "gy", "cs", "zs", "ny", "ly", "ty")
_ENGLISH_PAIRS = ("th", "wh", "ck", "w", "ou", "ea", "ee", "oo", "qu")

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# Weights: letters and words are strong evidence, letter pairs weak.
_W_ONLY_LETTER = 4.0
_W_LETTER = 1.5
_W_WORD = 2.0
_W_PAIR = 0.5

#: How far ahead one language must be to win; below that the line is UNKNOWN.
_MARGIN = 1.5


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def scores(text: str) -> tuple[float, float]:
    """(Hungarian, English) evidence for a line. Exposed for the tests."""
    lowered = text.lower()
    words = _WORD.findall(lowered)
    plain_words = [_strip_accents(w) for w in words]

    hu = en = 0.0
    for ch in lowered:
        if ch in _HUNGARIAN_ONLY_LETTERS:
            hu += _W_ONLY_LETTER
        elif ch in _HUNGARIAN_LETTERS:
            hu += _W_LETTER
    for word in plain_words:
        if word in _HUNGARIAN_WORDS:
            hu += _W_WORD
        if word in _ENGLISH_WORDS:
            en += _W_WORD
    joined = " ".join(plain_words)
    hu += _W_PAIR * sum(joined.count(pair) for pair in _HUNGARIAN_PAIRS)
    en += _W_PAIR * sum(joined.count(pair) for pair in _ENGLISH_PAIRS)
    return hu, en


def detect_language(text: str) -> Language | None:
    """English, Hungarian, or None when the line says too little to tell."""
    hu, en = scores(text)
    if hu - en >= _MARGIN:
        return Language.HUNGARIAN
    if en - hu >= _MARGIN:
        return Language.ENGLISH
    return None


class ChatLanguageDetector:
    """Detects language of chat messages, skipping gaming jargon."""

    # Sentinel: the language couldn't be determined but the text is not a
    # skip-phrase and is long enough — the pipeline should still translate it.
    UNKNOWN = "UNKNOWN"

    def __init__(self, own_language: Language = Language.HUNGARIAN) -> None:
        self._own_language = own_language

    @property
    def own_language(self) -> Language:
        return self._own_language

    @own_language.setter
    def own_language(self, lang: Language) -> None:
        self._own_language = lang

    def detect(self, text: str) -> Language | str | None:
        """Detect language of text.

        Returns:
        - the Language if it is foreign (not own_language)
        - UNKNOWN if it cannot be told, but the text should still be tried
        - None if text is too short, a skip-phrase, or in own_language
        """
        cleaned = text.strip().lower()

        if len(cleaned) < MIN_TEXT_LENGTH and not any(ch in _HUNGARIAN_ONLY_LETTERS for ch in cleaned):
            return None

        if cleaned in _SKIP_PHRASES:
            return None

        detected = detect_language(text)

        if detected is None:
            logger.debug("Undetectable, will translate anyway: %r", text[:40])
            return self.UNKNOWN

        if detected == self._own_language:
            return None

        return detected

    def needs_translation(self, text: str) -> bool:
        """Check if text needs translation (detected as foreign language)."""
        return self.detect(text) is not None
