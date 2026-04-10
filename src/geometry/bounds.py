"""Bounding box calculation for G-Code programs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

# Commands that perform actual work inside the material and carry X/Y/Z coordinates.
# G0 (rapid positioning) moves the tool outside the workpiece and must not
# contribute to the workpiece bounding box.  G38.x probing moves are likewise
# excluded because they do not cut material.
_WORK_COMMANDS = frozenset({"G1", "G2", "G3"})


@dataclass
class BoundingBox:
    """Axis-aligned bounding box for a toolpath."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def width(self) -> float:
        """Extent in the X direction."""
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        """Extent in the Y direction."""
        return self.max_y - self.min_y

    @property
    def depth(self) -> float:
        """Extent in the Z direction (absolute, always ≥ 0)."""
        return self.max_z - self.min_z


class XYOrigin(Enum):
    """Inferred position of the XY coordinate origin relative to the workpiece."""

    BOTTOM_LEFT = auto()   # All X ≥ 0, all Y ≥ 0
    TOP_LEFT = auto()      # All X ≥ 0, all Y ≤ 0
    BOTTOM_RIGHT = auto()  # All X ≤ 0, all Y ≥ 0
    TOP_RIGHT = auto()     # All X ≤ 0, all Y ≤ 0
    CENTER = auto()        # Mixed signs — origin inside or at centre of workpiece


class ZOrigin(Enum):
    """Inferred position of the Z coordinate origin."""

    WORKPIECE_SURFACE = auto()  # Z > 0 = safe height, Z < 0 = cut depth
    SPOILBOARD = auto()         # All Z ≥ 0 — Z=0 is the sacrificial plate
    AMBIGUOUS = auto()          # All Z ≤ 0 or no Z coordinates found


# All commands that produce tool motion (used for Z-origin inference only).
_ALL_MOTION_COMMANDS = frozenset({
    "G0", "G1", "G2", "G3",
    "G38.2", "G38.3", "G38.4", "G38.5",
})


def calculate_bounds(program) -> BoundingBox | None:
    """Calculate the axis-aligned bounding box of all *work* motion coordinates.

    Only G1/G2/G3 lines are considered.  G0 rapid-positioning moves travel
    outside the workpiece and must not influence the reported dimensions.
    Returns None when the program contains no work-motion coordinates at all.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []

    for line in program.lines:
        if line.command not in _WORK_COMMANDS:
            continue
        if 'X' in line.parameters:
            xs.append(line.parameters['X'])
        if 'Y' in line.parameters:
            ys.append(line.parameters['Y'])
        if 'Z' in line.parameters:
            zs.append(line.parameters['Z'])

    if not xs and not ys and not zs:
        return None

    # Fall back to 0.0 for axes that are never mentioned explicitly.
    min_x = min(xs) if xs else 0.0
    max_x = max(xs) if xs else 0.0
    min_y = min(ys) if ys else 0.0
    max_y = max(ys) if ys else 0.0
    min_z = min(zs) if zs else 0.0
    max_z = max(zs) if zs else 0.0

    return BoundingBox(min_x, min_y, min_z, max_x, max_y, max_z)


def calculate_z_travel_range(program) -> tuple[float, float] | None:
    """Return the (min_z, max_z) of all motion commands including G0 rapids.

    This is used specifically for Z-origin inference: the safe-height (G0 Zn)
    must be visible to correctly detect a workpiece-surface Z origin even
    though G0 moves are excluded from the workpiece bounding box.
    Returns None when no Z value is found in any motion command.
    """
    zs: list[float] = []
    for line in program.lines:
        if line.command in _ALL_MOTION_COMMANDS and 'Z' in line.parameters:
            zs.append(line.parameters['Z'])
    return (min(zs), max(zs)) if zs else None


def infer_xy_origin(bounds: BoundingBox) -> XYOrigin:
    """Infer the XY origin corner from the sign of coordinate extremes.

    Conventions (assuming a right-handed machine coordinate system as seen
    from above, with Y pointing away from the operator):

    * bottom-left  → X ≥ 0, Y ≥ 0  (most common for CNC routers)
    * top-left     → X ≥ 0, Y ≤ 0
    * bottom-right → X ≤ 0, Y ≥ 0
    * top-right    → X ≤ 0, Y ≤ 0
    * center       → mixed signs (origin inside workpiece)
    """
    x_nonneg = bounds.min_x >= 0
    x_nonpos = bounds.max_x <= 0
    y_nonneg = bounds.min_y >= 0
    y_nonpos = bounds.max_y <= 0

    if x_nonneg and y_nonneg:
        return XYOrigin.BOTTOM_LEFT
    if x_nonneg and y_nonpos:
        return XYOrigin.TOP_LEFT
    if x_nonpos and y_nonneg:
        return XYOrigin.BOTTOM_RIGHT
    if x_nonpos and y_nonpos:
        return XYOrigin.TOP_RIGHT
    return XYOrigin.CENTER


def infer_z_origin(
    bounds: BoundingBox,
    z_travel_range: tuple[float, float] | None = None,
) -> ZOrigin:
    """Infer whether the Z origin is on the workpiece surface or spoilboard.

    ``bounds`` contains only the work-move (G1/G2/G3) extents.  Because G0
    rapid moves travel to the safe height *above* the workpiece, they are not
    in ``bounds`` but are required to detect the "workpiece surface" origin
    pattern (Z > 0 safe height + Z < 0 cut depth).

    Pass the result of :func:`calculate_z_travel_range` as ``z_travel_range``
    to include G0 Z values in the Z-origin detection.  When omitted, only
    ``bounds`` is consulted.

    * workpiece-surface: max_z > 0 (safe height) and min_z < 0 (cut depth)
    * spoilboard:        all Z ≥ 0 — Z=0 is the sacrificial plate
    * ambiguous:         all Z ≤ 0 or no Z coordinates found
    """
    z_min = bounds.min_z
    z_max = bounds.max_z
    if z_travel_range is not None:
        z_min = min(z_min, z_travel_range[0])
        z_max = max(z_max, z_travel_range[1])

    if z_min >= 0:
        return ZOrigin.SPOILBOARD
    if z_max > 0:
        return ZOrigin.WORKPIECE_SURFACE
    return ZOrigin.AMBIGUOUS


def format_bounds_info(bounds: BoundingBox) -> str:
    """Return a human-readable description of the workpiece dimensions (cut moves only)."""
    return (
        f"X: {bounds.width:.2f} mm  "
        f"Y: {bounds.height:.2f} mm  "
        f"Z: {bounds.depth:.2f} mm"
    )
