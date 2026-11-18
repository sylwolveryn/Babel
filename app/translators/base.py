"""What a translation provider is, and how the app finds out about one.

The app has one translator, the local OPUS-MT models (opusmt_provider.py). It
still declares itself as a `ProviderSpec` in a small registry: the service
builds whatever is registered, and the tests register fakes the same way,
without the service having to know any provider by name.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Result of a translation attempt.

    On failure `translated` holds the original text: every caller renders this
    field, so a failed translation degrades to showing the message untranslated
    rather than showing nothing.
    """

    original: str
    translated: str
    source_lang: str
    target_lang: str
    success: bool
    error: str | None = None
    backend: str = ""


@runtime_checkable
class TranslatorBackend(Protocol):
    """A ready-to-use translator."""

    def translate(self, text: str, target_lang: str, source_lang: str | None = None) -> TranslationResult: ...


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Everything the app needs to know about a provider it has never met."""

    id: str
    display_name: str
    build: Callable[[], TranslatorBackend]


_REGISTRY: dict[str, ProviderSpec] = {}
_ORDER: list[str] = []


def register(spec: ProviderSpec) -> ProviderSpec:
    """Add a provider. Import order decides the listing order until it is set."""
    if spec.id in _REGISTRY:
        raise ValueError(f"provider {spec.id!r} is already registered")
    _REGISTRY[spec.id] = spec
    _ORDER.append(spec.id)
    return spec


def set_listing_order(order: Iterable[str]) -> None:
    """Fix the order providers are tried in.

    Leaving this to import order was a trap: the import sorter rearranged the
    provider imports and silently reordered the chain with them. So the order
    is stated once, explicitly, and anything unlisted keeps its registration
    position at the end.
    """
    wanted = [pid for pid in order if pid in _REGISTRY]
    rest = [pid for pid in _ORDER if pid not in wanted]
    _ORDER[:] = wanted + rest


def get(provider_id: str) -> ProviderSpec | None:
    return _REGISTRY.get(provider_id)


def all_providers() -> tuple[ProviderSpec, ...]:
    return tuple(_REGISTRY[pid] for pid in _ORDER)


def known_ids() -> tuple[str, ...]:
    return tuple(_ORDER)


class FAILURE:
    """Reasons a backend gives up, in one place so callers can match on them."""

    NO_BACKEND = "no_backend"
    AUTH = "auth_failed"
    QUOTA = "quota_exceeded"
    RETRIES = "max_retries_exceeded"
    NO_KEY = "no_key"
    #: The provider answered, and declined. Not a failure of the request — a
    #: refusal to carry it out, which is a different thing to tell the user and
    #: the only failure worth promoting past a later one in the chain.
    #:
    #: It lives here rather than beside the provider that produces it because
    #: two modules need to agree on the exact string, and two literals that must
    #: match are two literals that will eventually not.
    REFUSED = "provider_refused"


def failed(
    text: str,
    target_lang: str,
    source_lang: str | None,
    error: str,
    backend: str = "",
) -> TranslationResult:
    """A failure result carrying the original text through untouched."""
    return TranslationResult(
        original=text,
        translated=text,
        source_lang=source_lang or "",
        target_lang=target_lang,
        success=False,
        error=error,
        backend=backend,
    )


def unchanged(text: str, target_lang: str, source_lang: str | None) -> TranslationResult:
    """A success result for input that needs no translation (blank, whitespace)."""
    return TranslationResult(
        original=text,
        translated=text,
        source_lang=source_lang or "",
        target_lang=target_lang,
        success=True,
    )
