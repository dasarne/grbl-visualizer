"""G-Code analysis: version compatibility, warnings, and checks."""

from dataclasses import dataclass
from enum import Enum, auto

from ..gcode.commands import ALL_COMMANDS
from ..gcode.grbl_versions import get_version

# G-code commands that require a positive feedrate (non-rapid feed moves).
_FEED_MOVE_COMMANDS = frozenset({"G1", "G2", "G3"})


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
        """Run all checks and return the combined warning list."""
        warnings: list[AnalysisWarning] = []
        warnings.extend(self._check_version_compatibility(program))
        warnings.extend(self._check_feed_rates(program))
        return warnings

    def _check_version_compatibility(self, program) -> list[AnalysisWarning]:
        """Check for commands unsupported by the selected GRBL version.

        Produces an ERROR for commands that GRBL does not know at all
        (e.g. G81), and a WARNING for commands that exist in GRBL but are
        disabled in the currently selected firmware variant (e.g. G38.2 on
        GRBL 1.1H).
        """
        warnings: list[AnalysisWarning] = []
        version = get_version(self.version_id)

        for gcode_line in program.lines:
            cmd = gcode_line.command
            if cmd is None:
                continue

            if cmd not in ALL_COMMANDS:
                warnings.append(AnalysisWarning(
                    severity=WarningSeverity.ERROR,
                    message=f"{cmd} is not supported by GRBL",
                    line_number=gcode_line.line_number,
                    suggestion="Remove or replace with a GRBL-compatible command.",
                ))
            elif cmd in version.unsupported_commands:
                warnings.append(AnalysisWarning(
                    severity=WarningSeverity.WARNING,
                    message=f"{cmd} is not supported by GRBL {self.version_id}",
                    line_number=gcode_line.line_number,
                    suggestion=f"Use GRBL 1.1j for full command support.",
                ))

        return warnings

    def _check_missing_origin(self, program) -> list[AnalysisWarning]:
        """Warn if no explicit origin (G92 or G0 X0 Y0) is set.

        TODO: Implement origin detection heuristic.
        """
        return []

    def _check_feed_rates(self, program) -> list[AnalysisWarning]:
        """Warn about missing or zero feed rates on cut moves (G1/G2/G3)."""
        warnings: list[AnalysisWarning] = []
        current_feed: float | None = None

        for gcode_line in program.lines:
            # Update modal feedrate whenever an F word appears on any line.
            if 'F' in gcode_line.parameters:
                current_feed = gcode_line.parameters['F']

            cmd = gcode_line.command
            if cmd not in _FEED_MOVE_COMMANDS:
                continue

            if current_feed is None:
                warnings.append(AnalysisWarning(
                    severity=WarningSeverity.WARNING,
                    message=f"{cmd} has no feedrate — add an F parameter",
                    line_number=gcode_line.line_number,
                    suggestion="Specify a positive feedrate, e.g. F500.",
                ))
            elif current_feed == 0.0:
                warnings.append(AnalysisWarning(
                    severity=WarningSeverity.WARNING,
                    message=f"{cmd} has a feedrate of 0 — machine will not move",
                    line_number=gcode_line.line_number,
                    suggestion="Set a positive feedrate, e.g. F500.",
                ))

        return warnings
