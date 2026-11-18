"""Builds the registered translators and tries them in order."""

from __future__ import annotations

import dataclasses
import logging

from app.postedit import fix_terms
from app.translators import base
from app.translators.base import (
    FAILURE,
    TranslationResult,
    TranslatorBackend,
    failed,
    unchanged,
)

logger = logging.getLogger(__name__)


class TranslatorService:
    """Translates through every registered provider, in listing order.

    Construction never raises: a provider that cannot be built (its packages
    or models are missing) is logged and skipped, and with nothing left the
    service reports `has_backend` False and every translation fails cleanly,
    carrying the original text through.
    """

    def __init__(self) -> None:
        self._backends: dict[str, TranslatorBackend] = {}
        for spec in base.all_providers():
            try:
                self._backends[spec.id] = spec.build()
            except Exception as e:
                logger.warning("Could not initialise %s: %s", spec.display_name, e)

        if not self.has_backend:
            logger.warning("No translation backend available")

    @classmethod
    def from_config(cls, _config=None) -> TranslatorService:
        """Build for an AppConfig. Nothing in the config chooses the translator
        any more; the argument stays so callers need not care."""
        return cls()

    @property
    def has_backend(self) -> bool:
        return bool(self._backends)

    @property
    def active_ids(self) -> tuple[str, ...]:
        """Provider ids in the order they will be tried."""
        return tuple(self._backends)

    def translate(
        self,
        text: str,
        target_lang: str,
        source_lang: str | None = None,
        context: str | None = None,
    ) -> TranslationResult:
        if not text.strip():
            return unchanged(text, target_lang, source_lang)

        chain = self.active_ids
        if not chain:
            return failed(text, target_lang, source_lang, FAILURE.NO_BACKEND)

        result: TranslationResult | None = None
        refusal: TranslationResult | None = None
        for provider_id in chain:
            result = self._backends[provider_id].translate(text, target_lang, source_lang)
            if result.success:
                fixed = fix_terms(text, result.translated, source_lang, target_lang)
                if fixed != result.translated:
                    logger.debug("Post-edit: %r -> %r", result.translated, fixed)
                    result = dataclasses.replace(result, translated=fixed)
                return result
            # A provider that declined to translate — rather than failing to —
            # is the one worth remembering: "the translator declined this
            # message" says more than whatever failed after it.
            if result.error == FAILURE.REFUSED and refusal is None:
                refusal = result
            # The provider id, not the error text: an error can carry the
            # message itself.
            logger.info("Backend %s failed, trying next", provider_id)
            logger.debug("Backend %s error: %s", provider_id, result.error)
        # Every backend failed. A refusal explains itself; anything else, the
        # last failure is the most informative. Either way the original survives.
        return refusal or result  # type: ignore[return-value]
