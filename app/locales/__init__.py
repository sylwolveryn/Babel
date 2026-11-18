"""Interface strings.

The interface is Hungarian only. `STRINGS` keeps the key -> language -> text
shape the rest of the app reads, so adding a language later means adding a
module and a line here.
"""

from __future__ import annotations

from app.locales import hu

#: Language code to the module holding it.
LANGUAGE_MODULES = {"HU": hu}


def build() -> dict[str, dict[str, str]]:
    """Key to language to text, in the order the Hungarian file declares the keys."""
    table: dict[str, dict[str, str]] = {}
    for language, module in LANGUAGE_MODULES.items():
        for key, text in module.STRINGS.items():
            table.setdefault(key, {})[language] = text
    return table


STRINGS = build()
