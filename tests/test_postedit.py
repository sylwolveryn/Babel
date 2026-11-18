"""The post-translation fix-up of WoW terms (app/postedit.py)."""

from __future__ import annotations

import pytest

from app.postedit import fix_terms
from app.translators import base
from app.translators.base import ProviderSpec, TranslationResult
from app.translators.service import TranslatorService


@pytest.mark.parametrize(
    ("source", "model_output", "expected"),
    [
        ("the tank died", "A tartály elpusztult.", "A tank elpusztult."),
        ("heal the tank pls", "Gyógyítsa meg a tartályt, kérem.", "Gyógyítsa meg a tankot, kérem."),
        ("tanks and healers needed", "szükség van tartályokra", "szükség van tankokra"),
        ("kill the boss first", "Előbb öld meg a főnököt.", "Előbb öld meg a bosst."),
        ("join the raid", "Csatlakozz a rajtaütéshez!", "Csatlakozz a raidhez!"),
        ("need a rogue", "Kell egy gazember.", "Kell egy rogue."),
        ("need a rogue and a mage", "egy gazemberre és egy mágusra", "egy rogue-ra és egy mágusra"),
        ("the mob is aggro on me", "A csőcselék rám szállt.", "A mob rám szállt."),
        ("loot the chest", "Kifosztom a mellkast.", "Kifosztom a ládát."),
    ],
)
def test_en_hu_fixes(source, model_output, expected):
    assert fix_terms(source, model_output, "EN", "HU") == expected


def test_capital_at_sentence_start_is_kept():
    assert fix_terms("tank died", "Tartály meghalt.", "EN", "HU") == "Tank meghalt."


@pytest.mark.parametrize(
    ("source", "model_output"),
    [
        # The source never said "boss": a boss at work stays a "főnök".
        ("my manager is angry", "A főnök dühös."),
        # A chest piece is armour, where "mellkas" is right.
        ("I need a new chest piece", "Szükségem van egy új mellkas darabra."),
        # Part of a longer word is not the word.
        ("the tank died", "A tartálykocsi elpusztult."),
    ],
)
def test_leaves_alone_what_it_should(source, model_output):
    assert fix_terms(source, model_output, "EN", "HU") == model_output


def test_hu_en_fixes():
    assert fix_terms("tankolok", "fuellings", "HU", "EN") == "tanking"
    assert fix_terms("gyógyító vagyok", "I'm a doctor", "HU", "EN") == "I'm a healer"


def test_other_direction_rules_do_not_apply():
    assert fix_terms("the tank died", "A tartály elpusztult.", "HU", "EN") == "A tartály elpusztult."


class _Echo:
    def __init__(self, output):
        self.output = output

    def translate(self, text, target_lang, source_lang=None):
        return TranslationResult(text, self.output, source_lang or "", target_lang, True, backend="echo")


def test_service_applies_it_to_every_translation(monkeypatch):
    monkeypatch.setattr(
        base, "all_providers", lambda: [ProviderSpec("echo", "Echo", lambda: _Echo("A tartály elpusztult."))]
    )
    result = TranslatorService().translate("the tank died", target_lang="HU", source_lang="EN")
    assert result.success
    assert result.translated == "A tank elpusztult."
