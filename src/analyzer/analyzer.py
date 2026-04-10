"""G-Code analysis: version compatibility, warnings, and checks."""

from dataclasses import dataclass
from enum import Enum, auto

from ..gcode.commands import ALL_COMMANDS
from ..gcode.grbl_versions import get_version
from ..geometry.bounds import (
    calculate_bounds,
    calculate_z_travel_range,
    infer_xy_origin,
    infer_z_origin,
    XYOrigin,
    ZOrigin,
)

# G-code commands that require a positive feedrate (non-rapid feed moves).
_FEED_MOVE_COMMANDS = frozenset({"G1", "G2", "G3"})

_XY_ORIGIN_LABELS: dict[XYOrigin, str] = {
    XYOrigin.BOTTOM_LEFT: "bottom-left (X≥0, Y≥0)",
    XYOrigin.TOP_LEFT: "top-left (X≥0, Y≤0)",
    XYOrigin.BOTTOM_RIGHT: "bottom-right (X≤0, Y≥0)",
    XYOrigin.TOP_RIGHT: "top-right (X≤0, Y≤0)",
    XYOrigin.CENTER: "center or custom (mixed X/Y signs)",
}


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
        warnings.extend(self._check_missing_origin(program))
        warnings.extend(self._check_workpiece_geometry(program))
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
        """Warn if no explicit work-coordinate origin is established.

        An origin is considered established when the program contains any of:

        * A ``G92`` (Set coordinate offset) command.
        * A ``G0`` or ``G1`` move that explicitly names both ``X0`` and ``Y0``
          (i.e. a homing move to the work origin before cutting).

        If neither pattern is found and the program has at least one motion
        command, an INFO hint is emitted reminding the operator to zero the
        machine before running.
        """
        has_motion = False
        for line in program.lines:
            cmd = line.command
            if cmd is None:
                continue

            # G92 explicitly sets a coordinate-system offset — origin is defined.
            if cmd == "G92":
                return []

            if cmd in ("G0", "G00", "G1", "G01", "G2", "G02", "G3", "G03",
                       "G38.2", "G38.3", "G38.4", "G38.5"):
                has_motion = True
                params = line.parameters
                # A move to X0 Y0 (either axis may be absent if already at 0,
                # but both must be explicitly zero or already zero).
                x_at_zero = params.get('X', None) == 0.0
                y_at_zero = params.get('Y', None) == 0.0
                if x_at_zero and y_at_zero:
                    return []

        if not has_motion:
            return []

        return [AnalysisWarning(
            severity=WarningSeverity.INFO,
            message=(
                "No explicit work-coordinate origin found (no G92 and no "
                "G0/G1 X0 Y0 move). Ensure the machine is zeroed before running."
            ),
            suggestion=(
                "Add 'G92 X0 Y0 Z0' at the start of the program, or jog the "
                "machine to the work origin and zero it before running."
            ),
        )]

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

    def _check_workpiece_geometry(self, program) -> list[AnalysisWarning]:
        """Emit INFO hints about workpiece size and coordinate-origin placement.

        Computes the bounding box of all motion coordinates, then infers:
        * Required workpiece dimensions in X, Y, and Z (thickness).
        * Whether the XY origin is at a corner (bottom-left, top-left, …)
          or inside the workpiece.
        * Whether the Z origin is on the workpiece surface or on the
          sacrificial plate (spoilboard).
        """
        bounds = calculate_bounds(program)
        if bounds is None:
            return []

        z_travel = calculate_z_travel_range(program)

        hints: list[AnalysisWarning] = []

        # --- Workpiece X/Y dimensions ---
        hints.append(AnalysisWarning(
            severity=WarningSeverity.INFO,
            message=(
                f"Workpiece size: {bounds.width:.2f} mm (X) × {bounds.height:.2f} mm (Y)"
            ),
            suggestion="Ensure your stock is at least this large in X and Y.",
        ))

        # --- Workpiece thickness (Z extent) ---
        hints.append(AnalysisWarning(
            severity=WarningSeverity.INFO,
            message=(
                f"Z range: {bounds.min_z:.2f} to {bounds.max_z:.2f} mm "
                f"(thickness: {bounds.depth:.2f} mm)"
            ),
            suggestion="Verify that your workpiece is at least this thick.",
        ))

        # --- XY origin corner ---
        xy_origin = infer_xy_origin(bounds)
        hints.append(AnalysisWarning(
            severity=WarningSeverity.INFO,
            message=(
                f"XY origin appears to be at the "
                f"{_XY_ORIGIN_LABELS[xy_origin]} corner of the workpiece."
            ),
            suggestion="Set your machine zero to match this position before running.",
        ))

        # --- Z origin placement ---
        z_origin = infer_z_origin(bounds, z_travel)
        if z_origin == ZOrigin.SPOILBOARD:
            hints.append(AnalysisWarning(
                severity=WarningSeverity.INFO,
                message="Z origin appears to be on the spoilboard (all Z ≥ 0).",
                suggestion="Touch off Z on the spoilboard surface.",
            ))
        elif z_origin == ZOrigin.WORKPIECE_SURFACE:
            hints.append(AnalysisWarning(
                severity=WarningSeverity.INFO,
                message=(
                    "Z origin appears to be on the workpiece surface "
                    "(Z > 0 = safe height, Z < 0 = cut depth)."
                ),
                suggestion="Touch off Z on the top face of the workpiece.",
            ))
        else:
            hints.append(AnalysisWarning(
                severity=WarningSeverity.INFO,
                message="Z origin placement is ambiguous (all Z ≤ 0).",
                suggestion="Verify your Z zero position before running.",
            ))

        return hints
