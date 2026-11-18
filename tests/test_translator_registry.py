"""The provider registry and the service that builds from it.

There is one real provider now, the local OPUS-MT one. The registry stays
because it is what lets the service build without naming it, and what lets
these tests put fakes in its place.
"""

from __future__ import annotations

import json
import logging

import pytest

from app.config import AppConfig
from app.translators import base
from app.translators.base import FAILURE, ProviderSpec, TranslationResult
from app.translators.service import TranslatorService


class FakeBackend:
    """A backend that answers however the test needs it to."""

    def __init__(self, name: str, succeeds: bool = True, error: str = "boom") -> None:
        self.name = name
        self.succeeds = succeeds
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> TranslationResult:
        self.calls.append((text, target_lang))
        return TranslationResult(
            original=text,
            translated=f"{self.name}:{text}" if self.succeeds else text,
            source_lang=source_lang or "EN",
            target_lang=target_lang,
            success=self.succeeds,
            error=None if self.succeeds else self.error,
            backend=self.name,
        )


@pytest.fixture
def registry(monkeypatch):
    """An empty registry for the duration of one test.

    The real one is populated at import time by the provider modules; replacing
    its innards keeps tests from leaking fake providers into each other.
    """
    monkeypatch.setattr(base, "_REGISTRY", {})
    monkeypatch.setattr(base, "_ORDER", [])
    return base


def register_fake(registry, provider_id: str, backend: FakeBackend | None = None) -> FakeBackend:
    backend = backend or FakeBackend(provider_id)
    registry.register(ProviderSpec(id=provider_id, display_name=provider_id.title(), build=lambda b=backend: b))
    return backend


# ── the real registry ────────────────────────────────────────────────────────


def test_opusmt_is_the_only_provider():
    import app.translators  # noqa: F401  (registers the providers)

    assert base.known_ids() == ("opusmt",)


def test_with_opusmt_disabled_the_service_has_no_backend():
    """conftest.py sets BABELCHAT_DISABLE_OPUSMT, as every test run must: no
    test may load or convert a model. The service is then empty, and says so
    rather than raising."""
    import os

    from app.translators import opusmt_provider as opus

    assert os.environ.get(opus.DISABLE_ENV)
    service = TranslatorService()

    assert service.has_backend is False
    assert service.active_ids == ()
    result = service.translate("hello", "HU", "EN")
    assert result.success is False
    assert result.error == FAILURE.NO_BACKEND
    assert result.translated == "hello"


# ── registration ─────────────────────────────────────────────────────────────


def test_registration_order_is_the_listing_order(registry):
    register_fake(registry, "second")
    register_fake(registry, "first")
    assert registry.known_ids() == ("second", "first")


def test_registering_the_same_id_twice_is_refused(registry):
    register_fake(registry, "dup")
    with pytest.raises(ValueError, match="already registered"):
        register_fake(registry, "dup")


def test_set_listing_order_ignores_names_it_does_not_know(registry):
    register_fake(registry, "alpha")
    register_fake(registry, "beta")

    base.set_listing_order(("beta", "nonesuch", "alpha"))

    assert base.known_ids() == ("beta", "alpha")


def test_set_listing_order_keeps_unlisted_providers_at_the_end(registry):
    register_fake(registry, "alpha")
    register_fake(registry, "beta")
    register_fake(registry, "gamma")

    base.set_listing_order(("gamma",))

    assert base.known_ids() == ("gamma", "alpha", "beta")


# ── the service ──────────────────────────────────────────────────────────────


def test_the_service_builds_every_registered_provider_in_order(registry):
    register_fake(registry, "alpha")
    register_fake(registry, "beta")

    service = TranslatorService()

    assert service.active_ids == ("alpha", "beta")
    assert service.translate("hi", "HU").backend == "alpha"


def test_a_failure_falls_through_to_the_next_provider(registry):
    failing = register_fake(registry, "alpha", FakeBackend("alpha", succeeds=False))
    working = register_fake(registry, "beta")

    result = TranslatorService().translate("hi", "HU")

    assert result.success is True
    assert result.backend == "beta"
    assert failing.calls and working.calls


def test_when_every_provider_fails_the_last_failure_is_returned_with_the_original(registry):
    register_fake(registry, "alpha", FakeBackend("alpha", succeeds=False, error="alpha_down"))
    register_fake(registry, "beta", FakeBackend("beta", succeeds=False, error="beta_down"))

    result = TranslatorService().translate("hello", "HU")

    assert result.success is False
    assert result.error == "beta_down"
    assert result.translated == "hello", "a failed translation still shows the message"


def test_blank_input_is_returned_without_calling_a_provider(registry):
    backend = register_fake(registry, "alpha")

    result = TranslatorService().translate("   ", "HU")

    assert result.success is True
    assert backend.calls == []


def test_an_empty_registry_reports_no_backend_rather_than_raising(registry):
    service = TranslatorService()

    result = service.translate("hi", "HU")

    assert service.has_backend is False
    assert result.success is False
    assert result.error == FAILURE.NO_BACKEND
    assert result.translated == "hi"


def test_a_provider_that_cannot_be_built_does_not_take_the_others_down(registry, caplog):
    def explode():
        raise RuntimeError("no models")

    registry.register(ProviderSpec(id="broken", display_name="Broken", build=explode))
    register_fake(registry, "alpha")

    service = TranslatorService()

    assert service.active_ids == ("alpha",)
    assert "Broken" in caplog.text


def test_the_failing_backend_id_is_logged_without_its_error_text(registry, caplog):
    """An error can carry the message itself; the log names the provider only."""
    leaky_error = "url=?q=secret+whisper&de=me@example.com"
    register_fake(registry, "leaky", FakeBackend("leaky", succeeds=False, error=leaky_error))
    register_fake(registry, "good")

    with caplog.at_level(logging.INFO):
        TranslatorService().translate("hi", "HU")

    assert "secret+whisper" not in caplog.text
    assert "me@example.com" not in caplog.text
    assert "leaky" in caplog.text


# ── configs from before ──────────────────────────────────────────────────────


def test_a_config_with_old_translator_keys_still_loads(registry, tmp_path):
    """Provider credentials, a translator priority and the OPUS-MT migration
    flag were all config fields once. They are ignored now, not an error."""
    register_fake(registry, "alpha")
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "providers": {"mymemory": {"email": "me@example.com"}, "gigachat": "not-a-dict"},
                "translator_priority": "mymemory",
                "opusmt_offered": True,
                "wow_path": "C:/WoW",
            }
        ),
        encoding="utf-8",
    )

    loaded = AppConfig.load(str(config_file))

    assert loaded.wow_path == "C:/WoW"
    for gone in ("providers", "translator_priority", "opusmt_offered"):
        assert not hasattr(loaded, gone), gone
    assert TranslatorService.from_config(loaded).active_ids == ("alpha",)


def test_a_saved_config_carries_no_translator_settings(tmp_path):
    config_file = tmp_path / "config.json"
    AppConfig().save(str(config_file))

    saved = json.loads(config_file.read_text(encoding="utf-8"))

    for gone in ("providers", "translator_priority", "opusmt_offered"):
        assert gone not in saved, gone
