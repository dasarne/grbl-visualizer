"""Tests for src.analyzer.analyzer."""

import pytest
from src.analyzer.analyzer import GCodeAnalyzer, WarningSeverity, AnalysisWarning
from src.gcode.parser import GCodeParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _analyze(gcode: str, version: str = "1.1H") -> list[AnalysisWarning]:
    parser = GCodeParser(version)
    program = parser.parse_text(gcode)
    analyzer = GCodeAnalyzer(version)
    return analyzer.analyze(program)


def _by_severity(warnings, severity):
    return [w for w in warnings if w.severity == severity]


# ---------------------------------------------------------------------------
# Dataclass and initialization smoke tests
# ---------------------------------------------------------------------------

def test_analyzer_initialization():
    """GCodeAnalyzer should initialize without errors."""
    analyzer = GCodeAnalyzer("1.1H")
    assert analyzer.version_id == "1.1H"


def test_warning_severity_enum():
    """WarningSeverity must expose INFO, WARNING, and ERROR."""
    assert WarningSeverity.INFO is not None
    assert WarningSeverity.WARNING is not None
    assert WarningSeverity.ERROR is not None


def test_analysis_warning_dataclass():
    """AnalysisWarning must be constructible with expected fields."""
    warning = AnalysisWarning(
        severity=WarningSeverity.WARNING,
        message="Test warning",
        line_number=42,
        suggestion="Fix it",
    )
    assert warning.severity == WarningSeverity.WARNING
    assert warning.message == "Test warning"
    assert warning.line_number == 42


# ---------------------------------------------------------------------------
# Version compatibility checks
# ---------------------------------------------------------------------------

def test_g81_unsupported_by_grbl_produces_error():
    """G81 is a drilling cycle; GRBL does not support it — must be ERROR."""
    warnings = _analyze("G81 X10 Y10 Z-5 F200")
    errors = _by_severity(warnings, WarningSeverity.ERROR)
    assert len(errors) == 1
    assert "G81" in errors[0].message


def test_g81_error_has_correct_line_number():
    gcode = "G0 X0 Y0\nG81 X10 Y10 Z-5 F200\n"
    warnings = _analyze(gcode)
    errors = _by_severity(warnings, WarningSeverity.ERROR)
    assert errors[0].line_number == 2


def test_g38_2_unsupported_on_1_1h_produces_warning():
    """G38.2 (probing) is disabled on GRBL 1.1H — must produce WARNING."""
    warnings = _analyze("G38.2 Z-5 F100", version="1.1H")
    version_warnings = _by_severity(warnings, WarningSeverity.WARNING)
    assert any("G38.2" in w.message for w in version_warnings)


def test_g38_2_supported_on_1_1j_no_warning():
    """G38.2 is fully supported on GRBL 1.1j — must not produce a warning."""
    warnings = _analyze("G38.2 Z-5 F100", version="1.1j")
    assert not any("G38.2" in w.message for w in warnings)


def test_m8_unsupported_on_1_1h_produces_warning():
    """M8 (coolant) is not available on GRBL 1.1H."""
    warnings = _analyze("M8", version="1.1H")
    version_warnings = _by_severity(warnings, WarningSeverity.WARNING)
    assert any("M8" in w.message for w in version_warnings)


def test_valid_program_no_version_errors(sample_gcode):
    """The sample_gcode fixture has no unsupported commands."""
    warnings = _analyze(sample_gcode)
    errors = _by_severity(warnings, WarningSeverity.ERROR)
    assert errors == []


# ---------------------------------------------------------------------------
# Feed rate checks
# ---------------------------------------------------------------------------

def test_g1_without_any_feedrate_warns():
    """G1 with no F ever set must produce a WARNING."""
    warnings = _analyze("G1 X10 Y0")
    feed_warnings = [w for w in warnings if "feedrate" in w.message.lower() or "feed" in w.message.lower()]
    assert len(feed_warnings) >= 1


