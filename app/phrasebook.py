"""Built-in phrase dictionary for instant translation without a provider call."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Strip trailing punctuation only — preserve mid-word apostrophes
_RE_TRAILING_PUNCT = re.compile(r"[!?.,:;\"'()]+$")

PhrasebookKey = tuple[str, str, str]  # (norm_text, src_lang, tgt_lang)

_ENTRIES: dict[PhrasebookKey, str] = {}

# Universal gaming abbreviations — keyed by (abbrev, target_lang)
_ABBREVIATIONS: dict[tuple[str, str], str] = {}


def _normalize(text: str) -> str:
    """Lowercase, strip trailing punctuation."""
    return _RE_TRAILING_PUNCT.sub("", text.strip().lower())


def _add(phrase_map: dict[str, str]) -> None:
    """Register a phrase across all language pair combinations."""
    langs = list(phrase_map.items())
    for i, (src_lang, src_text) in enumerate(langs):
        for j, (tgt_lang, tgt_text) in enumerate(langs):
            if i != j:
                _ENTRIES[(_normalize(src_text), src_lang, tgt_lang)] = tgt_text


def _abbrev(abbr: str, translations: dict[str, str]) -> None:
    """Register a universal gaming abbreviation."""
    norm = _normalize(abbr)
    for lang, text in translations.items():
        _ABBREVIATIONS[(norm, lang)] = text


# ---------------------------------------------------------------------------
# Phrase data: {lang_code: phrase_text}
# Languages: EN, HU
# fmt: off
# ---------------------------------------------------------------------------

# --- Greetings ---
_add({"EN": "hello", "HU": "szia"})
_add({"EN": "hey", "HU": "hali"})
_add({"EN": "good morning", "HU": "jó reggelt"})
_add({"EN": "good evening", "HU": "jó estét"})
_add({"EN": "good night", "HU": "jó éjt"})
_add({"EN": "bye", "HU": "pá"})
_add({"EN": "goodbye", "HU": "viszontlátásra"})
_add({"EN": "see you", "HU": "viszlát"})
_add({"EN": "cya", "HU": "csá"})
_add({"EN": "later", "HU": "később"})
_add({"EN": "welcome", "HU": "üdv"})

# --- Politeness ---
_add({"EN": "thanks", "HU": "kösz"})
_add({"EN": "thank you", "HU": "köszönöm"})
_add({"EN": "thx", "HU": "köszi"})
_add({"EN": "please", "HU": "kérlek"})
_add({"EN": "pls", "HU": "légyszi"})
_add({"EN": "sorry", "HU": "bocsi"})
_add({"EN": "no problem", "HU": "semmi gond"})
_add({"EN": "you're welcome", "HU": "szívesen"})
_add({"EN": "my bad", "HU": "az én hibám"})

# --- Gaming coordination ---
_add({"EN": "ready", "HU": "kész"})
_add({"EN": "wait", "HU": "várj"})
_add({"EN": "stop", "HU": "állj"})
_add({"EN": "help", "HU": "segítség"})
_add({"EN": "follow me", "HU": "kövessetek"})
_add({"EN": "on my way", "HU": "úton vagyok"})
_add({"EN": "need help", "HU": "segítség kell"})
_add({"EN": "come here", "HU": "gyere ide"})
_add({"EN": "let's go", "HU": "gyerünk"})
_add({"EN": "run", "HU": "fussatok"})

# --- Status ---
_add({"EN": "i'm ready", "HU": "készen állok"})
_add({"EN": "i'm coming", "HU": "jövök"})
_add({"EN": "one moment", "HU": "egy pillanat"})
_add({"EN": "one sec", "HU": "egy sec"})
_add({"EN": "back", "HU": "vissza"})
_add({"EN": "i'm back", "HU": "visszajöttem"})

# --- Reactions ---
_add({"EN": "nice", "HU": "szép"})
_add({"EN": "great", "HU": "remek"})
_add({"EN": "cool", "HU": "király"})
_add({"EN": "awesome", "HU": "fantasztikus"})
_add({"EN": "well done", "HU": "szép volt"})
_add({"EN": "good job", "HU": "szép munka"})

# --- Common questions ---
_add({"EN": "how are you", "HU": "hogy vagy"})
_add({"EN": "where are you", "HU": "hol vagy"})
_add({"EN": "what's up", "HU": "mi újság"})
_add({"EN": "do you speak english", "HU": "beszélsz angolul"})

# --- WoW-specific ---
_add({"EN": "summon please", "HU": "idézést kérek"})
_add({"EN": "invite please", "HU": "meghívást kérek"})
_add({"EN": "good run", "HU": "jó futás volt"})
_add({"EN": "good group", "HU": "jó csapat"})
_add({"EN": "good luck", "HU": "sok sikert"})
_add({"EN": "have fun", "HU": "jó szórakozást"})
_add({"EN": "well played", "HU": "szépen játszottál"})

# ---------------------------------------------------------------------------
# Gaming abbreviations — universal, language-independent
# ---------------------------------------------------------------------------

_abbrev("gg", {"HU": "jó játék"})
_abbrev("bb", {"EN": "bye bye", "HU": "pá"})
_abbrev("afk", {"HU": "nem vagyok gépnél"})
_abbrev("brb", {"HU": "mindjárt jövök"})
_abbrev("ty", {"HU": "köszönöm"})
_abbrev("np", {"HU": "nincs mit"})
_abbrev("wp", {"HU": "szépen játszottál"})
_abbrev("gj", {"HU": "szép munka"})
_abbrev("gl", {"HU": "sok sikert"})
_abbrev("hf", {"HU": "jó szórakozást"})
_abbrev("omw", {"HU": "úton vagyok"})
_abbrev("oom", {"HU": "elfogyott a manám"})
_abbrev("lfg", {"HU": "csapatot keresek"})
_abbrev("lfm", {"HU": "tagokat keresünk"})
_abbrev("inv", {"HU": "hívj meg"})
_abbrev("rdy", {"HU": "kész"})
_abbrev("inc", {"HU": "jönnek"})
_abbrev("wts", {"HU": "eladó"})
_abbrev("wtb", {"HU": "vennék"})
_abbrev("mb", {"HU": "az én hibám"})
_abbrev("idd", {"HU": "valóban"})
_abbrev("lf", {"HU": "keresek"})
_abbrev("pls", {"HU": "kérlek"})
_abbrev("thx", {"HU": "kösz"})
_abbrev("nvm", {"HU": "mindegy"})
_abbrev("idk", {"HU": "nem tudom"})
_abbrev("imo", {"HU": "szerintem"})
_abbrev("tbh", {"HU": "őszintén szólva"})
_abbrev("btw", {"HU": "egyébként"})
_abbrev("gtg", {"HU": "mennem kell"})
_abbrev("nw", {"HU": "semmi gond"})

# Common short words (too short to detect, or commonly detected wrong)
_abbrev("yes", {"HU": "igen"})
_abbrev("yea", {"HU": "ja"})
_abbrev("yeah", {"HU": "ja"})
_abbrev("yep", {"HU": "aha"})
_abbrev("no", {"HU": "nem"})
_abbrev("nope", {"HU": "nem"})
_abbrev("hi", {"HU": "szia"})
_abbrev("sup", {"HU": "mizu"})
_abbrev("go", {"HU": "gyerünk"})

# Summon requests (WoW convention: "123" = "summon me")
_abbrev("123", {"EN": "summon", "HU": "idézés"})
_abbrev("123 pls", {"EN": "summon please", "HU": "idézést kérek"})
_abbrev("sum pls", {"EN": "summon please", "HU": "idézést kérek"})
_abbrev("sum", {"EN": "summon", "HU": "idézés"})
_abbrev("summ", {"EN": "summon", "HU": "idézés"})
_abbrev("summ pls", {"EN": "summon please", "HU": "idézést kérek"})
_abbrev("summ all pls", {"EN": "summon all please", "HU": "mindenkit idézz kérlek"})
_abbrev("sum all pls", {"EN": "summon all please", "HU": "mindenkit idézz kérlek"})

# Raid / instance coordination
_abbrev("bio", {"EN": "bio break", "HU": "rövid szünet (mosdó)"})
_abbrev("bio break", {"EN": "bio break", "HU": "rövid szünet (mosdó)"})
_abbrev("sec bio", {"EN": "sec, bio break", "HU": "egy pillanat, mosdó"})
_abbrev("30 sec bio", {"EN": "30 sec bio break", "HU": "30 mp szünet (mosdó)"})
_abbrev("2 min bio", {"EN": "2 min bio break", "HU": "2 perc szünet (mosdó)"})
_abbrev("5 min bio", {"EN": "5 min bio break", "HU": "5 perc szünet (mosdó)"})
_abbrev("on last", {"EN": "on last boss", "HU": "az utolsó bossnál"})
_abbrev("wipe", {"EN": "wipe", "HU": "mindenki meghalt"})
_abbrev("lust", {"EN": "bloodlust", "HU": "bloodlust (gyorsító buff)"})
_abbrev("bl", {"EN": "bloodlust", "HU": "bloodlust (gyorsító buff)"})
_abbrev("hero", {"EN": "heroism", "HU": "heroism (gyorsító buff)"})
_abbrev("brez", {"EN": "battle rez", "HU": "harci feltámasztás"})
_abbrev("rez", {"EN": "resurrect", "HU": "feltámasztás"})
_abbrev("rezz", {"EN": "resurrect", "HU": "feltámasztás"})
_abbrev("rezz pls", {"EN": "rez please", "HU": "támassz fel kérlek"})
_abbrev("rez pls", {"EN": "rez please", "HU": "támassz fel kérlek"})
_abbrev("cds", {"EN": "cooldowns", "HU": "cooldownok"})
_abbrev("pop cds", {"EN": "pop cooldowns", "HU": "nyomjátok a cooldownokat"})
_abbrev("kick", {"EN": "interrupt", "HU": "szakítsd meg"})
_abbrev("int", {"EN": "interrupt", "HU": "szakítsd meg"})
_abbrev("gl guys", {"EN": "good luck guys", "HU": "sok sikert srácok"})
_abbrev("gl all", {"EN": "good luck all", "HU": "sok sikert mindenkinek"})
_abbrev("gl hf", {"EN": "good luck, have fun", "HU": "sok sikert, jó szórakozást"})
_abbrev("gg wp", {"EN": "good game, well played", "HU": "jó játék, szépen játszottatok"})
_abbrev("gotta go", {"EN": "gotta go", "HU": "mennem kell"})
_abbrev("zug zug", {"EN": "zug zug (yes, sir)", "HU": "zug zug (igenis)"})
_abbrev("zamn", {"EN": "damn", "HU": "a mindenit"})

# fmt: on

# ---------------------------------------------------------------------------
# Merge glossary abbreviations (Pirson's WoW Translator).
# Our entries have priority — glossary only fills gaps.
# ---------------------------------------------------------------------------
try:
    from app.glossary_data import SAFE_ABBREVIATIONS as _GLOSSARY_ABBREVS

    _glossary_added = 0
    for _key, _translations in _GLOSSARY_ABBREVS.items():
        _norm = _normalize(_key)
        for _lang, _text in _translations.items():
            _lang_upper = _lang.upper()
            if (_norm, _lang_upper) not in _ABBREVIATIONS:
                _ABBREVIATIONS[(_norm, _lang_upper)] = _text
                _glossary_added += 1
    logger.debug("Merged %d glossary abbreviations", _glossary_added)
    del _GLOSSARY_ABBREVS, _glossary_added, _key, _translations, _norm, _lang, _text, _lang_upper
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lookup(text: str, source_lang: str, target_lang: str) -> str | None:
    """Look up a phrase in the built-in phrasebook.

    Checks language-specific phrases first, then abbreviations.
    Returns translation string if found, None on miss.
    """
    norm = _normalize(text)
    tgt = target_lang.upper()

    # 1. Language-specific phrases (exact source→target match)
    result = _ENTRIES.get((norm, source_lang.upper(), tgt))
    if result is not None:
        logger.debug(
            "Phrasebook hit: %r [%s->%s] = %r",
            text, source_lang, target_lang, result,
        )
        return result

    # 2. Universal abbreviations (language-independent)
    result = _ABBREVIATIONS.get((norm, tgt))
    if result is not None:
        logger.debug(
            "Abbreviation hit: %r [->%s] = %r",
            text, target_lang, result,
        )
        return result

    return None


def lookup_abbreviation(text: str, target_lang: str) -> str | None:
    """Look up a universal abbreviation (no source language needed).

    Use for pre-detection lookup of short gaming abbreviations
    that are identical across all languages.
    """
    result = _ABBREVIATIONS.get((_normalize(text), target_lang.upper()))
    if result is not None:
        logger.debug(
            "Abbreviation pre-detect: %r [->%s] = %r",
            text, target_lang, result,
        )
    return result


def stats() -> dict[str, int]:
    """Return phrasebook statistics."""
    sources = set()
    targets = set()
    phrases = set()
    for norm_text, src, tgt in _ENTRIES:
        sources.add(src)
        targets.add(tgt)
        phrases.add(norm_text)
    abbrev_phrases = {abbr for abbr, _ in _ABBREVIATIONS}
    abbrev_langs = {lang for _, lang in _ABBREVIATIONS}
    return {
        "entries": len(_ENTRIES) + len(_ABBREVIATIONS),
        "unique_phrases": len(phrases | abbrev_phrases),
        "languages": len(sources | targets | abbrev_langs),
    }
