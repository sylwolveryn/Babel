"""Two things one live session turned up, and what is left of a third.

A refusal shown as a translation. A provider can answer 200 with an explanation
of what it will not translate, and that went into the overlay where the
translation belongs. The provider that did it is gone; what stays is the
contract every provider shares: a refusal is a failure with its own code, it
survives the fall-through to the next provider, and the overlay has a short
line for it.

And the stall behind "it works for a minute and then stops". The native scanner
caches the address it found the buffer at and reads from it on every poll. When
Lua's garbage collector moves the buffer, the bytes left behind still parse —
same markers, same last sequence — so the fast path reads that ghost forever
and never rescans. Nothing arrives again until the app is restarted.
"""

from __future__ import annotations

import pathlib
import re

from app.translators.base import FAILURE

REFUSED = FAILURE.REFUSED


# ── a refusal is not a translation ───────────────────────────────────────────


def test_the_overlay_has_something_short_to_say_instead():
    from app.locales import LANGUAGE_MODULES

    for language, module in LANGUAGE_MODULES.items():
        assert "overlay.refused" in module.STRINGS, f"no {language} copy"
        assert len(module.STRINGS["overlay.refused"]) < 60, f"the {language} note is not short"


# ── the cached address has to expire ─────────────────────────────────────────

SCANNER = pathlib.Path(__file__).resolve().parent.parent / "babelchat_scanner_win" / "src"


def scanner_source() -> str:
    """The whole crate, not one file of it.

    The scanner outgrew a single module and was split along its seams — the
    process it reads, the markers it reads for, the search, and the table slot.
    A check that read only lib.rs would quietly stop covering four fifths of
    what it is about."""
    return chr(10).join(path.read_text(encoding="utf-8") for path in sorted(SCANNER.glob("*.rs")))


def test_the_scanner_source_is_where_it_is_expected():
    """Every check below reads this file; if the path were wrong they would all
    pass on an empty string."""
    source = scanner_source()

    assert "find_and_read_buffer" in source
    assert len(source.splitlines()) > 200


def test_a_quiet_cached_address_is_not_trusted_for_ever():
    """`FastRead::NoNew` returned 0 unconditionally, and a ghost buffer reads
    exactly like an idle one. That is the stall."""
    source = scanner_source()

    assert "CACHE_MAX_QUIET_MS" in source, "nothing bounds how long a silent cache is believed"
    assert "last_fresh_ms" in source, "the cache does not record when it last produced anything"

    quiet = re.search(r"const CACHE_MAX_QUIET_MS: u64 = ([0-9_]+);", source)
    assert quiet, "the limit is not a named constant"
    milliseconds = int(quiet.group(1).replace("_", ""))
    assert 3_000 <= milliseconds <= 30_000, f"{milliseconds}ms is not a sane limit"


def test_the_idle_fast_path_still_exists():
    """Rescanning on every idle poll is what the cache was introduced to stop,
    and undoing that would trade a stall for a pegged CPU."""
    source = scanner_source()

    assert "SCAN_MIN_GAP_MS" in source
    assert "if now_ms().saturating_sub(c.last_fresh_ms) < CACHE_MAX_QUIET_MS {" in source, (
        "the quiet path no longer returns early, so every idle poll scans"
    )


def test_a_fresh_read_resets_the_clock():
    """Without this the cache expires on a fixed schedule however busy the chat
    is, and a full scan lands in the middle of a raid."""
    source = scanner_source()

    assert "c.last_fresh_ms = now_ms();" in source


# ── and the Python side can climb back down ──────────────────────────────────


# NOTE: the "have I run ahead of the buffer?" probe that used to be tested here
# is gone. It asked the scanner with a filter of zero, and at zero any parseable
# bytes at the cached address look fresh — so the question renewed the very
# cache it existed to catch, and held a dead address for two minutes at a time.
# What replaced it is the buffer's pulse; see tests/test_buffer_pulse.py.


# ── colour escapes ───────────────────────────────────────────────────────────


def test_the_named_colour_escape_is_stripped():
    """`|cnIQ4:` — colour by NAME rather than by hex. A 3.3.5a client does not
    send it, but the parser keeps stripping it, and a stripped escape must not
    take the link it wraps along with it."""
    from app.parser import _RE_COLOR_CODES

    raw = "|cnIQ4:|Hitem:49623:0:0:0:0:0:0:0|h[Shadowmourne]|h|r anyone?"

    cleaned = _RE_COLOR_CODES.sub("", raw)

    assert "|cn" not in cleaned
    assert "IQ4" not in cleaned
    assert "|Hitem:" in cleaned, "the hyperlink itself must survive — it is what the link is"
    assert cleaned.endswith("anyone?")


