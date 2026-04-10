"""Tests for geometry modules."""

import math
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
from src.geometry.path import PathSegment, PathType, ToolPath, build_toolpath, _interpolate_arc
from src.geometry.transforms import apply_work_offset, to_screen_coordinates
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


# ---------------------------------------------------------------------------
# _interpolate_arc
# ---------------------------------------------------------------------------

def test_arc_quarter_circle_ccw():
    """CCW quarter-circle from (10,0) to (0,10) with center at origin."""
    pts = _interpolate_arc(10.0, 0.0, 0.0, 10.0, i=-10.0, j=0.0, cw=False, n_points=32)
    assert len(pts) == 33  # n_points + 1
    # First point must equal start.
    assert math.isclose(pts[0][0], 10.0, abs_tol=1e-6)
    assert math.isclose(pts[0][1], 0.0, abs_tol=1e-6)
    # Last point must equal end.
    assert math.isclose(pts[-1][0], 0.0, abs_tol=1e-6)
    assert math.isclose(pts[-1][1], 10.0, abs_tol=1e-6)
    # All points must lie on the circle of radius 10.
    for x, y in pts:
        assert math.isclose(math.hypot(x, y), 10.0, abs_tol=1e-6)


def test_arc_quarter_circle_cw():
    """CW quarter-circle from (10,0) to (0,-10) with center at origin."""
    pts = _interpolate_arc(10.0, 0.0, 0.0, -10.0, i=-10.0, j=0.0, cw=True, n_points=32)
    assert math.isclose(pts[0][0], 10.0, abs_tol=1e-6)
    assert math.isclose(pts[0][1], 0.0, abs_tol=1e-6)
    assert math.isclose(pts[-1][0], 0.0, abs_tol=1e-6)
    assert math.isclose(pts[-1][1], -10.0, abs_tol=1e-6)
    for x, y in pts:
        assert math.isclose(math.hypot(x, y), 10.0, abs_tol=1e-6)


def test_arc_full_circle():
    """Coincident start/end produces a full circle (arc_points wraps 360°)."""
    pts = _interpolate_arc(10.0, 0.0, 10.0, 0.0, i=-10.0, j=0.0, cw=False, n_points=64)
    # First and last points coincide (full loop).
    assert math.isclose(pts[0][0], pts[-1][0], abs_tol=1e-4)
    assert math.isclose(pts[0][1], pts[-1][1], abs_tol=1e-4)
    # All 65 points stay on the circle.
    for x, y in pts:
        assert math.isclose(math.hypot(x, y), 10.0, abs_tol=1e-4)


def test_arc_degenerate_zero_radius():
    """Zero-radius arc (I=J=0) must fall back to a straight line."""
    pts = _interpolate_arc(0.0, 0.0, 5.0, 0.0, i=0.0, j=0.0, cw=False)
    assert pts == [(0.0, 0.0), (5.0, 0.0)]


# ---------------------------------------------------------------------------
# build_toolpath — G91 incremental mode
# ---------------------------------------------------------------------------

def test_g91_incremental_single_move():
    """G91 X10 Y0 from origin should land at (10, 0)."""
    program = _parse("G91\nG1 X10 Y0 F500\n")
    tp = build_toolpath(program)
    assert len(tp.segments) == 1
    seg = tp.segments[0]
    assert math.isclose(seg.end_x, 10.0, abs_tol=1e-9)
    assert math.isclose(seg.end_y, 0.0, abs_tol=1e-9)


def test_g91_accumulates_position():
    """Two G91 moves of X5 each must land at X10, not X5."""
    program = _parse("G91\nG1 X5 F500\nG1 X5 F500\n")
    tp = build_toolpath(program)
    assert len(tp.segments) == 2
    assert math.isclose(tp.segments[0].end_x, 5.0, abs_tol=1e-9)
    assert math.isclose(tp.segments[1].end_x, 10.0, abs_tol=1e-9)


def test_g91_switch_back_to_g90():
    """G91 followed by G90 should resume absolute interpretation."""
    program = _parse("G0 X10 Y0\nG91\nG1 X5 F500\nG90\nG1 X0 Y0 F500\n")
    tp = build_toolpath(program)
    # After incremental X5 from X10 → X15.
    assert math.isclose(tp.segments[1].end_x, 15.0, abs_tol=1e-9)
    # Absolute G1 X0 Y0 → back to origin.
    assert math.isclose(tp.segments[2].end_x, 0.0, abs_tol=1e-9)
    assert math.isclose(tp.segments[2].end_y, 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# build_toolpath — G2/G3 arc segments store arc_points
# ---------------------------------------------------------------------------

def test_g2_arc_has_arc_points():
    """G2 arc segment must have arc_points populated."""
    program = _parse("G0 X10 Y0\nG2 X0 Y10 I-10 J0 F500\n")
    tp = build_toolpath(program)
    arc_seg = tp.segments[-1]
    assert arc_seg.type == PathType.ARC_CW
    assert arc_seg.arc_points is not None
    assert len(arc_seg.arc_points) > 2


def test_g3_arc_has_arc_points():
    """G3 arc segment must have arc_points populated."""
    program = _parse("G0 X10 Y0\nG3 X0 Y10 I-10 J0 F500\n")
    tp = build_toolpath(program)
    arc_seg = tp.segments[-1]
    assert arc_seg.type == PathType.ARC_CCW
    assert arc_seg.arc_points is not None


def test_linear_segment_has_no_arc_points():
    """G1 segment must not have arc_points."""
    program = _parse("G1 X10 Y0 F500\n")
    tp = build_toolpath(program)
    assert tp.segments[0].arc_points is None


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def test_apply_work_offset_subtracts():
    result = apply_work_offset(10.0, 20.0, 5.0, 2.0, 3.0, 1.0)
    assert result == (8.0, 17.0, 4.0)


def test_apply_work_offset_zero_offset_is_identity():
    result = apply_work_offset(5.0, 6.0, 7.0, 0.0, 0.0, 0.0)
    assert result == (5.0, 6.0, 7.0)


def test_to_screen_coordinates_scale_and_offset():
    x, y = to_screen_coordinates(10.0, 5.0, scale=2.0, offset_x=100.0, offset_y=50.0)
    assert math.isclose(x, 120.0)
    assert math.isclose(y, 60.0)


def test_to_screen_coordinates_identity():
    x, y = to_screen_coordinates(3.0, 4.0, scale=1.0, offset_x=0.0, offset_y=0.0)
    assert math.isclose(x, 3.0)
    assert math.isclose(y, 4.0)
