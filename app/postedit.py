"""Fix known mistranslations of WoW terms in the translator's output.

The last step before a translation is shown. The local model knows ordinary
English and Hungarian but not WoW chat, so a few game words come out as their
everyday meaning: "tank" becomes "tartály" (a container), "boss" becomes
"főnök" (a boss at work), "rogue" becomes "gazember" (a scoundrel). Players
use the English words in Hungarian too, so this puts them back.

A fix applies only when the source line contains the English word it stands
for, so a real "főnök" in a line that never said "boss" is left alone.
Hungarian adds suffixes to the word, so each fix lists its inflected forms
explicitly ("tartályt" -> "tankot", "főnökkel" -> "bossal"); a form that is
not listed stays as the model wrote it.

The pre-translation steps (app/slang.py, app/glossary.py) work on the English
input; this one works on the output, which is why it has its own table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def _forms(wrong_stem: str, right_stem: str, *pairs: tuple[str, str]) -> dict[str, str]:
    """`wrong_stem + suffix` -> `right_stem + suffix'` for each suffix pair."""
    return {wrong_stem + w: right_stem + r for w, r in pairs}


@dataclass(frozen=True)
class Rule:
    #: Matched against the source line; the fix applies only when it matches.
    source: re.Pattern[str]
    #: Wrong word form in the output -> right form. Matched as whole words.
    fixes: dict[str, str]
    _pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        words = sorted(self.fixes, key=len, reverse=True)
        pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)
        object.__setattr__(self, "_pattern", pattern)
        # Lookup is case-insensitive; keep the table's own spelling for output.
        object.__setattr__(self, "fixes", {k.lower(): v for k, v in self.fixes.items()})

    def apply(self, text: str) -> str:
        return self._pattern.sub(lambda m: _match_case(m.group(0), self.fixes[m.group(0).lower()]), text)


def _match_case(original: str, replacement: str) -> str:
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _src(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Suffixes that attach the same way to a back-vowel stem ending in a consonant
# — "tartály" and "tank" alike.
_BACK_CONSONANT = (
    ("", ""),
    ("ok", "ok"),
    ("okat", "okat"),
    ("okra", "okra"),
    ("oknak", "oknak"),
    ("okkal", "okkal"),
    ("nak", "nak"),
    ("ra", "ra"),
    ("ról", "ról"),
    ("tól", "tól"),
    ("hoz", "hoz"),
    ("ért", "ért"),
    ("ként", "ként"),
    ("ban", "ban"),
    ("ba", "ba"),
    ("ból", "ból"),
    ("on", "on"),
    ("om", "om"),
    ("od", "od"),
    ("unk", "unk"),
    ("otok", "otok"),
)

EN_HU: tuple[Rule, ...] = (
    Rule(
        _src(r"\btanks?\b|\btanking\b"),
        {
            **_forms("tartály", "tank", *_BACK_CONSONANT, ("t", "ot"), ("a", "ja"), ("unkat", "unkat")),
            "tartállyal": "tankkal",
        },
    ),
    Rule(
        _src(r"\bboss(es)?\b"),
        _forms(
            "főnök",
            "boss",
            ("", ""),
            ("öt", "t"),
            ("ök", "ok"),
            ("öket", "okat"),
            ("ökre", "okra"),
            ("öknek", "oknak"),
            ("ökkel", "okkal"),
            ("nek", "nak"),
            ("re", "ra"),
            ("ről", "ról"),
            ("től", "tól"),
            ("höz", "hoz"),
            ("ön", "on"),
            ("nél", "nál"),
            ("kel", "al"),
            ("ért", "ért"),
            ("ként", "ként"),
            ("e", "a"),
            ("ét", "át"),
        ),
    ),
    Rule(
        _src(r"\braids?\b"),
        {
            **_forms(
                "razzi",
                "raid",
                ("a", ""),
                ("át", "et"),
                ("ára", "re"),
                ("ába", "be"),
                ("ában", "ben"),
                ("ából", "ből"),
                ("ához", "hez"),
                ("áról", "ről"),
                ("ák", "ek"),
                ("ákat", "eket"),
                ("ával", "del"),
            ),
            **_forms(
                "rajtaütés",
                "raid",
                ("", ""),
                ("t", "et"),
                ("hez", "hez"),
                ("re", "re"),
                ("en", "en"),
                ("ben", "ben"),
                ("be", "be"),
                ("ből", "ből"),
                ("sel", "del"),
                ("ek", "ek"),
                ("eket", "eket"),
                ("ről", "ről"),
                ("nek", "nek"),
            ),
        },
    ),
    Rule(
        _src(r"\brogues?\b"),
        _forms(
            "gazember",
            "rogue",
            ("", ""),
            ("t", "-ot"),
            ("re", "-ra"),
            ("ek", "-ok"),
            ("eket", "-okat"),
            ("ekre", "-okra"),
            ("nek", "-nak"),
            ("rel", "-gal"),
            ("ként", "-ként"),
        ),
    ),
    Rule(
        _src(r"\bmobs?\b"),
        _forms(
            "csőcselék",
            "mob",
            ("", ""),
            ("et", "ot"),
            ("ek", "ok"),
            ("eket", "okat"),
            ("nek", "nak"),
            ("re", "ra"),
            ("kel", "bal"),
            ("től", "tól"),
        ),
    ),
    # "chest" is also the armour slot, where "mellkas" is right; only a chest
    # that is looted or opened is a "láda".
    Rule(
        _src(r"\b(loot\w*|open\w*)\b.*\bchests?\b|\bchests?\b.*\b(loot\w*|open\w*)\b"),
        _forms(
            "mellkas",
            "lád",
            ("", "a"),
            ("t", "át"),
            ("ból", "ából"),
            ("ba", "ába"),
            ("ok", "ák"),
            ("okat", "ákat"),
            ("on", "án"),
            ("ra", "ára"),
        ),
    ),
)

HU_EN: tuple[Rule, ...] = (
    Rule(_src(r"\bgyógyító"), {"doctor": "healer", "doctors": "healers"}),
    Rule(
        _src(r"\btankol"),
        {"fuellings": "tanking", "fuelling": "tanking", "fueling": "tanking", "refueling": "tanking"},
    ),
)

RULES: dict[tuple[str, str], tuple[Rule, ...]] = {("EN", "HU"): EN_HU, ("HU", "EN"): HU_EN}


def fix_terms(source: str, translated: str, source_lang: str | None, target_lang: str) -> str:
    """The translation with known WoW mistranslations put right."""
    rules = RULES.get(((source_lang or "").upper(), target_lang.upper()), ())
    for rule in rules:
        if rule.source.search(source):
            translated = rule.apply(translated)
    return translated
