"""G-Code tokenizer (lexer)."""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Types of tokens produced by the G-Code tokenizer."""

    COMMAND = auto()
    PARAMETER = auto()
    COMMENT = auto()
    WHITESPACE = auto()
    UNKNOWN = auto()


@dataclass
class Token:
    """A single lexical token from a G-Code line."""

    type: TokenType
    value: str
    position: int


class GCodeTokenizer:
    """Splits a G-Code line into a stream of Token objects."""

    def tokenize(self, line: str) -> list[Token]:
        """Tokenize a single G-Code line.

        TODO: Implement lexer logic.
        """
        return []
