"""GRBL command definitions and constants."""

from dataclasses import dataclass, field


MOTION_COMMANDS: dict[str, str] = {
    "G0": "Rapid positioning",
    "G00": "Rapid positioning",
    "G1": "Linear interpolation",
    "G01": "Linear interpolation",
    "G2": "Clockwise arc",
    "G02": "Clockwise arc",
    "G3": "Counter-clockwise arc",
    "G03": "Counter-clockwise arc",
    "G38.2": "Probe toward workpiece (error stop)",
    "G38.3": "Probe toward workpiece (no error)",
    "G38.4": "Probe away from workpiece (error stop)",
    "G38.5": "Probe away from workpiece (no error)",
}

COORDINATE_COMMANDS: dict[str, str] = {
    "G17": "XY plane selection",
    "G18": "ZX plane selection",
    "G19": "YZ plane selection",
    "G20": "Inch units",
    "G21": "Millimeter units",
    "G90": "Absolute positioning",
    "G91": "Incremental positioning",
    "G92": "Set coordinate system offset",
    "G92.1": "Reset G92 offsets",
}

PROGRAM_COMMANDS: dict[str, str] = {
    "M0": "Program pause",
    "M2": "End of program",
    "M30": "End of program with return to start",
}

SPINDLE_COMMANDS: dict[str, str] = {
    "M3": "Spindle on, clockwise",
    "M4": "Spindle on, counter-clockwise",
    "M5": "Spindle stop",
}

# Note: M7 and M8 are only available in GRBL 1.1j
COOLANT_COMMANDS: dict[str, str] = {
    "M7": "Mist coolant on",
    "M8": "Flood coolant on",
    "M9": "All coolant off",
}

ALL_COMMANDS: dict[str, str] = {
    **MOTION_COMMANDS,
    **COORDINATE_COMMANDS,
    **PROGRAM_COMMANDS,
    **SPINDLE_COMMANDS,
    **COOLANT_COMMANDS,
}


@dataclass
class GRBLCommand:
    """Represents a single GRBL G-Code command with metadata."""

    code: str
    description: str
    supported_versions: list[str] = field(default_factory=list)


# Alias for module-level access
class GRBLCommands:
    """Namespace for GRBL command dictionaries."""

    MOTION = MOTION_COMMANDS
    COORDINATE = COORDINATE_COMMANDS
    PROGRAM = PROGRAM_COMMANDS
    SPINDLE = SPINDLE_COMMANDS
    COOLANT = COOLANT_COMMANDS
    ALL = ALL_COMMANDS
