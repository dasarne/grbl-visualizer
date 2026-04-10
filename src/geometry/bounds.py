"""Bounding box calculation for G-Code programs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

# Commands that explicitly move the tool and may carry X/Y/Z coordinates.
_MOTION_COMMANDS = frozenset({
    "G0", "G1", "G2", "G3",
    "G38.2", "G38.3", "G38.4", "G38.5",
})


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


def calculate_bounds(program) -> BoundingBox | None:
    """Calculate the axis-aligned bounding box of all motion coordinates.

    Scans every G0/G1/G2/G3/G38.x line and records the explicitly stated
    X, Y, and Z values.  Returns None when the program contains no motion
    coordinates at all.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []

    for line in program.lines:
        if line.command not in _MOTION_COMMANDS:
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


def infer_z_origin(bounds: BoundingBox) -> ZOrigin:
    """Infer whether the Z origin is on the workpiece surface or spoilboard.

    * workpiece-surface: mixed signs (Z > 0 = safe height above material,
                         Z < 0 = cut depth into material)
    * spoilboard:        all Z ≥ 0 — Z=0 is the sacrificial plate, the
                         workpiece sits on top with positive Z values
    * ambiguous:         all Z ≤ 0 or no Z coordinates present
    """
    if bounds.min_z >= 0:
        return ZOrigin.SPOILBOARD
    if bounds.max_z > 0:
        return ZOrigin.WORKPIECE_SURFACE
    return ZOrigin.AMBIGUOUS


def format_bounds_info(bounds: BoundingBox) -> str:
    """Return a human-readable description of the workpiece size."""
    return (
        f"Width: {bounds.width:.2f} mm  "
        f"Height: {bounds.height:.2f} mm  "
        f"Depth: {bounds.depth:.2f} mm"
    )
