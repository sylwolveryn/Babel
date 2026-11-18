"""The in-chat gloss: what it matches, in what order, and how it reads.

The engine's output was the project owner's headline complaint, and every part
of it was a separate defect: the same term repeated once per occurrence, entries
ordered by dictionary traversal rather than by the message, alternatives printed
verbatim ("Спасибо/спс"), the same arrow glyph used for two different meanings,
and a newline that doubled the height of every glossed line.
"""

from __future__ import annotations

import pytest

pytest.importorskip("lupa", reason="lupa provides the Lua 5.1 runtime the addon needs")

from tests.lua_harness import AddonHarness  # noqa: E402


def build(dictionary: dict[str, str], **db_overrides):
    """A harness with one synthetic category loaded and the engine rebuilt.

    Each term carries only an enUS translation and the target is enUS, so these
    tests pin the matching rules and nothing about language selection — that
    has its own section at the end.
    """
    harness = AddonHarness()
    lua = harness.lua

    entries = lua.eval("{}")
    for term, translation in dictionary.items():
        entries[term] = lua.table_from({"enUS": translation})
    harness.addon_table.SocialDict = entries

    harness.load("DictEngine.lua")

    lua.execute(
        """
        BabelChatDB.dict = {
            enabled = true,
            targetLocale = "enUS",
            mode = "always",
            chatColor = "808080",
            settings = { showSocial = true },
        }
        BabelChatDB.companion = { enabled = false }
        """
    )
    for key, value in db_overrides.items():
        lua.globals().BabelChatDB.dict[key] = value

    harness.addon_table.RebuildMasterDict()
    return harness


def gloss(harness, text: str) -> tuple[str, bool]:
    result, changed = harness.addon_table.TranslateChat(text)
    return result, bool(changed)


# ── the reported symptoms ────────────────────────────────────────────────────


def test_a_repeated_term_is_glossed_once():
    """ "ty ty ty" produced three identical entries."""
    h = build({"ty": "спасибо"})

    text, changed = gloss(h, "ty ty ty for the run")

    assert changed is True
    assert text.count("ty = спасибо") == 1


def test_entries_follow_the_order_of_the_message():
    """They followed the order of the dictionary's hash traversal, so the gloss
    read in a different order from the sentence above it."""
    h = build({"wts": "продаю", "bis": "лучшее в слоте", "ty": "спасибо"})

    text, _ = gloss(h, "ty for the wts bis")

    assert text.index("ty =") < text.index("wts =") < text.index("bis =")


def test_an_alternatives_list_shows_only_the_first():
    """The data says "Спасибо/спс" — a lexicographer's note, printed verbatim."""
    h = build({"ty": "Спасибо/спс"})

    text, _ = gloss(h, "ty")

    assert "Спасибо" in text
    assert "/спс" not in text


def test_the_gloss_stays_on_one_line():
    """A newline doubled the height of every glossed message and broke
    copy-chat, which is what made a busy Trade channel unreadable."""
    h = build({"ty": "спасибо"})

    text, _ = gloss(h, "ty")

    assert "\n" not in text
    assert text.startswith("ty")


def test_the_arrow_glyph_is_gone():
    """It meant both "annotation follows" and "maps to" in the same line."""
    h = build({"ty": "спасибо"})

    text, _ = gloss(h, "ty")

    assert "→" not in text


def test_a_long_list_is_capped_with_a_count():
    """Which three matters: the cap keeps the first three the message says, so
    the gloss still reads alongside the sentence above it. Counting three pairs
    and a "+2" would pass on any three."""
    h = build({"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"})

    text, _ = gloss(h, "e d c b a")

    assert text.count(" = ") == 3
    assert "+2" in text
    assert "e = 5" in text
    assert "d = 4" in text
    assert "c = 3" in text
    assert "b = 2" not in text
    assert "a = 1" not in text


# ── word boundaries ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("term", "message"),
    [
        ("sec", "wait a second"),
        ("ez", "I need to freeze the boss"),
        ("on it", "money on itself"),
        ("gg", "the logging is broken"),
    ],
)
def test_a_term_inside_a_longer_word_is_not_matched(term, message):
    h = build({term: "TRANSLATED"})

    text, changed = gloss(h, message)

    assert changed is False, f"{term!r} matched inside {message!r}"
    assert text == message


