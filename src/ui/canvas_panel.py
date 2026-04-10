"""Visualization canvas panel."""

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal, Qt

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity

_SEVERITY_ICON: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "✕",
    WarningSeverity.WARNING: "▲",
    WarningSeverity.INFO: "ℹ",
}


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
        self._placeholder.setWordWrap(True)
        layout.addWidget(self._placeholder)

        self._warning_label = QLabel("")
        self._warning_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet("color: #CC6600; font-size: 11px; padding: 4px;")
        layout.addWidget(self._warning_label)

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

    def show_warnings(self, warnings: list[AnalysisWarning]) -> None:
        """Display a summary of analysis warnings below the canvas."""
        if not warnings:
            self._warning_label.setText("")
            self._warning_label.hide()
            return

        lines: list[str] = []
        for w in warnings:
            icon = _SEVERITY_ICON[w.severity]
            loc = f" (line {w.line_number})" if w.line_number is not None else ""
            lines.append(f"{icon} {w.message}{loc}")

        self._warning_label.setText("\n".join(lines))
        self._warning_label.show()
