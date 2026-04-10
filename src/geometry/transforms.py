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

    Subtracts the given work-offset from each axis so that the returned
    coordinates are expressed relative to the work origin rather than the
    machine origin.
    """
    return (x - offset_x, y - offset_y, z - offset_z)


def to_screen_coordinates(
    x: float, y: float, scale: float, offset_x: float, offset_y: float
) -> tuple[float, float]:
    """Convert G-Code world coordinates to screen pixel coordinates.

    Applies a uniform ``scale`` factor and then shifts by ``(offset_x,
    offset_y)`` so that the world origin maps to the desired screen position.
    """
    return (x * scale + offset_x, y * scale + offset_y)
