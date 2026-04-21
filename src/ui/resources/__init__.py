"""UI string resources for GCode Lisa."""

from .strings_de import STRINGS as _DE
from .strings_en import STRINGS as _EN

_LANGUAGES: dict[str, dict[str, str]] = {
    "de": _DE,
    "en": _EN,
}


def get_string(language: str, key: str) -> str:
    """Return the translated string for *key* in *language*.

    Falls back to English if *language* is unknown; falls back to *key*
    itself if the key is missing from both tables.
    """
    return _LANGUAGES.get(language, _EN).get(key, _LANGUAGES["en"].get(key, key))


def get_strings(language: str) -> dict[str, str]:
    """Return the full string map for *language* (falls back to English)."""
    return _LANGUAGES.get(language, _EN)
