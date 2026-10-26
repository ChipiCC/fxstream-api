"""Symbol normalization and validation helpers."""

from __future__ import annotations

import re

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,12}/[A-Z0-9]{2,12}$")


def normalize_symbol(value: str) -> str:
    """Normalize a ``BASE/QUOTE`` symbol and raise ``ValueError`` if invalid."""
    normalized = value.strip().upper()
    if not _SYMBOL_RE.fullmatch(normalized):
        raise ValueError(f"invalid symbol {value!r}; expected BASE/QUOTE")
    return normalized


def split_symbol(value: str) -> tuple[str, str]:
    """Return the normalized base and quote currencies of a symbol."""
    base, quote = normalize_symbol(value).split("/", 1)
    return base, quote
