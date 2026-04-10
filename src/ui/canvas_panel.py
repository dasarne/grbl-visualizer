"""Visualization canvas panel."""

import matplotlib.cm as _cm
import matplotlib.colors as _mcolors
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  – registers the '3d' projection
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal, Qt

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity
from ..geometry.path import PathType, ToolPath

_SEVERITY_ICON: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "✕",
    WarningSeverity.WARNING: "▲",
    WarningSeverity.INFO: "ℹ",
}

# Visual style for rapid (G0) moves — always gray dashed regardless of Z.
_RAPID_COLOR = "#AAAAAA"
_RAPID_LINESTYLE = "--"
# Style for cut/arc segments when Z-depth coloring is disabled.
_CUT_COLOR = "#3399FF"
_ARC_COLOR = "#33CCAA"
_HIGHLIGHT_COLOR = "#FF9900"

# Colormap used for Z-depth encoding (deep = dark; surface = light).
_Z_CMAP = _cm.get_cmap("Blues_r")

# Default view extent when no toolpath is loaded yet (mm).
_DEFAULT_VIEW = (-10.0, 50.0)

_ARC_TYPES = frozenset({PathType.ARC_CW, PathType.ARC_CCW})


class CanvasPanel(QWidget):
    """Side-panel rendering the tool path using matplotlib."""

    segment_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toolpath: ToolPath | None = None
        self._highlighted_line: int | None = None
        self._colorbar = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the canvas layout with a matplotlib FigureCanvas and navigation toolbar."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(tight_layout=True)
        self._axes = self._figure.add_subplot(111, projection="3d")
        self._mpl_canvas = FigureCanvasQTAgg(self._figure)

        self._nav_toolbar = NavigationToolbar2QT(self._mpl_canvas, self)
        layout.addWidget(self._nav_toolbar)
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
        """Draw axis labels, origin marker, and enable the grid for the 3-D view."""
        ax = self._axes
        ax.plot([0], [0], [0], "r+", markersize=10, markeredgewidth=1.5, zorder=5)
        ax.set_xlabel("X [mm]", fontsize=9)
        ax.set_ylabel("Y [mm]", fontsize=9)
        ax.set_zlabel("Z [mm]", fontsize=9)  # type: ignore[attr-defined]
        ax.tick_params(labelsize=8)

    def _draw_empty_canvas(self) -> None:
        """Show an empty coordinate system when no toolpath is loaded."""
        self._axes.clear()
        self._draw_coordinate_system()
        self._axes.set_xlim(*_DEFAULT_VIEW)
        self._axes.set_ylim(*_DEFAULT_VIEW)
        self._axes.set_zlim(*_DEFAULT_VIEW)  # type: ignore[attr-defined]
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
        # Remove old colorbar before clearing axes so its axes are gone too.
        if self._colorbar is not None:
            self._colorbar.remove()
            self._colorbar = None

        self._axes.clear()
        self._draw_coordinate_system()

        if not self._toolpath or not self._toolpath.segments:
            self._axes.set_xlim(*_DEFAULT_VIEW)
            self._axes.set_ylim(*_DEFAULT_VIEW)
            self._mpl_canvas.draw()
            return

        # Build Z-depth normalizer from all non-rapid segments.
        cut_segs = [s for s in self._toolpath.segments if s.type != PathType.RAPID]
        z_values = [s.start_z for s in cut_segs] + [s.end_z for s in cut_segs]
        use_z_color = bool(z_values) and (max(z_values) - min(z_values)) > 0.01

        if use_z_color:
            norm = _mcolors.Normalize(vmin=min(z_values), vmax=max(z_values))
        else:
            norm = None

        for seg in self._toolpath.segments:
            highlighted = seg.line_number == self._highlighted_line
            lw = 2.0 if highlighted else 1.0
            zorder = 3 if highlighted else 2

            # Choose colour.
            if highlighted:
                color = _HIGHLIGHT_COLOR
            elif seg.type == PathType.RAPID:
                color = _RAPID_COLOR
            elif use_z_color and norm is not None:
                color = _Z_CMAP(norm(seg.start_z))
            elif seg.type in _ARC_TYPES:
                color = _ARC_COLOR
            else:
                color = _CUT_COLOR

            # Choose line style.
            linestyle = _RAPID_LINESTYLE if seg.type == PathType.RAPID else "-"

            # Build coordinate arrays: use arc waypoints (3-tuples) when available.
            if seg.arc_points:
                xs = [p[0] for p in seg.arc_points]
                ys = [p[1] for p in seg.arc_points]
                zs = [p[2] for p in seg.arc_points]
            else:
                xs = [seg.start_x, seg.end_x]
                ys = [seg.start_y, seg.end_y]
                zs = [seg.start_z, seg.end_z]

            self._axes.plot(
                xs, ys, zs,
                color=color,
                linewidth=lw,
                linestyle=linestyle,
                solid_capstyle="round",
                zorder=zorder,
            )

        # Add a colorbar when Z-depth encoding is active.
        if use_z_color and norm is not None:
            sm = _cm.ScalarMappable(cmap=_Z_CMAP, norm=norm)
            sm.set_array([])
            self._colorbar = self._figure.colorbar(
                sm, ax=self._axes, label="Z [mm]", fraction=0.04, pad=0.04
            )

        self._fit_view()
        self._mpl_canvas.draw()

    def _fit_view(self) -> None:
        """Auto-scale the 3-D view to include all segments (including arc waypoints) and origin."""
        if not self._toolpath or not self._toolpath.segments:
            return

        all_x: list[float] = [0.0]
        all_y: list[float] = [0.0]
        all_z: list[float] = [0.0]

        for s in self._toolpath.segments:
            if s.arc_points:
                all_x.extend(p[0] for p in s.arc_points)
                all_y.extend(p[1] for p in s.arc_points)
                all_z.extend(p[2] for p in s.arc_points)
            else:
                all_x.extend([s.start_x, s.end_x])
                all_y.extend([s.start_y, s.end_y])
                all_z.extend([s.start_z, s.end_z])

        span_x = max(max(all_x) - min(all_x), 1.0)
        span_y = max(max(all_y) - min(all_y), 1.0)
        span_z = max(max(all_z) - min(all_z), 1.0)
        mx = max(span_x * 0.05, 2.0)
        my = max(span_y * 0.05, 2.0)
        mz = max(span_z * 0.05, 2.0)

        self._axes.set_xlim(min(all_x) - mx, max(all_x) + mx)
        self._axes.set_ylim(min(all_y) - my, max(all_y) + my)
        self._axes.set_zlim(min(all_z) - mz, max(all_z) + mz)  # type: ignore[attr-defined]
