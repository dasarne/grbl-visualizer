"""Tool path construction from parsed G-Code."""

from dataclasses import dataclass, field
from enum import Enum, auto


class PathType(Enum):
    """Classification of a tool-path segment."""

    RAPID = auto()
    CUT = auto()
    ARC_CW = auto()
    ARC_CCW = auto()


@dataclass
class PathSegment:
    """A single segment of the tool path."""

    type: PathType
    start_x: float
    start_y: float
    start_z: float
    end_x: float
    end_y: float
    end_z: float
    line_number: int
    feed_rate: float = 0.0


class ToolPath:
    """Collection of path segments representing the complete tool path."""

    def __init__(self) -> None:
        self.segments: list[PathSegment] = []

    def add_segment(self, segment: PathSegment) -> None:
        """Append a segment to the tool path."""
        self.segments.append(segment)

    def get_segments_for_line(self, line_number: int) -> list[PathSegment]:
        """Return all segments that originate from the given G-Code line."""
        return [s for s in self.segments if s.line_number == line_number]


def build_toolpath(program) -> ToolPath:
    """Build a ToolPath from a GCodeProgram.

    TODO: Implement motion command interpretation.
    """
    return ToolPath()
