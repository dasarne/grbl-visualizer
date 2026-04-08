"""Tests for src.gcode.parser."""

from src.gcode.parser import GCodeParser, GCodeLine, GCodeProgram


def test_parser_initialization():
    """GCodeParser should initialize without errors."""
    parser = GCodeParser("1.1H")
    assert parser.version_id == "1.1H"


def test_parse_line_stub():
    """parse_line stub must return a GCodeLine without raising."""
    parser = GCodeParser("1.1H")
    result = parser.parse_line("G1 X10 Y0 F500", 1)
    assert isinstance(result, GCodeLine)


def test_gcode_program_dataclass():
    """GCodeProgram must initialize with defaults."""
    program = GCodeProgram()
    assert program.lines == []
    assert program.filename is None
    assert program.metadata == {}
