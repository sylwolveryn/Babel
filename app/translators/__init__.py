"""Translation providers.

Importing this package registers every provider that ships with the app — now
just the local OPUS-MT one. The import below looks unused and is not: the
module calls `register()` at import time, and that is how the registry gets
populated.
"""

from app.translators import opusmt_provider as _opusmt  # noqa: F401,E402  (registers "opusmt")
from app.translators.base import (
    FAILURE,
    ProviderSpec,
    TranslationResult,
    TranslatorBackend,
    all_providers,
    get,
    known_ids,
    register,
    set_listing_order,
)
from app.translators.service import TranslatorService

# Stated here rather than left to import order, which the import sorter rewrites.
set_listing_order(("opusmt",))

__all__ = [
    "FAILURE",
    "ProviderSpec",
    "TranslationResult",
    "TranslatorBackend",
    "TranslatorService",
    "all_providers",
    "get",
    "known_ids",
    "register",
    "set_listing_order",
]
