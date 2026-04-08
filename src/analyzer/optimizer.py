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
        """Run all optimization passes and return hints.

        TODO: Aggregate results from individual passes.
        """
        return []

    def _find_redundant_rapids(self, program) -> list[OptimizationHint]:
        """Detect consecutive G0 moves that could be combined.

        TODO: Implement rapid consolidation analysis.
        """
        return []

    def _find_repeated_tool_changes(self, program) -> list[OptimizationHint]:
        """Detect tool changes that interrupt otherwise uninterrupted cutting.

        TODO: Implement tool-change pattern detection.
        """
        return []