def test_g1_with_zero_feedrate_warns():
    """G1 F0 must produce a WARNING."""
    warnings = _analyze("G1 X10 Y0 F0")
    feed_warnings = [w for w in warnings if "0" in w.message]
    assert len(feed_warnings) >= 1


def test_g1_with_valid_feedrate_no_warning():
    """G1 with a positive F must not produce a feed-rate warning."""
    warnings = _analyze("G1 X10 Y0 F500")
    feed_warnings = [w for w in warnings if "feedrate" in w.message.lower() or "feed" in w.message.lower() or "F" in w.message]
    assert feed_warnings == []


def test_feedrate_is_modal():
    """F set on a prior line applies to subsequent G1 lines — no warning."""
    gcode = "G1 Z-1 F100\nG1 X10 Y0\n"
    warnings = _analyze(gcode)
    feed_warnings = [w for w in warnings if "feedrate" in w.message.lower() or "feed" in w.message.lower()]
    assert feed_warnings == []


def test_g0_without_feedrate_no_warning():
    """G0 (rapid) does not require an F parameter — must not warn."""
    warnings = _analyze("G0 X0 Y0")
    feed_warnings = [w for w in warnings if "feedrate" in w.message.lower() or "feed" in w.message.lower()]
    assert feed_warnings == []


def test_sample_gcode_no_feed_warnings(sample_gcode):
    """The sample_gcode fixture sets F before every cut — must not warn."""
    warnings = _analyze(sample_gcode)
    feed_warnings = [
        w for w in warnings
        if "feedrate" in w.message.lower() or "feed" in w.message.lower()
    ]
    assert feed_warnings == []



# ---------------------------------------------------------------------------
# Workpiece geometry INFO hints
# ---------------------------------------------------------------------------

def test_workpiece_geometry_info_produced(sample_gcode):
    """analyze() must produce INFO hints for a program with motion commands."""
    warnings = _analyze(sample_gcode)
    infos = _by_severity(warnings, WarningSeverity.INFO)
    assert len(infos) >= 1


def test_workpiece_size_hint_present(sample_gcode):
    """An INFO hint about workpiece X/Y dimensions must be present."""
    warnings = _analyze(sample_gcode)
    assert any("Workpiece size" in w.message for w in warnings)


def test_workpiece_z_range_hint_present(sample_gcode):
    """An INFO hint about the Z range must be present."""
    warnings = _analyze(sample_gcode)
    assert any("Z range" in w.message for w in warnings)


def test_workpiece_xy_origin_hint_present(sample_gcode):
    """An INFO hint about the XY origin corner must be present."""
    warnings = _analyze(sample_gcode)
    assert any("XY origin" in w.message for w in warnings)


def test_workpiece_z_origin_hint_present(sample_gcode):
    """An INFO hint about Z origin placement must be present."""
    warnings = _analyze(sample_gcode)
    assert any("Z origin" in w.message for w in warnings)


def test_workpiece_xy_origin_bottom_left(sample_gcode):
    """sample_gcode has all X≥0, Y≥0 — origin should be inferred as bottom-left."""
    warnings = _analyze(sample_gcode)
    xy_hints = [w for w in warnings if "XY origin" in w.message]
    assert len(xy_hints) == 1
    assert "bottom-left" in xy_hints[0].message


def test_workpiece_z_origin_workpiece_surface(sample_gcode):
    """sample_gcode has Z5 (safe) and Z-1 (cut) — should detect workpiece surface."""
    warnings = _analyze(sample_gcode)
    z_hints = [w for w in warnings if "Z origin" in w.message]
    assert len(z_hints) == 1
    assert "workpiece surface" in z_hints[0].message.lower()


def test_workpiece_geometry_no_info_for_empty_program():
    """A program with no motion lines must produce no geometry INFO hints."""
    warnings = _analyze("G21\nG90\nM30\n")
    assert not any(w.severity == WarningSeverity.INFO for w in warnings)


