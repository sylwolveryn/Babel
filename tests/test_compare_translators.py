"""The translator comparison tool, run against a fake engine."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import compare_translators as ct  # noqa: E402
from translator_corpus import EN_HU, HU_EN  # noqa: E402


def test_chrf_is_100_for_a_match_and_low_for_nonsense():
    assert ct.chrf("Köszi a segítséget!", "köszi a segítséget!") == 100
    assert ct.chrf("xyz qqq", "Köszi a segítséget!") < 10
    close = ct.chrf("Köszönöm a segítséget!", "Köszi a segítséget!")
    assert 50 < close < 100


def test_the_corpus_pairs_every_line_with_a_reference():
    for corpus in (EN_HU, HU_EN):
        assert corpus
        for line, reference in corpus:
            assert line.strip() and reference.strip()


def test_an_engine_is_scored_and_reported():
    echo_reference = dict(EN_HU)

    def factory(source, target):
        return lambda text: echo_reference.get(text, text)

    result = ct.run_direction("perfect", factory, "en", "hu", EN_HU)
    assert result.chrf == 100 and not result.error
    report = ct.render_report([result])
    assert "| perfect | en→hu | 100.0 |" in report
    assert EN_HU[0][0] in report


def test_a_missing_package_is_a_skip_not_a_crash():
    def factory(source, target):
        raise ImportError("no module", name="ctranslate2")

    result = ct.run_direction("ct2", factory, "en", "hu", EN_HU)
    assert result.error == "skipped: ctranslate2 not installed"
    assert "skipped" in ct.render_report([result])


def test_the_mymemory_engine_calls_the_api_directly(monkeypatch):
    """The app no longer has a MyMemory provider; the tool asks the HTTP API
    itself, so a comparison run still includes it."""
    import requests

    from tests.translator_fakes import FakeResponse, FakeSession

    session = FakeSession()
    session.script(
        ct.MYMEMORY_ENDPOINT,
        FakeResponse(200, {"responseStatus": 200, "responseData": {"translatedText": "szia"}}),
        FakeResponse(429, {"responseStatus": 429, "responseDetails": "QUOTA"}),
    )
    monkeypatch.setattr(requests, "Session", lambda: session)

    translate = ct.ENGINES["mymemory"]("en", "hu")

    assert translate("hi") == "szia"
    assert session.calls[0]["params"] == {"q": "hi", "langpair": "en|hu"}
    assert translate("hi again").startswith("[failed:")