def test_a_term_next_to_punctuation_is_still_matched():
    h = build({"ty": "спасибо"})

    _text, changed = gloss(h, "ty, that was great")

    assert changed is True


def test_a_cyrillic_term_is_not_matched_inside_a_longer_cyrillic_word():
    """Lua patterns are byte-based and %w is ASCII-only, so a naive boundary
    check treats every Cyrillic byte as a separator."""
    h = build({"да": "yes"})

    _text, changed = gloss(h, "надо подождать")

    assert changed is False


# ── multi-word phrases ───────────────────────────────────────────────────────


def test_a_phrase_is_matched_as_a_whole():
    h = build({"raid finder": "поиск рейда"})

    text, changed = gloss(h, "queue for raid finder now")

    assert changed is True
    assert "raid finder = поиск рейда" in text


def test_the_longer_phrase_wins_at_the_same_position():
    h = build({"raid": "рейд", "raid finder": "поиск рейда"})

    text, _ = gloss(h, "raid finder")

    assert "raid finder = поиск рейда" in text
    assert text.count(" = ") == 1


# ── links and colour codes ───────────────────────────────────────────────────


def test_nothing_inside_an_item_link_is_glossed():
    h = build({"ring": "кольцо"})
    link = "|cffa335ee|Hitem:245770::::::::90:62|h[Ring of Power]|h|r"

    text, changed = gloss(h, f"wts {link}")

    assert changed is False
    assert text == f"wts {link}"


def test_a_named_colour_code_does_not_swallow_the_rest_of_the_line():
    """The old range finder looked for the closing |r ten characters in, which
    is right for |cffRRGGBB and wrong for the named form — so everything after
    a short block was treated as inside it and never matched."""
    h = build({"ty": "спасибо"})

    _text, changed = gloss(h, "|cnRED_FONT_COLOR:warning|r ty")

    assert changed is True, "a term after a named colour block must still match"


def test_a_message_that_is_only_a_link_is_returned_untouched():
    h = build({"ring": "кольцо"})
    link = "|cffa335ee|Hitem:1::::::::90:62|h[Ring]|h|r"

    text, changed = gloss(h, link)

    assert changed is False
    assert text == link


# ── nothing to say ───────────────────────────────────────────────────────────


def test_a_message_with_no_matches_comes_back_byte_for_byte():
    h = build({"ty": "спасибо"})

    text, changed = gloss(h, "nothing here matches anything")

    assert changed is False
    assert text == "nothing here matches anything"


def test_a_non_string_does_not_raise():
    h = build({"ty": "спасибо"})

    _text, changed = gloss(h, 42)

    assert changed is False


# ── who speaks: the addon or the overlay ─────────────────────────────────────


def test_the_gloss_stays_quiet_when_the_companion_is_set_up():
    """Both were printing an answer for the same message: a term list in chat
    and a full sentence in the overlay, differing in wording."""
    h = build({"ty": "спасибо"}, mode="auto")
    h.lua.execute("BabelChatDB.companion.enabled = true")

    _text, changed = gloss(h, "ty")

    assert changed is False


def test_the_gloss_speaks_when_the_companion_is_not_set_up():
    h = build({"ty": "спасибо"}, mode="auto")

    _text, changed = gloss(h, "ty")

    assert changed is True


def test_always_overrides_the_companion():
    h = build({"ty": "спасибо"}, mode="always")
    h.lua.execute("BabelChatDB.companion.enabled = true")

    _text, changed = gloss(h, "ty")

    assert changed is True


def test_the_mode_defaults_to_auto_when_the_saved_config_predates_it():
    h = build({"ty": "спасибо"})
    h.lua.execute("BabelChatDB.dict.mode = nil; BabelChatDB.companion.enabled = true")

    _text, changed = gloss(h, "ty")

    assert changed is False, "an older config must not start double-printing"


# ── the punctuation a Russian message is actually written with ───────────────


