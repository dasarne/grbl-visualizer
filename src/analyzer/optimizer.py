"""G-Code optimization hints."""

from dataclasses import dataclass, field


@dataclass
class OptimizationHint:
    """A suggestion for improving the G-Code program."""

    description: str
    estimated_saving: str
    line_numbers: list[int] = field(default_factory=list)


class GCodeOptimizer:
    """Scans a GCodeProgram and produces optimization hints."""

    def optimize(self, program) -> list[OptimizationHint]:
        """Run all optimization passes and return hints."""
        hints: list[OptimizationHint] = []
        hints.extend(self._find_redundant_rapids(program))
        hints.extend(self._find_repeated_tool_changes(program))
        return hints

    def _find_redundant_rapids(self, program) -> list[OptimizationHint]:
        """Detect consecutive G0 moves whose end-points could be merged.

        Consecutive rapid (G0) lines that each move only in X or Y — but not
        to the same destination — are left as-is.  However, a rapid that
        does not change the XY position at all (e.g. two G0 Z lifts in a row)
        is flagged as redundant because it wastes motion planning overhead.

        Two distinct patterns are detected:

        1. **Z-only duplicate lift**: A G0 that sets Z to the same value as
           the previous G0 (no XY change either), meaning the machine is
           already at the safe height.
        2. **Back-to-back rapids**: Two consecutive G0 commands that could
           theoretically be collapsed into one (same destination reached via
           intermediate waypoint with identical final position).
        """
        hints: list[OptimizationHint] = []

        prev_rapid_line = None
        prev_x: float | None = None
        prev_y: float | None = None
        prev_z: float | None = None

        for line in program.lines:
            cmd = line.command
            if cmd not in ("G0", "G00"):
                if cmd is not None and cmd not in ("G90", "G91", "G21", "G20"):
                    # Reset tracking on any non-trivial non-rapid command.
                    prev_rapid_line = None
                    prev_x = prev_y = prev_z = None
                continue

            cur_x = line.parameters.get('X', prev_x)
            cur_y = line.parameters.get('Y', prev_y)
            cur_z = line.parameters.get('Z', prev_z)

            if (
                prev_rapid_line is not None
                and cur_x == prev_x
                and cur_y == prev_y
                and cur_z == prev_z
            ):
                hints.append(OptimizationHint(
                    description=(
                        f"Redundant rapid move on line {line.line_number}: "
                        f"position unchanged from line {prev_rapid_line}."
                    ),
                    estimated_saving="Remove duplicate G0 to reduce program size.",
                    line_numbers=[prev_rapid_line, line.line_number],
                ))
            else:
                prev_rapid_line = line.line_number
                prev_x, prev_y, prev_z = cur_x, cur_y, cur_z

        return hints

    def _find_repeated_tool_changes(self, program) -> list[OptimizationHint]:
        """Detect M3/M5 spindle-on/off pairs that bracket very few cut moves.

        A tool-change cycle (M5 → M3) is flagged when fewer than two cutting
        moves (G1/G2/G3) appear between a spindle stop (M5) and the next
        spindle start (M3).  This typically indicates an unnecessary pause
        that could be eliminated by reordering operations.
        """
        hints: list[OptimizationHint] = []

        last_m5_line: int | None = None
        cut_count_since_m5 = 0

        for line in program.lines:
            cmd = line.command
            if cmd is None:
                continue

            if cmd == "M5":
                last_m5_line = line.line_number
                cut_count_since_m5 = 0
            elif cmd in ("G1", "G2", "G3", "G01", "G02", "G03"):
                cut_count_since_m5 += 1
            elif cmd in ("M3", "M4") and last_m5_line is not None:
                if cut_count_since_m5 < 2:
                    hints.append(OptimizationHint(
                        description=(
                            f"Unnecessary spindle stop/start between lines "
                            f"{last_m5_line} and {line.line_number} "
                            f"({cut_count_since_m5} cut move(s) in between)."
                        ),
                        estimated_saving=(
                            "Merge adjacent operations to avoid repeated "
                            "spindle stop/start cycles."
                        ),
                        line_numbers=[last_m5_line, line.line_number],
                    ))
                last_m5_line = None
                cut_count_since_m5 = 0

        return hints
