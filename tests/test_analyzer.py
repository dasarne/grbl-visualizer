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
