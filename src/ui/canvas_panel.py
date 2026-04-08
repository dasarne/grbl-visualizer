"""Visualization canvas panel."""

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal, Qt


class CanvasPanel(QWidget):
    """Side-panel rendering the tool path using matplotlib."""

    segment_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the canvas layout with a placeholder label."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # TODO: Replace placeholder with matplotlib FigureCanvas
        self._placeholder = QLabel("Canvas — tool path will be rendered here")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._placeholder)

    def render_toolpath(self, toolpath) -> None:
        """Render a ToolPath onto the canvas.

        TODO: Implement matplotlib drawing.
        """
        pass

    def highlight_segment(self, line_number: int) -> None:
        """Highlight the path segment corresponding to the given G-Code line.

        TODO: Implement segment selection and redraw.
        """
        pass
