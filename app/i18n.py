"""Internationalization — the interface is Hungarian only."""

from __future__ import annotations

from typing import ClassVar

from app import locales

#: Key to language to text, assembled from app/locales.
_STRINGS: dict[str, dict[str, str]] = locales.STRINGS

UI_LANGUAGES = {"HU": "Magyar"}

DEFAULT_UI_LANGUAGE = "HU"


class tr:
    """Simple translation helper. Call tr("key") to get localized string."""

    _lang: ClassVar[str] = DEFAULT_UI_LANGUAGE

    @classmethod
    def set_language(cls, lang: str) -> None:
        cls._lang = lang if lang in UI_LANGUAGES else DEFAULT_UI_LANGUAGE

    @classmethod
    def get_language(cls) -> str:
        return cls._lang

    @classmethod
    def __class_getitem__(cls, key: str) -> str:
        """Allow tr["key"] syntax."""
        return cls(key)

    def __new__(cls, key: str, **kwargs: object) -> str:  # type: ignore[misc]
        entry = _STRINGS.get(key)
        if not entry:
            return key
        text = entry.get(cls._lang, entry.get(DEFAULT_UI_LANGUAGE, key))
        if kwargs:
            text = text.format(**kwargs)
        return text


def startup_ui_language(*, config_exists: bool, saved: str) -> str:
    """The language to render in: a saved choice if it is one this build has."""
    if config_exists and saved in UI_LANGUAGES:
        return saved
    return DEFAULT_UI_LANGUAGE
