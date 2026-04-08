"""Tests for geometry modules."""

from src.geometry.bounds import BoundingBox
from src.geometry.path import PathSegment, PathType, ToolPath


def test_bounding_box_properties():
    """BoundingBox width/height/depth properties must compute correctly."""
    bb = BoundingBox(min_x=0, min_y=0, min_z=0, max_x=10, max_y=20, max_z=5)
    assert bb.width == 10
    assert bb.height == 20
    assert bb.depth == 5


def test_path_segment_creation():
    """PathSegment must be constructable with expected field values."""
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
