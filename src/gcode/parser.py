"""G-Code parser for GRBL programs.

Parsing pipeline:
    raw text  →  GCodeTokenizer  →  tokens  →  GCodeParser  →  GCodeProgram
"""

import re
from dataclasses import dataclass, field

# Matches a G-code word: one letter followed by an optional sign and a number.
_WORD_RE = re.compile(r'([A-Za-z])([+-]?\d+(?:\.\d+)?)')


@dataclass
class GCodeLine:
    """Represents a single parsed G-Code line."""

    line_number: int
    raw_line: str
    command: str | None = None
    parameters: dict[str, float] = field(default_factory=dict)
    comment: str | None = None


@dataclass
class GCodeProgram:
    """Represents a complete parsed G-Code program."""

    lines: list[GCodeLine] = field(default_factory=list)
    filename: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class GCodeParser:
    """Parses G-Code text into a structured GCodeProgram."""

    def __init__(self, version_id: str = "1.1H") -> None:
        self.version_id = version_id

    def parse_file(self, filepath: str) -> GCodeProgram:
        """Parse a G-Code file and return a GCodeProgram."""
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
        program = GCodeProgram(filename=filepath)
        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            program.lines.append(self.parse_line(raw_line, line_number))
        return program

    def parse_text(self, content: str) -> GCodeProgram:
        """Parse G-Code text (string) and return a GCodeProgram."""
        program = GCodeProgram()
        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            program.lines.append(self.parse_line(raw_line, line_number))
        return program

    def parse_line(self, line: str, line_number: int) -> GCodeLine:
        """Parse a single G-Code line and return a GCodeLine.

        Strips inline comments (parentheses) and end-of-line comments
        (semicolons), then extracts the first G or M command and all
        letter-value parameter pairs.
        """
        raw_line = line
        working = line.strip()

        # Collect comment text
        comment_parts: list[str] = []

        # Remove parenthetical comments: (...)
        for match in re.finditer(r'\(([^)]*)\)', working):
            text = match.group(1).strip()
            if text:
                comment_parts.append(text)
        working = re.sub(r'\([^)]*\)', '', working)

        # Remove semicolon end-of-line comment
        semi_idx = working.find(';')
        if semi_idx >= 0:
            text = working[semi_idx + 1:].strip()
            if text:
                comment_parts.append(text)
            working = working[:semi_idx]

        comment = ' '.join(comment_parts) if comment_parts else None
        working = working.strip().upper()

        command: str | None = None
        parameters: dict[str, float] = {}

        for match in _WORD_RE.finditer(working):
            letter = match.group(1)
            num_val = float(match.group(2))

            if letter in ('G', 'M'):
                if command is None:
                    # Normalise leading zeros: G01 → G1, but preserve decimals: G38.2 → G38.2
                    if num_val == int(num_val):
                        command = f"{letter}{int(num_val)}"
                    else:
                        command = f"{letter}{num_val}"
            else:
                parameters[letter] = num_val

        return GCodeLine(
            line_number=line_number,
            raw_line=raw_line,
            command=command,
            parameters=parameters,
            comment=comment,
        )

    def validate_program(self, program: GCodeProgram) -> list[str]:
        """Validate a parsed program against the selected GRBL version.

        Returns a list of warning strings.

        TODO: Implement version-specific command validation.
        """
        return []
