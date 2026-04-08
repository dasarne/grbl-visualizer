"""GRBL version feature matrix and version-aware helpers."""

from dataclasses import dataclass, field

GRBL_VERSIONS: list[str] = ["1.1", "1.1H", "1.1j"]
DEFAULT_VERSION: str = "1.1H"


@dataclass
class GRBLVersion:
    """Describes the capabilities of a specific GRBL firmware version."""

    version_id: str
    name: str
    description: str
    supported_commands: set[str] = field(default_factory=set)
    unsupported_commands: set[str] = field(default_factory=set)
    notes: str = ""


GRBL_1_1 = GRBLVersion(
    version_id="1.1",
    name="GRBL 1.1",
    description="Standard GRBL 1.1 release",
    supported_commands={"G0", "G1", "G2", "G3", "G38.2", "G38.3", "G38.4", "G38.5", "M3", "M4", "M5"},
    unsupported_commands={"M7", "M8"},
    notes="No coolant support.",
)

GRBL_1_1H = GRBLVersion(
    version_id="1.1H",
    name="GRBL 1.1H",
    description="Hobbyist variant — no probing, no coolant",
    supported_commands={"G0", "G1", "G2", "G3", "M3", "M4", "M5"},
    unsupported_commands={"G38.2", "G38.3", "G38.4", "G38.5", "M7", "M8"},
    notes="Probing (G38.x) and coolant (M7/M8) are not available.",
)

GRBL_1_1J = GRBLVersion(
    version_id="1.1j",
    name="GRBL 1.1j",
    description="Most feature-complete GRBL 1.1 variant",
    supported_commands={
        "G0", "G1", "G2", "G3",
        "G38.2", "G38.3", "G38.4", "G38.5",
        "M3", "M4", "M5", "M7", "M8", "M9",
    },
    unsupported_commands=set(),
    notes="Full feature set including probing and coolant.",
)

VERSION_MAP: dict[str, GRBLVersion] = {
    "1.1": GRBL_1_1,
    "1.1H": GRBL_1_1H,
    "1.1j": GRBL_1_1J,
}


class GRBLVersions:
    """Namespace for GRBL version constants."""

    V1_1 = GRBL_1_1
    V1_1H = GRBL_1_1H
    V1_1J = GRBL_1_1J
    ALL = GRBL_VERSIONS
    DEFAULT = DEFAULT_VERSION


def get_version(version_id: str) -> GRBLVersion:
    """Return the GRBLVersion for the given version_id."""
    if version_id not in VERSION_MAP:
        raise ValueError(f"Unknown GRBL version: {version_id!r}. Valid: {GRBL_VERSIONS}")
    return VERSION_MAP[version_id]


def is_command_supported(command: str, version_id: str) -> bool:
    """Return True if the command is supported in the given GRBL version."""
    version = get_version(version_id)
    return command not in version.unsupported_commands
