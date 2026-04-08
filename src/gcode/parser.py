"""G-Code parser for GRBL programs.

Parsing pipeline:
    raw text  →  GCodeTokenizer  →  tokens  →  GCodeParser  →  GCodeProgram
"""

from dataclasses import dataclass, field


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
        """Parse a G-Code file and return a GCodeProgram.

        TODO: Implement file reading and line-by-line parsing.
        """
        return GCodeProgram(filename=filepath)

    def parse_line(self, line: str, line_number: int) -> GCodeLine:
        """Parse a single G-Code line and return a GCodeLine.

        TODO: Implement tokenization and parameter extraction.
        """
        return GCodeLine(line_number=line_number, raw_line=line)

    def validate_program(self, program: GCodeProgram) -> list[str]:
        """Validate a parsed program against the selected GRBL version.

        Returns a list of warning strings.

        TODO: Implement version-specific command validation.
        """
        return []
