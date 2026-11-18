"""Tests for built-in phrase dictionary."""

from app.phrasebook import _normalize, lookup, lookup_abbreviation, stats


class TestNormalize:
    """Test text normalization for lookup."""

    def test_lowercase(self):
        assert _normalize("Hello") == "hello"

    def test_strip_trailing_punctuation(self):
        assert _normalize("hi!") == "hi"
        assert _normalize("thanks.") == "thanks"
        assert _normalize("ready?") == "ready"

    def test_strip_multiple_trailing_punct(self):
        assert _normalize("help!!!") == "help"

    def test_preserve_mid_word_apostrophe(self):
        assert _normalize("i'm ready") == "i'm ready"
        assert _normalize("what's up") == "what's up"
        assert _normalize("you're welcome") == "you're welcome"

    def test_strip_whitespace(self):
        assert _normalize("  hello  ") == "hello"

    def test_combined(self):
        assert _normalize("  Thank You!  ") == "thank you"


class TestLookup:
    """Test phrasebook lookup."""

    def test_basic_en_to_hu(self):
        assert lookup("hello", "EN", "HU") == "szia"

    def test_basic_hu_to_en(self):
        """The reply box goes the other way: Hungarian typed, English sent."""
        assert lookup("köszönöm", "HU", "EN") == "thank you"
        assert lookup("szia", "HU", "EN") == "hello"

    def test_case_insensitive(self):
        assert lookup("Hello", "EN", "HU") == lookup("hello", "EN", "HU")
        assert lookup("THANKS", "EN", "HU") == lookup("thanks", "EN", "HU")

    def test_punctuation_insensitive(self):
        assert lookup("hello!", "EN", "HU") == lookup("hello", "EN", "HU")
        assert lookup("thanks.", "EN", "HU") == lookup("thanks", "EN", "HU")

    def test_miss_returns_none(self):
        assert lookup("supercalifragilistic", "EN", "HU") is None

    def test_wrong_lang_pair_returns_none(self):
        assert lookup("hello", "JA", "HU") is None

    def test_a_language_that_is_not_carried_returns_none(self):
        assert lookup("hello", "EN", "RU") is None

    def test_lang_codes_case_insensitive(self):
        assert lookup("hello", "en", "hu") == lookup("hello", "EN", "HU")

    def test_gaming_phrases(self):
        assert lookup("ready", "EN", "HU") == "kész"
        assert lookup("wait", "EN", "HU") == "várj"
        assert lookup("let's go", "EN", "HU") == "gyerünk"

    def test_wow_specific(self):
        assert lookup("good luck", "EN", "HU") == "sok sikert"
        assert lookup("good run", "EN", "HU") == "jó futás volt"

    def test_questions(self):
        assert lookup("how are you", "EN", "HU") == "hogy vagy"
        assert lookup("where are you", "EN", "HU") == "hol vagy"


class TestAbbreviations:
    """Test universal gaming abbreviation lookup."""

    def test_gg_to_hu(self):
        assert lookup_abbreviation("gg", "HU") == "jó játék"

    def test_bb_to_hu(self):
        assert lookup_abbreviation("bb", "HU") == "pá"

    def test_bb_to_en(self):
        assert lookup_abbreviation("bb", "EN") == "bye bye"

    def test_afk_to_hu(self):
        assert lookup_abbreviation("afk", "HU") == "nem vagyok gépnél"

    def test_brb_to_hu(self):
        assert lookup_abbreviation("brb", "HU") == "mindjárt jövök"

    def test_ty_to_hu(self):
        assert lookup_abbreviation("ty", "HU") == "köszönöm"

    def test_np_to_hu(self):
        assert lookup_abbreviation("np", "HU") == "nincs mit"

    def test_omw_to_hu(self):
        assert lookup_abbreviation("omw", "HU") == "úton vagyok"

    def test_oom_to_hu(self):
        assert lookup_abbreviation("oom", "HU") == "elfogyott a manám"

    def test_idk_to_hu(self):
        assert lookup_abbreviation("idk", "HU") == "nem tudom"

    def test_btw_to_hu(self):
        assert lookup_abbreviation("btw", "HU") == "egyébként"

    def test_case_insensitive(self):
        assert lookup_abbreviation("GG", "HU") == lookup_abbreviation("gg", "HU")
        assert lookup_abbreviation("AFK", "HU") == lookup_abbreviation("afk", "HU")

    def test_miss_returns_none(self):
        assert lookup_abbreviation("xyz123", "HU") is None

    def test_abbreviation_via_lookup(self):
        """Abbreviations should also work through the main lookup function,
        whatever the detector made of the source."""
        assert lookup("gg", "EN", "HU") == "jó játék"
        assert lookup("brb", "HU", "HU") == "mindjárt jövök"


class TestStats:
    """Test phrasebook statistics."""

    def test_has_entries(self):
        s = stats()
        assert s["entries"] > 0
        assert s["unique_phrases"] > 0

    def test_exactly_english_and_hungarian(self):
        assert stats()["languages"] == 2