def test_workpiece_z_origin_spoilboard():
    """All-positive Z values must be recognised as spoilboard origin."""
    gcode = "G0 X0 Y0 Z20\nG1 X50 Y0 Z5 F300\nG0 Z20\n"
    warnings = _analyze(gcode)
    z_hints = [w for w in warnings if "Z origin" in w.message]
    assert len(z_hints) == 1
    assert "spoilboard" in z_hints[0].message.lower()


def test_workpiece_xy_origin_top_left():
    """X≥0, Y≤0 — origin should be top-left."""
    gcode = "G0 X0 Y0 Z5\nG1 X50 Y-30 Z-2 F300\nG0 Z5\n"
    warnings = _analyze(gcode)
    xy_hints = [w for w in warnings if "XY origin" in w.message]
    assert "top-left" in xy_hints[0].message


# ---------------------------------------------------------------------------
# analyze() aggregation
# ---------------------------------------------------------------------------

def test_analyze_aggregates_both_checks():
    """analyze() must return warnings from both compatibility and feed checks."""
    gcode = "G81 X5\nG1 X10\n"
    warnings = _analyze(gcode)
    errors = _by_severity(warnings, WarningSeverity.ERROR)
    feed_warnings = [w for w in warnings if "G1" in w.message or "feedrate" in w.message.lower() or "feed" in w.message.lower()]
    assert len(errors) >= 1      # G81 unsupported
    assert len(feed_warnings) >= 1  # G1 no feedrate


# ---------------------------------------------------------------------------
# Comment extraction (used by CommentPanel)
# ---------------------------------------------------------------------------

def test_comment_extraction_semicolon(sample_gcode):
    """Every semicolon comment in sample_gcode must be captured."""
    from src.gcode.parser import GCodeParser
    program = GCodeParser("1.1H").parse_text(sample_gcode)
    comments = [(l.line_number, l.comment) for l in program.lines if l.comment]
    assert len(comments) == len(sample_gcode.splitlines())  # every line has a comment


def test_comment_extraction_parenthetical():
    """Parenthetical (inline) comments must be captured."""
    from src.gcode.parser import GCodeParser
    program = GCodeParser("1.1H").parse_text("G0 X0 Y0 (move to origin)\n")
    line = program.lines[0]
    assert line.comment == "move to origin"


def test_comment_extraction_no_comment():
    """Lines with no comment must have comment=None."""
    from src.gcode.parser import GCodeParser
    program = GCodeParser("1.1H").parse_text("G1 X10 F500\n")
    assert program.lines[0].comment is None


# ---------------------------------------------------------------------------
# Origin detection (_check_missing_origin)
# ---------------------------------------------------------------------------

def test_origin_detected_via_g92():
    """G92 anywhere in the program suppresses the missing-origin hint."""
    gcode = "G92 X0 Y0 Z0\nG0 X10 Y10\nG1 X20 F500\n"
    warnings = _analyze(gcode)
    missing_hints = [w for w in warnings if "No explicit work-coordinate origin" in w.message]
    assert missing_hints == []


def test_origin_detected_via_move_to_zero():
    """A G0 X0 Y0 move is accepted as an explicit origin."""
    gcode = "G0 X0 Y0\nG1 X10 F500\n"
    warnings = _analyze(gcode)
    missing_hints = [w for w in warnings if "No explicit work-coordinate origin" in w.message]
    assert missing_hints == []


def test_missing_origin_hint_emitted():
    """A program with motion but no G92/X0Y0 should emit an INFO hint."""
    gcode = "G0 X5 Y5\nG1 X50 F500\n"
    warnings = _analyze(gcode)
    missing_hints = [w for w in warnings if "No explicit work-coordinate origin" in w.message]
    assert len(missing_hints) == 1
    assert missing_hints[0].severity == WarningSeverity.INFO


def test_no_motion_no_origin_hint():
    """A program with no motion commands must not produce an origin hint."""
    gcode = "G21\nG90\nM30\n"
    warnings = _analyze(gcode)
    missing_hints = [w for w in warnings if "No explicit work-coordinate origin" in w.message]
    assert missing_hints == []


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def _optimize(gcode: str):
    from src.analyzer.optimizer import GCodeOptimizer
    from src.gcode.parser import GCodeParser
    program = GCodeParser("1.1H").parse_text(gcode)
    return GCodeOptimizer().optimize(program)


