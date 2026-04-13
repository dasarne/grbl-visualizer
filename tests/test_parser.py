"""Tests for src.gcode.parser."""

import pytest
from src.gcode.parser import GCodeParser, GCodeLine, GCodeProgram


def test_parser_initialization():
    """GCodeParser should initialize without errors."""
    parser = GCodeParser("1.1H")
    assert parser.version_id == "1.1H"


def test_parse_line_stub():
    """parse_line must return a GCodeLine without raising."""
    parser = GCodeParser("1.1H")
    result = parser.parse_line("G1 X10 Y0 F500", 1)
    assert isinstance(result, GCodeLine)


def test_gcode_program_dataclass():
    """GCodeProgram must initialize with defaults."""
    program = GCodeProgram()
    assert program.lines == []
    assert program.filename is None
    assert program.metadata == {}


# ---------------------------------------------------------------------------
# parse_line: command extraction
# ---------------------------------------------------------------------------

def test_parse_line_extracts_g1():
    parser = GCodeParser("1.1H")
    line = parser.parse_line("G1 X10 Y5 F300", 1)
    assert line.command == "G1"


def test_parse_line_normalises_leading_zero():
    """G01 must be normalised to G1."""
    parser = GCodeParser("1.1H")
    line = parser.parse_line("G01 X10", 1)
    assert line.command == "G1"


def test_parse_line_g38_decimal():
    """G38.2 must remain G38.2 after normalisation."""
    parser = GCodeParser("1.1H")
    line = parser.parse_line("G38.2 Z-5 F100", 1)
    assert line.command == "G38.2"


def test_parse_line_unsupported_g81():
    """G81 is a drilling cycle unknown to GRBL — command must be extracted."""
    parser = GCodeParser("1.1H")
    line = parser.parse_line("G81 X10 Y10 Z-5 F200", 1)
    assert line.command == "G81"


def test_parse_line_m_command():
    parser = GCodeParser("1.1H")
    line = parser.parse_line("M3 S1000", 1)
    assert line.command == "M3"


# ---------------------------------------------------------------------------
# parse_line: parameter extraction
# ---------------------------------------------------------------------------

def test_parse_line_parameters():
    parser = GCodeParser("1.1H")
    line = parser.parse_line("G1 X10.5 Y-3.2 Z0 F500", 1)
    assert line.parameters["X"] == pytest.approx(10.5)
    assert line.parameters["Y"] == pytest.approx(-3.2)
    assert line.parameters["Z"] == pytest.approx(0.0)
    assert line.parameters["F"] == pytest.approx(500.0)


def test_parse_line_no_parameters_on_comment_only():
    parser = GCodeParser("1.1H")
    line = parser.parse_line("; This is a comment", 1)
    assert line.command is None
    assert line.parameters == {}


def test_parse_line_inline_comment_stripped():
    """Parenthetical comment text is captured but not parsed as parameters."""
    parser = GCodeParser("1.1H")
    line = parser.parse_line("G0 X0 Y0 (move to origin)", 1)
    assert line.command == "G0"
    assert line.comment == "move to origin"
    assert "O" not in line.parameters  # 'origin' must not leak


def test_parse_line_semicolon_comment():
    parser = GCodeParser("1.1H")
    line = parser.parse_line("G21 ; millimeter mode", 1)
    assert line.command == "G21"
    assert "millimeter mode" in (line.comment or "")


def test_parse_line_preserves_raw():
    raw = "G1 X10 Y0 F500"
    parser = GCodeParser("1.1H")
    line = parser.parse_line(raw, 3)
    assert line.raw_line == raw
    assert line.line_number == 3


def test_parse_line_empty():
    parser = GCodeParser("1.1H")
    line = parser.parse_line("", 1)
    assert line.command is None
    assert line.parameters == {}


# ---------------------------------------------------------------------------
# parse_text
# ---------------------------------------------------------------------------

def test_parse_text_line_count(sample_gcode):
    parser = GCodeParser("1.1H")
    program = parser.parse_text(sample_gcode)
    expected_lines = len(sample_gcode.splitlines())
    assert len(program.lines) == expected_lines


def test_parse_text_line_numbers_are_1_based(sample_gcode):
    parser = GCodeParser("1.1H")
    program = parser.parse_text(sample_gcode)
    assert program.lines[0].line_number == 1
    assert program.lines[-1].line_number == len(program.lines)


def test_parse_file(sample_gcode_file):
    parser = GCodeParser("1.1H")
    program = parser.parse_file(sample_gcode_file)
    assert program.filename == sample_gcode_file
    assert len(program.lines) > 0
