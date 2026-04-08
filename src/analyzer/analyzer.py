"""G-Code analysis: version compatibility, warnings, and checks."""

from dataclasses import dataclass
from enum import Enum, auto


class WarningSeverity(Enum):
    """Severity level for an analysis warning."""

    INFO = auto()
    WARNING = auto()
    ERROR = auto()


@dataclass
class AnalysisWarning:
    """A single warning produced by the analyzer."""

    severity: WarningSeverity
    message: str
    line_number: int | None = None
    suggestion: str | None = None


class GCodeAnalyzer:
    """Analyzes a GCodeProgram and produces a list of warnings."""

    def __init__(self, version_id: str = "1.1H") -> None:
        self.version_id = version_id

    def analyze(self, program) -> list[AnalysisWarning]:
        """Run all checks and return the combined warning list.

        TODO: Call individual check methods and aggregate results.
        """
        return []

    def _check_version_compatibility(self, program) -> list[AnalysisWarning]:
        """Check for commands unsupported by the selected GRBL version.

        TODO: Implement per-line command lookup against version map.
        """
        return []

    def _check_missing_origin(self, program) -> list[AnalysisWarning]:
        """Warn if no explicit origin (G92 or G0 X0 Y0) is set.

        TODO: Implement origin detection heuristic.
        """
        return []

    def _check_feed_rates(self, program) -> list[AnalysisWarning]:
        """Warn about missing or suspicious feed rates on cut moves.

        TODO: Implement feed rate validation.
        """
        return []
