"""Tests for geometry modules."""

import pytest
from src.geometry.bounds import (
    BoundingBox,
    XYOrigin,
    ZOrigin,
    calculate_bounds,
    infer_xy_origin,
    infer_z_origin,
    format_bounds_info,
)
from src.geometry.path import PathSegment, PathType, ToolPath
from src.gcode.parser import GCodeParser


# ---------------------------------------------------------------------------
# BoundingBox dataclass
# ---------------------------------------------------------------------------

def test_bounding_box_properties():
    """BoundingBox width/height/depth properties must compute correctly."""
    bb = BoundingBox(min_x=0, min_y=0, min_z=0, max_x=10, max_y=20, max_z=5)
    assert bb.width == 10
    assert bb.height == 20
    assert bb.depth == 5


# ---------------------------------------------------------------------------
# PathSegment / ToolPath
# ---------------------------------------------------------------------------

def test_path_segment_creation():
    """PathSegment must be constructible with expected field values."""
    seg = PathSegment(
        type=PathType.CUT,
        start_x=0.0, start_y=0.0, start_z=0.0,
        end_x=10.0, end_y=0.0, end_z=0.0,
        line_number=5,
        feed_rate=500.0,
    )
    assert seg.type == PathType.CUT
    assert seg.end_x == 10.0
    assert seg.line_number == 5


def test_pathtype_enum():
    """PathType enum must contain RAPID and CUT."""
    assert PathType.RAPID is not None
    assert PathType.CUT is not None


# ---------------------------------------------------------------------------
# calculate_bounds
# ---------------------------------------------------------------------------

def _parse(gcode: str):
    return GCodeParser("1.1H").parse_text(gcode)


def test_calculate_bounds_no_motion_returns_none():
    program = _parse("; just a comment\nG21\nG90\n")
    assert calculate_bounds(program) is None


def test_calculate_bounds_single_move():
    bb = calculate_bounds(_parse("G0 X10 Y5 Z3"))
    assert bb is not None
    assert bb.max_x == pytest.approx(10.0)
    assert bb.max_y == pytest.approx(5.0)
    assert bb.max_z == pytest.approx(3.0)
    assert bb.min_x == pytest.approx(10.0)
    assert bb.width == pytest.approx(0.0)


def test_calculate_bounds_multiple_moves():
    gcode = "G0 X0 Y0 Z5\nG1 X50 Y30 Z-2 F300\nG0 X0 Y0 Z5\n"
    bb = calculate_bounds(_parse(gcode))
    assert bb is not None
    assert bb.min_x == pytest.approx(0.0)
    assert bb.max_x == pytest.approx(50.0)
    assert bb.min_y == pytest.approx(0.0)
    assert bb.max_y == pytest.approx(30.0)
    assert bb.min_z == pytest.approx(-2.0)
    assert bb.max_z == pytest.approx(5.0)
    assert bb.width == pytest.approx(50.0)
    assert bb.height == pytest.approx(30.0)
    assert bb.depth == pytest.approx(7.0)


def test_calculate_bounds_sample_gcode(sample_gcode):
    bb = calculate_bounds(_parse(sample_gcode))
    assert bb is not None
    assert bb.max_x == pytest.approx(10.0)
    assert bb.min_z < 0   # plunge at Z-1


def test_calculate_bounds_ignores_non_motion_commands():
    """M3, G21, G90 etc. must not contribute coordinates."""
    gcode = "G21\nM3 S1000\nG0 X5 Y5 Z2\n"
    bb = calculate_bounds(_parse(gcode))
    assert bb is not None
    assert bb.max_x == pytest.approx(5.0)
    # S parameter from M3 must not pollute coordinates
    assert bb.min_y == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# infer_xy_origin
# ---------------------------------------------------------------------------

def test_xy_origin_bottom_left():
    bb = BoundingBox(0.0, 0.0, -2.0, 50.0, 30.0, 5.0)
    assert infer_xy_origin(bb) == XYOrigin.BOTTOM_LEFT


def test_xy_origin_top_left():
    bb = BoundingBox(0.0, -30.0, -2.0, 50.0, 0.0, 5.0)
    assert infer_xy_origin(bb) == XYOrigin.TOP_LEFT


def test_xy_origin_bottom_right():
    bb = BoundingBox(-50.0, 0.0, -2.0, 0.0, 30.0, 5.0)
    assert infer_xy_origin(bb) == XYOrigin.BOTTOM_RIGHT


def test_xy_origin_top_right():
    bb = BoundingBox(-50.0, -30.0, -2.0, 0.0, 0.0, 5.0)
    assert infer_xy_origin(bb) == XYOrigin.TOP_RIGHT


def test_xy_origin_center():
    bb = BoundingBox(-25.0, -15.0, -2.0, 25.0, 15.0, 5.0)
    assert infer_xy_origin(bb) == XYOrigin.CENTER


# ---------------------------------------------------------------------------
# infer_z_origin
# ---------------------------------------------------------------------------

def test_z_origin_workpiece_surface():
    """Z > 0 safe height + Z < 0 cut depth → workpiece surface."""
    bb = BoundingBox(0.0, 0.0, -3.0, 50.0, 30.0, 5.0)
    assert infer_z_origin(bb) == ZOrigin.WORKPIECE_SURFACE


def test_z_origin_spoilboard():
    """All Z ≥ 0 → spoilboard."""
    bb = BoundingBox(0.0, 0.0, 0.0, 50.0, 30.0, 20.0)
    assert infer_z_origin(bb) == ZOrigin.SPOILBOARD


def test_z_origin_ambiguous():
    """All Z ≤ 0 → ambiguous."""
    bb = BoundingBox(0.0, 0.0, -10.0, 50.0, 30.0, 0.0)
    assert infer_z_origin(bb) == ZOrigin.AMBIGUOUS


# ---------------------------------------------------------------------------
# format_bounds_info
# ---------------------------------------------------------------------------

def test_format_bounds_info_contains_dimensions():
    bb = BoundingBox(0.0, 0.0, -3.0, 50.0, 30.0, 5.0)
    info = format_bounds_info(bb)
    assert "50.00" in info
    assert "30.00" in info
    assert "8.00" in info  # depth = 5 - (-3) = 8
