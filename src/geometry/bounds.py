"""Bounding box calculation for G-Code programs."""

from __future__ import annotations

from dataclasses import dataclass


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
        """Extent in the Z direction."""
        return self.max_z - self.min_z


def calculate_bounds(program) -> BoundingBox:
    """Calculate the bounding box of a GCodeProgram.

    TODO: Implement coordinate extraction and min/max reduction.
    """
    return BoundingBox(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def format_bounds_info(bounds: BoundingBox) -> str:
    """Return a human-readable description of the workpiece size.

    TODO: Implement formatted output.
    """
    return (
        f"Width: {bounds.width:.2f} mm  "
        f"Height: {bounds.height:.2f} mm  "
        f"Depth: {bounds.depth:.2f} mm"
    )
