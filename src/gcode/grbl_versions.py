"""GRBL version compatibility layer backed by dialect profiles."""

from .dialects import (
    DialectProfile,
    DEFAULT_PROFILE_ID,
    get_profile,
    is_command_supported as _is_command_supported,
    list_profile_ids,
)

GRBLVersion = DialectProfile
GRBL_VERSIONS: list[str] = list_profile_ids(family="grbl")
DEFAULT_VERSION: str = DEFAULT_PROFILE_ID

GRBL_1_1 = get_profile("1.1")
GRBL_1_1H = get_profile("1.1H")
GRBL_1_1J = get_profile("1.1j")

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
    return get_profile(version_id)


def is_command_supported(command: str, version_id: str) -> bool:
    """Return True if the command is supported in the given GRBL version."""
    return _is_command_supported(command, version_id)
