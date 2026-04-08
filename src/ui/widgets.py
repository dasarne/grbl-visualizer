"""Reusable custom UI widgets."""

from PyQt6.QtWidgets import QComboBox, QLabel, QWidget
from PyQt6.QtCore import Qt

from ..gcode.grbl_versions import GRBL_VERSIONS


class GRBLVersionSelector(QComboBox):
    """Combo box pre-populated with the supported GRBL versions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.addItems(GRBL_VERSIONS)


class LineNumberBar(QWidget):
    """Stub widget for displaying line numbers alongside the code editor.

    TODO: Implement QPainter-based line number rendering.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)


class StatusIndicator(QLabel):
    """A colored status label for showing connection/parse state."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_ok(self) -> None:
        """Display a green OK status."""
        self.setStyleSheet("color: green; font-weight: bold;")

    def set_warning(self) -> None:
        """Display an amber warning status."""
        self.setStyleSheet("color: orange; font-weight: bold;")

    def set_error(self) -> None:
        """Display a red error status."""
        self.setStyleSheet("color: red; font-weight: bold;")
