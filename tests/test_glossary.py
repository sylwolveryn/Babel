"""Tests for WoW glossary: abbreviation lookup + context-gated term expansion."""

from app.glossary import (
    _CONTEXT_GATE,
    _NEVER_EXPAND,
    expand_wow_terms,
    lookup_abbreviation,
)
from app.glossary_data import CONTEXT_EXPANSIONS, SAFE_ABBREVIATIONS


class TestLookupAbbreviation:
    """Tier 1: safe standalone abbreviation lookup."""

    def test_hit_exact(self):
        assert lookup_abbreviation("aoe", "HU") == "Területi hatás (AoE)"

    def test_hit_different_lang(self):
        assert lookup_abbreviation("aoe", "EN") == "Area of Effect"

    def test_case_insensitive(self):
        assert lookup_abbreviation("AOE", "HU") == lookup_abbreviation("aoe", "HU")

    def test_whitespace_stripped(self):
        assert lookup_abbreviation("  aoe  ", "HU") == "Területi hatás (AoE)"

    def test_miss_returns_none(self):
        assert lookup_abbreviation("xyznotaword", "HU") is None

    def test_known_key_unknown_lang(self):
        # "aoe" exists but only English and Hungarian are carried
        assert lookup_abbreviation("aoe", "RU") is None

    def test_several_entries(self):
        """Spot-check a handful of entries in both languages."""
        assert lookup_abbreviation("dk", "EN") == "Death Knight"
        assert lookup_abbreviation("dk", "HU") == "Halállovag"
        assert lookup_abbreviation("ilvl", "HU") == "Tárgyszint"
        assert lookup_abbreviation("gz", "HU") == "Gratulálok"
        assert lookup_abbreviation("cc", "HU") == "Tömegirányítás (CC)"

    def test_lang_code_case_insensitive(self):
        assert lookup_abbreviation("aoe", "hu") == lookup_abbreviation("aoe", "HU")


class TestExpandWowTerms:
    """Tier 2: context-gated expansion of WoW terms."""

    def test_no_expansion_single_term(self):
        """Single WoW term — below context gate, no expansion."""
        text = "the aggro is bad"
        assert expand_wow_terms(text) == text

    def test_expansion_two_terms(self):
        """Two recognized terms → both get expanded."""
        text = "aggro on trash"
        result = expand_wow_terms(text)
        assert "Threat/Aggro" in result
        assert "Trash mobs" in result

    def test_expansion_preserves_non_terms(self):
        """Non-WoW words stay untouched."""
        text = "pull aggro on trash please"
        result = expand_wow_terms(text)
        assert "please" in result

    def test_never_expand_words_untouched(self):
        """Words in _NEVER_EXPAND stay as-is even with 2+ gaming terms."""
        # "fire" is in _NEVER_EXPAND, "aggro" and "trash" are expandable
        text = "fire aggro trash"
        result = expand_wow_terms(text)
        assert result.startswith("fire")
        assert "Threat/Aggro" in result

    def test_case_insensitive_matching(self):
        """Terms match case-insensitively."""
        text = "AGGRO on TRASH"
        result = expand_wow_terms(text)
        assert "Threat/Aggro" in result
        assert "Trash mobs" in result

    def test_context_gate_exact_threshold(self):
        """Exactly _CONTEXT_GATE terms triggers expansion."""
        assert _CONTEXT_GATE == 2
        text = "aggro trash"
        assert expand_wow_terms(text) != text

    def test_below_context_gate_no_expansion(self):
        """Only _NEVER_EXPAND terms don't count toward gate."""
        # "fire" and "frost" are in _NEVER_EXPAND — they don't count
        text = "fire frost"
        assert expand_wow_terms(text) == text

    def test_plain_english_unchanged(self):
        """Regular English sentence with no WoW terms stays unchanged."""
        text = "Hello everyone, how are you doing today?"
        assert expand_wow_terms(text) == text

    def test_dungeon_abbreviations(self):
        """Instance abbreviations expand correctly."""
        text = "lets run brd then naxx"
        result = expand_wow_terms(text)
        assert "Blackrock Depths" in result
        assert "Naxxramas" in result


class TestNeverExpand:
    """Verify _NEVER_EXPAND set contains expected dangerous words."""

    def test_common_english_words_blocked(self):
        for word in ("add", "hit", "focus", "fire", "arms", "balance", "shadow"):
            assert word in _NEVER_EXPAND, f"{word!r} should be in _NEVER_EXPAND"

    def test_never_expand_are_lowercase(self):
        for word in _NEVER_EXPAND:
            assert word == word.lower(), f"{word!r} should be lowercase"


class TestDataIntegrity:
    """Verify glossary data is properly structured."""

    def test_safe_abbreviations_non_empty(self):
        assert len(SAFE_ABBREVIATIONS) > 50

    def test_context_expansions_non_empty(self):
        assert len(CONTEXT_EXPANSIONS) > 50

    def test_safe_abbreviation_keys_lowercase(self):
        for key in SAFE_ABBREVIATIONS:
            assert key == key.lower(), f"Key {key!r} should be lowercase"

    def test_context_expansion_keys_lowercase(self):
        for key in CONTEXT_EXPANSIONS:
            assert key == key.lower(), f"Key {key!r} should be lowercase"

    def test_safe_abbreviations_have_translations(self):
        """Every entry carries English and Hungarian, and nothing else."""
        for key, translations in SAFE_ABBREVIATIONS.items():
            assert set(translations) == {"EN", "HU"}, f"{key!r} carries {sorted(translations)}"
            assert all(text.strip() for text in translations.values()), f"{key!r} has a blank translation"

    def test_context_expansions_are_strings(self):
        for key, val in CONTEXT_EXPANSIONS.items():
            assert isinstance(val, str), f"{key!r} value should be str"
            assert len(val) > 0, f"{key!r} has empty expansion"
