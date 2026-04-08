"""Tests for src.analyzer.analyzer."""

from src.analyzer.analyzer import GCodeAnalyzer, WarningSeverity, AnalysisWarning


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
