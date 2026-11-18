"""Translation service — kept as the import path the rest of the app uses.

The implementation lives in `app.translators`.
"""

from __future__ import annotations

from app.translators import (
    FAILURE,
    TranslationResult,
    TranslatorBackend,
    TranslatorService,
)

__all__ = [
    "FAILURE",
    "TranslationResult",
    "TranslatorBackend",
    "TranslatorService",
]
