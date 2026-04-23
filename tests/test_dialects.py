"""Tests for dialect profile registry and GRBL compatibility adapter."""

import pytest

from src.gcode.dialects import (
    DEFAULT_PROFILE_ID,
    get_profile,
    is_command_supported,
    list_profile_ids,
    list_profiles,
)
from src.gcode.grbl_versions import (
    DEFAULT_VERSION,
    GRBL_VERSIONS,
    get_version,
)


def test_default_profile_matches_existing_default_version():
    assert DEFAULT_PROFILE_ID == DEFAULT_VERSION


def test_list_grbl_profile_ids_matches_existing_versions():
    assert list_profile_ids("grbl") == GRBL_VERSIONS


def test_get_profile_returns_grbl_profile():
    profile = get_profile("1.1H")
    assert profile.family == "grbl"
    assert profile.profile_id == "1.1H"
    assert profile.version_id == "1.1H"


def test_unknown_profile_raises_value_error():
    with pytest.raises(ValueError):
        get_profile("does-not-exist")


def test_is_command_supported_for_grbl_profiles():
    assert is_command_supported("G1", "1.1H") is True
    assert is_command_supported("G38.2", "1.1H") is False


def test_list_profiles_returns_profile_objects():
    profiles = list_profiles("grbl")
    assert profiles
    assert all(p.family == "grbl" for p in profiles)


def test_get_version_compatibility_wrapper_uses_profile_registry():
    version = get_version("1.1j")
    assert version.profile_id == "1.1j"
    assert "M9" in version.supported_commands