def test_optimizer_redundant_rapid_detected():
    """Two consecutive G0 to the same position must flag a redundant move."""
    gcode = "G0 X10 Y5 Z3\nG0 X10 Y5 Z3\n"
    hints = _optimize(gcode)
    assert len(hints) == 1
    assert "Redundant" in hints[0].description
    assert hints[0].line_numbers == [1, 2]


def test_optimizer_no_redundant_rapids_for_different_positions():
    """G0 moves to different positions must not be flagged."""
    gcode = "G0 X10 Y0\nG0 X20 Y0\n"
    hints = _optimize(gcode)
    rapid_hints = [h for h in hints if "Redundant" in h.description]
    assert rapid_hints == []


def test_optimizer_repeated_tool_change_detected():
    """M3, M5, M3 with fewer than 2 cuts must flag an unnecessary stop/start."""
    gcode = "M3 S1000\nG1 X10 F500\nM5\nM3 S1000\nG1 X20 F500\n"
    hints = _optimize(gcode)
    tc_hints = [h for h in hints if "spindle" in h.description.lower()]
    assert len(tc_hints) == 1
    assert 3 in tc_hints[0].line_numbers  # M5 on line 3
    assert 4 in tc_hints[0].line_numbers  # M3 on line 4


def test_optimizer_no_hint_when_many_cuts_between_tool_changes():
    """Multiple cuts between M5 and M3 must not trigger the hint."""
    gcode = "M3 S1000\nM5\nG1 X10 F500\nG1 X20 F500\nM3 S1000\n"
    hints = _optimize(gcode)
    tc_hints = [h for h in hints if "spindle" in h.description.lower()]
    assert tc_hints == []


def test_optimizer_clean_program_no_hints(sample_gcode):
    """The sample_gcode fixture should produce no optimization hints."""
    from src.analyzer.optimizer import GCodeOptimizer
    from src.gcode.parser import GCodeParser
    program = GCodeParser("1.1H").parse_text(sample_gcode)
    hints = GCodeOptimizer().optimize(program)
    assert hints == []


# ---------------------------------------------------------------------------
# validate_program (parser)
# ---------------------------------------------------------------------------

def test_validate_program_flags_unknown_command():
    """G81 is unknown to GRBL — validate_program must flag it."""
    from src.gcode.parser import GCodeParser
    parser = GCodeParser("1.1H")
    program = parser.parse_text("G81 X10 Y10 Z-5 F200\n")
    warnings = parser.validate_program(program)
    assert len(warnings) == 1
    assert "G81" in warnings[0]


def test_validate_program_flags_unsupported_command_for_version():
    """G38.2 is unsupported on 1.1H — validate_program must flag it."""
    from src.gcode.parser import GCodeParser
    parser = GCodeParser("1.1H")
    program = parser.parse_text("G38.2 Z-5 F100\n")
    warnings = parser.validate_program(program)
    assert len(warnings) == 1
    assert "G38.2" in warnings[0]
    assert "1.1H" in warnings[0]


def test_validate_program_clean_for_supported_commands():
    """Supported commands must produce no warnings."""
    from src.gcode.parser import GCodeParser
    parser = GCodeParser("1.1j")
    program = parser.parse_text("G0 X0 Y0\nG1 X10 F500\nG38.2 Z-5 F100\nM3 S1000\n")
    warnings = parser.validate_program(program)
    assert warnings == []


def test_validate_program_includes_line_numbers():
    """Warning strings must reference the correct line number."""
    from src.gcode.parser import GCodeParser
    parser = GCodeParser("1.1H")
    program = parser.parse_text("G0 X0\nG81 X10 Z-5\n")
    warnings = parser.validate_program(program)
    assert any("2" in w for w in warnings)
