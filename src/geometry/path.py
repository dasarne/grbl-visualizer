"""Tool path construction from parsed G-Code."""

import math as _math
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
    # Interpolated arc waypoints (x, y, z); None for linear segments.
    arc_points: list[tuple[float, float, float]] | None = field(default=None)


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

_ARC_COMMANDS = frozenset({"G2", "G3"})


def _interpolate_arc(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    i: float,
    j: float,
    cw: bool,
    n_points: int = 32,
) -> list[tuple[float, float]]:
    """Interpolate a circular arc defined by I/J center offsets.

    Returns a list of (x, y) waypoints from start to end.
    Falls back to ``[start, end]`` for degenerate arcs (zero radius).
    """
    cx = start_x + i
    cy = start_y + j
    r = _math.hypot(i, j)

    if r < 1e-9:
        return [(start_x, start_y), (end_x, end_y)]

    start_angle = _math.atan2(start_y - cy, start_x - cx)
    end_angle = _math.atan2(end_y - cy, end_x - cx)

    if cw:
        # Clockwise: angles decrease.
        if end_angle >= start_angle:
            end_angle -= 2 * _math.pi
        # Full circle when start and end coincide.
        if abs(end_angle - start_angle) < 1e-9:
            end_angle = start_angle - 2 * _math.pi
    else:
        # Counter-clockwise: angles increase.
        if end_angle <= start_angle:
            end_angle += 2 * _math.pi
        # Full circle when start and end coincide.
        if abs(end_angle - start_angle) < 1e-9:
            end_angle = start_angle + 2 * _math.pi

    sweep = end_angle - start_angle
    points: list[tuple[float, float]] = []
    for k in range(n_points + 1):
        t = k / n_points
        angle = start_angle + t * sweep
        points.append((cx + r * _math.cos(angle), cy + r * _math.sin(angle)))
    return points


def build_toolpath(program) -> ToolPath:
    """Build a ToolPath by simulating modal G-code execution.

    Tracks the current tool position and active motion command across lines.
    Only lines that carry a motion command (G0/G1/G2/G3) produce segments.

    Supports:
    * G90 absolute positioning (default).
    * G91 incremental positioning — each axis value is treated as an offset
      from the current position.
    * G2/G3 arcs interpolated via I/J center offsets; waypoints are stored in
      ``PathSegment.arc_points`` for rendering.
    """
    toolpath = ToolPath()

    # Modal state — machine starts at the origin with G0 / absolute mode active.
    cur_x = 0.0
    cur_y = 0.0
    cur_z = 0.0
    cur_feed = 0.0
    cur_motion = "G0"
    coord_mode = "G90"  # G90 = absolute, G91 = incremental

    for line in program.lines:
        # Update modal feedrate whenever an F word appears.
        if 'F' in line.parameters:
            cur_feed = line.parameters['F']

        cmd = line.command
        if cmd is None:
            continue

        # Handle coordinate-mode switches.
        if cmd == "G90":
            coord_mode = "G90"
            continue
        if cmd == "G91":
            coord_mode = "G91"
            continue

        # Update active motion command if a new one is given.
        if cmd in _MOTION_COMMANDS:
            cur_motion = cmd
        else:
            # Non-motion command (M, G21, …) — no segment.
            continue

        # Resolve target coordinates.
        if coord_mode == "G91":
            # Incremental: values are offsets; missing axes contribute 0.
            new_x = cur_x + line.parameters.get('X', 0.0)
            new_y = cur_y + line.parameters.get('Y', 0.0)
            new_z = cur_z + line.parameters.get('Z', 0.0)
        else:
            # Absolute: missing axes retain their current (modal) value.
            new_x = line.parameters.get('X', cur_x)
            new_y = line.parameters.get('Y', cur_y)
            new_z = line.parameters.get('Z', cur_z)

        # Skip null moves — but allow arcs with coincident start/end (full circles).
        if cur_motion not in _ARC_COMMANDS:
            if new_x == cur_x and new_y == cur_y and new_z == cur_z:
                continue

        # Interpolate arcs; linear moves have no arc_points.
        arc_pts: list[tuple[float, float, float]] | None = None
        if cur_motion in _ARC_COMMANDS:
            i_off = line.parameters.get('I', 0.0)
            j_off = line.parameters.get('J', 0.0)
            xy_pts = _interpolate_arc(
                cur_x, cur_y, new_x, new_y,
                i_off, j_off,
                cw=(cur_motion == "G2"),
            )
            n = len(xy_pts)
            arc_pts = [
                (
                    xy_pts[k][0],
                    xy_pts[k][1],
                    cur_z + (new_z - cur_z) * k / (n - 1) if n > 1 else cur_z,
                )
                for k in range(n)
            ]

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
            arc_points=arc_pts,
        ))

        cur_x, cur_y, cur_z = new_x, new_y, new_z

    return toolpath
