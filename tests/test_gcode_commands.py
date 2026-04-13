"""Tests for src.gcode.commands."""

from src.gcode.commands import (
    MOTION_COMMANDS,
    ALL_COMMANDS,
    GRBLCommand,
)


def test_motion_commands_exist():
    """Core motion commands must be present."""
    for code in ("G0", "G1", "G2", "G3"):
        assert code in MOTION_COMMANDS, f"{code} missing from MOTION_COMMANDS"


def test_all_commands_not_empty():
    """ALL_COMMANDS must not be empty."""
    assert len(ALL_COMMANDS) > 0


def test_grbl_command_dataclass():
    """GRBLCommand must be constructible and expose its fields."""
    cmd = GRBLCommand(code="G1", description="Linear interpolation", supported_versions=["1.1H"])
    assert cmd.code == "G1"
    assert cmd.description == "Linear interpolation"
    assert "1.1H" in cmd.supported_versions
