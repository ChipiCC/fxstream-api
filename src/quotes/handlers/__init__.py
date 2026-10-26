"""Quote endpoint handlers."""

from quotes.handlers.create import create_quote
from quotes.handlers.get import get_quote

__all__ = ["create_quote", "get_quote"]
