"""Shared pytest fixtures for the GCode Lisa test suite."""

import pytest


@pytest.fixture
def sample_gcode() -> str:
    """Return a minimal but valid G-Code program string."""
    return (
        "G21 ; Set units to millimeters\n"
        "G90 ; Absolute positioning\n"
        "G0 Z5 ; Safe height\n"
        "G0 X0 Y0 ; Move to origin\n"
        "M3 S1000 ; Start spindle\n"
        "G1 Z-1 F100 ; Plunge\n"
        "G1 X10 Y0 F500 ; Cut right\n"
        "G0 Z5 ; Lift\n"
        "M5 ; Stop spindle\n"
        "M30 ; End program\n"
    )


@pytest.fixture
def sample_gcode_file(tmp_path, sample_gcode) -> str:
    """Write sample_gcode to a temporary file and return its path."""
    gcode_file = tmp_path / "test.gcode"
    gcode_file.write_text(sample_gcode, encoding="utf-8")
    return str(gcode_file)


@pytest.fixture
def grbl_version() -> str:
    """Return the default GRBL version used in tests."""
    return "1.1H"
