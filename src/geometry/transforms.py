"""Coordinate system transforms for G-Code visualization."""

from enum import Enum, auto


class CoordinateSystem(Enum):
    """Coordinate system mode for position interpretation."""

    ABSOLUTE = auto()
    INCREMENTAL = auto()


def apply_work_offset(
    x: float, y: float, z: float,
    offset_x: float, offset_y: float, offset_z: float,
) -> tuple[float, float, float]:
    """Apply a work coordinate offset to machine coordinates.

    TODO: Implement offset application.
    """
    return (x, y, z)


def to_screen_coordinates(
    x: float, y: float, scale: float, offset_x: float, offset_y: float
) -> tuple[float, float]:
    """Convert G-Code world coordinates to screen pixel coordinates.

    TODO: Implement scale and pan transform.
    """
    return (x, y)