@pytest.mark.parametrize(
    "message",
    [
        "«спс» за помощь",
        "спс — очень выручил",
        "спс… побежал",
        "спс\u00a0за инвайт",  # a non-breaking space, which Word and Discord insert
        "(спс)",
        "спс!",
        "…спс",
    ],
)
def test_a_term_wrapped_in_russian_punctuation_is_still_matched(message):
    """Word boundaries were decided one byte at a time, and every byte above 127
    counted as a letter. Guillemets, the em dash, the ellipsis and the
    non-breaking space are all multi-byte, so each of them glued itself to the
    word and the term stopped matching — on exactly the punctuation a Russian
    player types."""
    h = build({"спс": "thanks"})

    _text, changed = gloss(h, message)

    assert changed is True, f"nothing matched in {message!r}"


def test_a_capitalised_russian_term_matches_its_lower_case_key():
    """Lua's string.lower is ASCII-only, so "Спс" never met the key "спс" — and
    a message starts with a capital letter."""
    h = build({"спс": "thanks"})

    _text, changed = gloss(h, "Спс за помощь")

    assert changed is True


# Р is the first letter whose lower case crosses into a different UTF-8 lead
# byte, so a fold that stops one code short of it looks right everywhere else.
@pytest.mark.parametrize("word", ["Ёлка", "Ярость", "Отряд", "Рейд", "Победа", "Ясно"])
def test_the_whole_cyrillic_alphabet_folds(word):
    """Р-Я cross into a different UTF-8 lead byte and Ё sits outside the block
    altogether, so a fold that only handles А-П works for half the alphabet."""
    h = build({word.lower(): "TRANSLATED"})

    _text, changed = gloss(h, f"{word} тут")

    assert changed is True


def test_punctuation_does_not_make_a_term_match_inside_a_word():
    """Trimming must not go so far that boundaries stop being checked."""
    h = build({"да": "yes"})

    _text, changed = gloss(h, "«надо» подождать")

    assert changed is False


def test_a_phrase_wrapped_in_punctuation_is_not_downgraded_to_its_first_word():
    """Phrases were looked up on the raw token, so "«raid finder»" missed the
    phrase and fell through to the single word — glossing "raid", which is a
    shorter answer and the wrong one."""
    h = build({"raid": "рейд", "raid finder": "поиск рейда"})

    text, _ = gloss(h, "«raid finder» сейчас")

    assert "raid finder = поиск рейда" in text
    assert "raid = рейд" not in text


# ── which language the gloss is written in ──────────────────────────────────


def bilingual(target):
    """The engine over one entry that carries both shipped languages."""
    harness = AddonHarness()
    lua = harness.lua
    harness.addon_table.SocialDict = lua.eval(
        '{ ty = { enUS = "Thank you", huHU = "Köszönöm" }, np = { enUS = "No problem" } }'
    )
    harness.load("DictEngine.lua")
    lua.execute(
        """
        BabelChatDB.dict = { enabled = true, mode = "always", chatColor = "808080",
                             settings = { showSocial = true } }
        BabelChatDB.companion = { enabled = false }
        """
    )
    if target is not None:
        lua.globals().BabelChatDB.dict.targetLocale = target
    harness.addon_table.RebuildMasterDict()
    return harness


def test_with_no_choice_saved_the_gloss_is_hungarian():
    text, _ = gloss(bilingual(None), "ty")

    assert "ty = Köszönöm" in text


def test_hungarian_is_used_when_chosen():
    text, _ = gloss(bilingual("huHU"), "ty")

    assert "ty = Köszönöm" in text


def test_english_is_used_when_chosen():
    text, _ = gloss(bilingual("enUS"), "ty")

    assert "ty = Thank you" in text


def test_an_entry_with_no_hungarian_falls_back_to_english():
    """Better an English gloss than none at all."""
    text, changed = gloss(bilingual("huHU"), "np")

    assert changed is True
    assert "np = No problem" in text


def test_the_engine_no_longer_offers_zone_or_item_set_names():
    """LibBabble is gone; its toggles must not linger as dead settings."""
    h = bilingual("huHU")

    assert h.addon_table.InitLibBabble is None
