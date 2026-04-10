"""Visualization canvas panel."""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal, Qt

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity
from ..geometry.path import PathType, ToolPath

_SEVERITY_ICON: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "✕",
    WarningSeverity.WARNING: "▲",
    WarningSeverity.INFO: "ℹ",
}

# Visual style per motion type.
_SEGMENT_COLOR: dict[PathType, str] = {
    PathType.RAPID: "#AAAAAA",
    PathType.CUT: "#3399FF",
    PathType.ARC_CW: "#33CCAA",
    PathType.ARC_CCW: "#33CCAA",
}
_SEGMENT_LINESTYLE: dict[PathType, str] = {
    PathType.RAPID: "--",
    PathType.CUT: "-",
    PathType.ARC_CW: "-",
    PathType.ARC_CCW: "-",
}
_HIGHLIGHT_COLOR = "#FF9900"

# Default view extent when no toolpath is loaded yet (mm).
_DEFAULT_VIEW = (-10.0, 50.0)


class CanvasPanel(QWidget):
    """Side-panel rendering the tool path using matplotlib."""

    segment_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toolpath: ToolPath | None = None
        self._highlighted_line: int | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the canvas layout with a matplotlib FigureCanvas."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(tight_layout=True)
        self._axes = self._figure.add_subplot(111)
        self._mpl_canvas = FigureCanvasQTAgg(self._figure)
        layout.addWidget(self._mpl_canvas, stretch=1)

        self._warning_label = QLabel("")
        self._warning_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet("color: #CC6600; font-size: 11px; padding: 4px;")
        layout.addWidget(self._warning_label, stretch=0)

        self._draw_empty_canvas()

    # ------------------------------------------------------------------
    # Coordinate system
    # ------------------------------------------------------------------

    def _draw_coordinate_system(self) -> None:
        """Draw X/Y axis lines through the origin, a grid, and axis labels."""
        ax = self._axes
        ax.axhline(0, color="#888888", linewidth=0.8, zorder=1)
        ax.axvline(0, color="#888888", linewidth=0.8, zorder=1)
        ax.plot(0, 0, "r+", markersize=10, markeredgewidth=1.5, zorder=5)
        ax.set_xlabel("X [mm]", fontsize=9)
        ax.set_ylabel("Y [mm]", fontsize=9)
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, linestyle=":", linewidth=0.5, color="#CCCCCC", zorder=0)
        ax.tick_params(labelsize=8)

    def _draw_empty_canvas(self) -> None:
        """Show an empty coordinate system when no toolpath is loaded."""
        self._axes.clear()
        self._draw_coordinate_system()
        self._axes.set_xlim(*_DEFAULT_VIEW)
        self._axes.set_ylim(*_DEFAULT_VIEW)
        self._mpl_canvas.draw()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_toolpath(self, toolpath: ToolPath) -> None:
        """Render a ToolPath onto the canvas."""
        self._toolpath = toolpath
        self._highlighted_line = None
        self._redraw()

    def highlight_segment(self, line_number: int) -> None:
        """Highlight the path segment corresponding to the given G-Code line."""
        self._highlighted_line = line_number
        self._redraw()

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

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        """Clear the axes and repaint all content."""
        self._axes.clear()
        self._draw_coordinate_system()

        if not self._toolpath or not self._toolpath.segments:
            self._axes.set_xlim(*_DEFAULT_VIEW)
            self._axes.set_ylim(*_DEFAULT_VIEW)
            self._mpl_canvas.draw()
            return

        for seg in self._toolpath.segments:
            highlighted = seg.line_number == self._highlighted_line
            color = _HIGHLIGHT_COLOR if highlighted else _SEGMENT_COLOR[seg.type]
            lw = 2.0 if highlighted else 1.0
            self._axes.plot(
                [seg.start_x, seg.end_x],
                [seg.start_y, seg.end_y],
                color=color,
                linewidth=lw,
                linestyle=_SEGMENT_LINESTYLE[seg.type],
                solid_capstyle="round",
                zorder=3 if highlighted else 2,
            )

        self._fit_view()
        self._mpl_canvas.draw()

    def _fit_view(self) -> None:
        """Auto-scale the view to include all segments and the origin."""
        if not self._toolpath or not self._toolpath.segments:
            return

        all_x = (
            [s.start_x for s in self._toolpath.segments]
            + [s.end_x for s in self._toolpath.segments]
            + [0.0]
        )
        all_y = (
            [s.start_y for s in self._toolpath.segments]
            + [s.end_y for s in self._toolpath.segments]
            + [0.0]
        )

        span_x = max(max(all_x) - min(all_x), 1.0)
        span_y = max(max(all_y) - min(all_y), 1.0)
        mx = max(span_x * 0.05, 2.0)
        my = max(span_y * 0.05, 2.0)

        self._axes.set_xlim(min(all_x) - mx, max(all_x) + mx)
        self._axes.set_ylim(min(all_y) - my, max(all_y) + my)