def test_the_hex_colour_escape_goes():
    """The form a 3.3.5a client actually sends."""
    from app.parser import _RE_COLOR_CODES

    assert _RE_COLOR_CODES.sub("", "|cff3fc7ebName-Realm|r: hello") == "Name-Realm: hello"


def test_a_bare_pipe_in_ordinary_text_is_left_alone():
    """Players type pipes. Widening the pattern until it eats them would be a
    different bug with the same symptom."""
    from app.parser import _RE_COLOR_CODES

    assert _RE_COLOR_CODES.sub("", "a | b |cn| c") == "a | b |cn| c"


# ── what replaced the probe ──────────────────────────────────────────────────


def test_a_negative_sequence_still_forces_a_scan():
    """Kept from the first attempt at this, because it is the only way to make
    the scanner distrust its cache from outside — and a diagnostic that cannot
    do that is not much of one."""
    source = scanner_source()

    assert "let forced = min_seq < 0;" in source
    assert "if !forced {" in source, "a forced call still goes through the fast path"


def test_a_forced_scan_is_not_refused_by_the_rate_limiter():
    source = scanner_source()

    assert "if !forced && now.saturating_sub(last) < SCAN_MIN_GAP_MS {" in source


# ── and the refusal has to survive the chain ─────────────────────────────────


def chain_of(*backends):
    """A TranslatorService with a fixed order, for testing what it does with
    results rather than how it sorts providers.

    `active_ids` is a property computed from the registry of real providers, so
    a fake cannot be put in the order any other way — and the alternative,
    registering fakes globally, leaks between tests.
    """
    from app.translators.service import TranslatorService

    class Fixed(TranslatorService):
        def __init__(self, mapping):
            self._backends = mapping
            self._priority = ""

        @property
        def active_ids(self):
            return tuple(self._backends)

    return Fixed({name: backend for name, backend in backends})


def test_a_refusal_is_what_the_user_is_told_even_though_it_was_not_last():
    """The keyless fallback is always last, so its failure is what the chain
    returned — and "the translator declined this message" was unreachable
    however often it happened. A refusal explains itself; a network error at
    the end of the chain does not explain the refusal at the start of it."""
    from app.translators.base import failed

    class Declines:
        def translate(self, text, target_lang, source_lang=None):
            return failed(text, target_lang, source_lang, REFUSED, "declines")

    class Unreachable:
        def translate(self, text, target_lang, source_lang=None):
            return failed(text, target_lang, source_lang, FAILURE.RETRIES, "unreachable")

    result = chain_of(("declines", Declines()), ("unreachable", Unreachable())).translate("hello", "HU")

    assert result.success is False
    assert result.error == REFUSED, f"the chain reported {result.error!r} instead of the refusal"
    assert result.translated == "hello"


def test_a_provider_that_succeeds_after_a_refusal_still_wins():
    """Remembering the refusal must not stop the next provider being used —
    the next provider may have no objection to the text, and a translation
    beats an explanation."""
    from app.translators.base import TranslationResult, failed

    class Declines:
        def translate(self, text, target_lang, source_lang=None):
            return failed(text, target_lang, source_lang, REFUSED, "declines")

    class Obliges:
        def translate(self, text, target_lang, source_lang=None):
            return TranslationResult(
                original=text,
                translated="szia",
                source_lang="",
                target_lang=target_lang,
                success=True,
                backend="obliges",
            )

    result = chain_of(("declines", Declines()), ("obliges", Obliges())).translate("hello", "HU")

    assert result.success is True
    assert result.translated == "szia"


def test_an_ordinary_failure_is_still_the_last_one():
    """Only a refusal is promoted. Otherwise the first thing that went wrong
    would mask everything after it, and the last failure is usually the most
    informative one about why nothing worked."""
    from app.translators.base import FAILURE, failed

    class Quota:
        def translate(self, text, target_lang, source_lang=None):
            return failed(text, target_lang, source_lang, FAILURE.QUOTA, "quota")

    class Network:
        def translate(self, text, target_lang, source_lang=None):
            return failed(text, target_lang, source_lang, FAILURE.RETRIES, "network")

    result = chain_of(("quota", Quota()), ("network", Network())).translate("hello", "HU")

    assert result.error == FAILURE.RETRIES


def test_the_refusal_code_has_exactly_one_definition():
    """It was spelled out in two modules that both have to agree, which is the
    same shape as the addon-and-scanner anchor pair — two literals that must
    match are two literals that will eventually not."""
    import pathlib

    translators = pathlib.Path(__file__).resolve().parent.parent / "app" / "translators"
    literal = 0
    for path in translators.glob("*.py"):
        literal += path.read_text(encoding="utf-8").count('"provider_refused"')

    assert literal == 1, f'"provider_refused" is written out {literal} times; it should be defined once'
