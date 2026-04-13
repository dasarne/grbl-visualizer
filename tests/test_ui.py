"""Tests for src.ui modules (import-only; no display required)."""

import os
import pytest


@pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"),
    reason="No display available",
)
def test_main_window_import():
    """MainWindow should be importable."""
    from src.ui.main_window import MainWindow  # noqa: F401
