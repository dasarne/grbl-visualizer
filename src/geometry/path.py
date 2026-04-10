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


# G-code motion commands and their mapping to PathType.
_MOTION_COMMANDS: dict[str, PathType] = {
    "G0": PathType.RAPID,
    "G1": PathType.CUT,
    "G2": PathType.ARC_CW,
    "G3": PathType.ARC_CCW,
}


def build_toolpath(program) -> ToolPath:
    """Build a ToolPath by simulating modal G-code execution.

    Tracks the current tool position and active motion command across lines.
    Only lines that carry a motion command (G0/G1/G2/G3) produce segments;
    axes not mentioned on a line retain their previous values (modal axes).
    """
    toolpath = ToolPath()

    # Modal state — machine starts at the origin with G0 active.
    cur_x = 0.0
    cur_y = 0.0
    cur_z = 0.0
    cur_feed = 0.0
    cur_motion = "G0"

    for line in program.lines:
        # Update modal feedrate whenever an F word appears.
        if 'F' in line.parameters:
            cur_feed = line.parameters['F']

        cmd = line.command
        if cmd is None:
            continue

        # Update active motion command if a new one is given.
        if cmd in _MOTION_COMMANDS:
            cur_motion = cmd
        else:
            # Non-motion command (M, G21, G90, …) — no segment.
            continue

        # Resolve target coordinates using modal (sticky) values.
        new_x = line.parameters.get('X', cur_x)
        new_y = line.parameters.get('Y', cur_y)
        new_z = line.parameters.get('Z', cur_z)

        # Skip null moves (position unchanged).
        if new_x == cur_x and new_y == cur_y and new_z == cur_z:
            continue

        toolpath.add_segment(PathSegment(
            type=_MOTION_COMMANDS[cur_motion],
            start_x=cur_x,
            start_y=cur_y,
            start_z=cur_z,
            end_x=new_x,
            end_y=new_y,
            end_z=new_z,
            line_number=line.line_number,
            feed_rate=cur_feed,
        ))

        cur_x, cur_y, cur_z = new_x, new_y, new_z

    return toolpath
