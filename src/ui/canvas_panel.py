"""Visualization canvas panel.

Uses a 2D isometric projection to render the toolpath.  This avoids the
slow and shrink-prone matplotlib 3-D backend and closely matches the visual
style of ncviewer.com: light background, gray grid floor, blue cut moves,
orange rapid moves, and a semi-transparent workpiece surface.

Projection (cabinet / axonometric):
    screen_x = world_x + world_y * cos(30°)
    screen_y = world_z + world_y * sin(30°)

X goes to the right, Y recedes to the upper-right at 30°, Z goes straight up.
"""

from __future__ import annotations

import math

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.patches import Polygon as MplPolygon
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal, Qt

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity
from ..geometry.path import PathType, ToolPath

# ---------------------------------------------------------------------------
# Isometric projection constants
# ---------------------------------------------------------------------------

_C30 = math.cos(math.radians(30))   # ≈ 0.866
_S30 = math.sin(math.radians(30))   # ≈ 0.500


def _proj(x: float, y: float, z: float) -> tuple[float, float]:
    """Map world (x, y, z) → 2-D screen (sx, sy) via axonometric projection."""
    return x + y * _C30, z + y * _S30


def _proj_arrays(
    xs: list[float], ys: list[float], zs: list[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised projection for arrays of world coordinates."""
    xa = np.asarray(xs, dtype=float)
    ya = np.asarray(ys, dtype=float)
    za = np.asarray(zs, dtype=float)
    return xa + ya * _C30, za + ya * _S30


# ---------------------------------------------------------------------------
# Visual style constants
# ---------------------------------------------------------------------------

_BG_COLOR = "#F8F8F8"           # canvas background (nearly white)
_GRID_COLOR = "#CCCCCC"         # floor grid lines
_WORKPIECE_FACE = "#EBEBEB"     # workpiece surface fill
_WORKPIECE_EDGE = "#999999"     # workpiece edge colour
_RAPID_COLOR = "#FF9900"        # orange — rapid positioning (G0)
_CUT_COLOR = "#2244BB"          # blue — linear cut (G1)
_ARC_COLOR = "#2266DD"          # slightly lighter blue — arcs (G2/G3)
_HIGHLIGHT_COLOR = "#EE3300"    # red — currently selected segment
_AX_X = "#CC3333"               # X-axis arrow colour
_AX_Y = "#33AA33"               # Y-axis arrow colour
_AX_Z = "#3366CC"               # Z-axis arrow colour

_SEVERITY_ICON: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "✕",
    WarningSeverity.WARNING: "▲",
    WarningSeverity.INFO: "ℹ",
}

_ARC_TYPES = frozenset({PathType.ARC_CW, PathType.ARC_CCW})
_DEFAULT_SX = (-10.0, 50.0)
_DEFAULT_SY = (-5.0, 30.0)


# ---------------------------------------------------------------------------
# CanvasPanel
# ---------------------------------------------------------------------------

class CanvasPanel(QWidget):
    """Side-panel rendering the tool path using a 2-D isometric projection.

    Switching from matplotlib Axes3D to a plain 2-D axes with a manual
    isometric projection provides two major benefits:

    * **No shrinking on re-draw**: the 3-D colorbar + tight_layout combo
      shrank the axes a little each time ``_redraw()`` was called (e.g. on
      every editor-line selection).  The 2-D approach uses a fixed axes
      rectangle and never adds a colorbar.
    * **Speed**: all line segments are batched into a single
      ``LineCollection`` per layer instead of one ``plot()`` call per
      segment, which is ~10–100× faster for complex toolpaths.
    """

    segment_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toolpath: ToolPath | None = None
        self._highlighted_line: int | None = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the layout: navigation toolbar → canvas → warning label → dims label."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Figure with a fixed axes rectangle — no tight_layout so the axes
        # pixel size never changes between redraws.
        self._figure = Figure(facecolor=_BG_COLOR)
        self._axes = self._figure.add_axes([0.02, 0.04, 0.96, 0.94])
        self._axes.set_facecolor(_BG_COLOR)
        self._axes.set_aspect("equal", adjustable="datalim")
        self._axes.axis("off")

        self._mpl_canvas = FigureCanvasQTAgg(self._figure)
        self._nav_toolbar = NavigationToolbar2QT(self._mpl_canvas, self)
        layout.addWidget(self._nav_toolbar)
        layout.addWidget(self._mpl_canvas, stretch=1)

        self._warning_label = QLabel("")
        self._warning_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet("color: #CC6600; font-size: 11px; padding: 4px;")
        layout.addWidget(self._warning_label, stretch=0)

        self._dims_label = QLabel("")
        self._dims_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._dims_label.setStyleSheet(
            "background: #1E1E2E; color: #CDD6F4; font-size: 12px; "
            "font-weight: bold; padding: 6px 8px; border-radius: 4px;"
        )
        self._dims_label.hide()
        layout.addWidget(self._dims_label, stretch=0)

        self._draw_empty_canvas()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_toolpath(self, toolpath: ToolPath) -> None:
        """Render *toolpath* onto the canvas."""
        self._toolpath = toolpath
        self._highlighted_line = None
        self._redraw()

    def highlight_segment(self, line_number: int) -> None:
        """Highlight the path segment whose G-Code line is *line_number*."""
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

    def _draw_empty_canvas(self) -> None:
        """Show an empty isometric coordinate system (no toolpath loaded)."""
        ax = self._axes
        ax.clear()
        ax.set_facecolor(_BG_COLOR)
        ax.axis("off")
        ox, oy = _proj(0.0, 0.0, 0.0)
        ax.plot(ox, oy, "r+", markersize=10, markeredgewidth=1.5, zorder=5)
        ax.set_xlim(*_DEFAULT_SX)
        ax.set_ylim(*_DEFAULT_SY)
        self._mpl_canvas.draw()

    def _redraw(self) -> None:
        """Clear the axes and repaint the complete isometric toolpath view."""
        ax = self._axes
        ax.clear()
        ax.set_facecolor(_BG_COLOR)
        ax.axis("off")
        ax.set_aspect("equal", adjustable="datalim")

        if not self._toolpath or not self._toolpath.segments:
            ax.set_xlim(*_DEFAULT_SX)
            ax.set_ylim(*_DEFAULT_SY)
            self._mpl_canvas.draw()
            return

        # ------------------------------------------------------------------
        # Collect all world coordinates (for view fit) and cut-only coords
        # (for workpiece bounding box and dims label).
        # ------------------------------------------------------------------
        all_wx: list[float] = [0.0]
        all_wy: list[float] = [0.0]
        all_wz: list[float] = [0.0]
        cut_wx: list[float] = []
        cut_wy: list[float] = []
        cut_wz: list[float] = []

        cut_segs = [s for s in self._toolpath.segments if s.type != PathType.RAPID]

        for seg in self._toolpath.segments:
            is_cut = seg.type != PathType.RAPID
            if seg.arc_points:
                px = [p[0] for p in seg.arc_points]
                py = [p[1] for p in seg.arc_points]
                pz = [p[2] for p in seg.arc_points]
            else:
                px = [seg.start_x, seg.end_x]
                py = [seg.start_y, seg.end_y]
                pz = [seg.start_z, seg.end_z]
            all_wx.extend(px); all_wy.extend(py); all_wz.extend(pz)
            if is_cut:
                cut_wx.extend(px); cut_wy.extend(py); cut_wz.extend(pz)

        # Work-plane Z floor: lowest Z in the cut moves (deepest cut).
        z_floor = min(cut_wz) if cut_wz else 0.0
        wp_xmin = min(cut_wx) if cut_wx else 0.0
        wp_xmax = max(cut_wx) if cut_wx else 0.0
        wp_ymin = min(cut_wy) if cut_wy else 0.0
        wp_ymax = max(cut_wy) if cut_wy else 0.0

        # ------------------------------------------------------------------
        # Layer 1: grid floor
        # ------------------------------------------------------------------
        self._draw_grid_floor(ax, wp_xmin, wp_xmax, wp_ymin, wp_ymax, z_floor)

        # ------------------------------------------------------------------
        # Layer 2: workpiece surface
        # ------------------------------------------------------------------
        self._draw_workpiece_surface(ax, wp_xmin, wp_xmax, wp_ymin, wp_ymax, z_floor)

        # ------------------------------------------------------------------
        # Layer 3: toolpath lines (batched into LineCollections)
        # ------------------------------------------------------------------
        rapid_lines: list[list[tuple[float, float]]] = []
        cut_lines: list[list[tuple[float, float]]] = []
        highlight_lines: list[list[tuple[float, float]]] = []

        for seg in self._toolpath.segments:
            highlighted = seg.line_number == self._highlighted_line
            if seg.arc_points:
                pts = seg.arc_points
                sxs, sys_ = _proj_arrays(
                    [p[0] for p in pts],
                    [p[1] for p in pts],
                    [p[2] for p in pts],
                )
                # Convert arc into small line segments for LineCollection.
                screen_pts = list(zip(sxs.tolist(), sys_.tolist()))
                for i in range(len(screen_pts) - 1):
                    segment_2pt = [screen_pts[i], screen_pts[i + 1]]
                    if highlighted:
                        highlight_lines.append(segment_2pt)
                    elif seg.type == PathType.RAPID:
                        rapid_lines.append(segment_2pt)
                    else:
                        cut_lines.append(segment_2pt)
            else:
                s1 = _proj(seg.start_x, seg.start_y, seg.start_z)
                s2 = _proj(seg.end_x, seg.end_y, seg.end_z)
                segment_2pt = [s1, s2]
                if highlighted:
                    highlight_lines.append(segment_2pt)
                elif seg.type == PathType.RAPID:
                    rapid_lines.append(segment_2pt)
                else:
                    cut_lines.append(segment_2pt)

        if rapid_lines:
            ax.add_collection(LineCollection(
                rapid_lines, colors=_RAPID_COLOR,
                linewidths=0.9, linestyles="--", zorder=4,
            ))
        if cut_lines:
            ax.add_collection(LineCollection(
                cut_lines, colors=_CUT_COLOR,
                linewidths=1.1, zorder=5,
            ))
        if highlight_lines:
            ax.add_collection(LineCollection(
                highlight_lines, colors=_HIGHLIGHT_COLOR,
                linewidths=2.5, zorder=7,
            ))

        # ------------------------------------------------------------------
        # Layer 4: coordinate axis arrows
        # ------------------------------------------------------------------
        self._draw_axis_arrows(ax, wp_xmin, wp_xmax, wp_ymin, wp_ymax, z_floor)

        # ------------------------------------------------------------------
        # Fit view and update dimensions label
        # ------------------------------------------------------------------
        self._fit_view(ax, all_wx, all_wy, all_wz)
        self._update_dims_label(cut_segs)
        self._mpl_canvas.draw()

    def _draw_grid_floor(
        self,
        ax,
        xmin: float, xmax: float,
        ymin: float, ymax: float,
        z_floor: float,
    ) -> None:
        """Draw a regular grid in the XY plane at *z_floor*."""
        pad_x = max((xmax - xmin) * 0.25, 5.0)
        pad_y = max((ymax - ymin) * 0.25, 5.0)
        gxmin, gxmax = xmin - pad_x, xmax + pad_x
        gymin, gymax = ymin - pad_y, ymax + pad_y

        span = max(gxmax - gxmin, gymax - gymin, 1.0)
        raw_step = span / 10.0
        magnitude = 10 ** math.floor(math.log10(raw_step))
        step = next(
            (n * magnitude for n in (1, 2, 5, 10) if raw_step <= n * magnitude),
            10 * magnitude,
        )

        grid_lines: list[list[tuple[float, float]]] = []

        # Lines parallel to the X axis (constant Y, varying X).
        y = math.floor(gymin / step) * step
        while y <= gymax + step * 0.5:
            p1 = _proj(gxmin, y, z_floor)
            p2 = _proj(gxmax, y, z_floor)
            grid_lines.append([p1, p2])
            y += step

        # Lines parallel to the Y axis (constant X, varying Y).
        x = math.floor(gxmin / step) * step
        while x <= gxmax + step * 0.5:
            p1 = _proj(x, gymin, z_floor)
            p2 = _proj(x, gymax, z_floor)
            grid_lines.append([p1, p2])
            x += step

        if grid_lines:
            ax.add_collection(LineCollection(
                grid_lines, colors=_GRID_COLOR, linewidths=0.5, zorder=1,
            ))

    def _draw_workpiece_surface(
        self,
        ax,
        xmin: float, xmax: float,
        ymin: float, ymax: float,
        z_floor: float,
    ) -> None:
        """Draw a semi-transparent rectangle for the workpiece XY surface."""
        if xmin >= xmax or ymin >= ymax:
            return
        corners = [
            _proj(xmin, ymin, z_floor),
            _proj(xmax, ymin, z_floor),
            _proj(xmax, ymax, z_floor),
            _proj(xmin, ymax, z_floor),
        ]
        poly = MplPolygon(
            corners, closed=True,
            facecolor=_WORKPIECE_FACE, edgecolor=_WORKPIECE_EDGE,
            linewidth=1.0, alpha=0.75, zorder=2,
        )
        ax.add_patch(poly)

    def _draw_axis_arrows(
        self,
        ax,
        xmin: float, xmax: float,
        ymin: float, ymax: float,
        z_floor: float,
    ) -> None:
        """Draw small X/Y/Z axis arrows at the world origin."""
        arrow_len = max((xmax - xmin) * 0.06, (ymax - ymin) * 0.06, 3.0)
        ox, oy = _proj(0.0, 0.0, z_floor)
        arrow_kw = dict(width=0.0, head_width=arrow_len * 0.15,
                        head_length=arrow_len * 0.18,
                        length_includes_head=True, zorder=8)

        for (dx, dy, dz), color, label in (
            ((arrow_len, 0, 0), _AX_X, "X"),
            ((0, arrow_len, 0), _AX_Y, "Y"),
            ((0, 0, arrow_len), _AX_Z, "Z"),
        ):
            ex, ey = _proj(dx, dy, dz + z_floor)
            ax.arrow(ox, oy, ex - ox, ey - oy, fc=color, ec=color, **arrow_kw)
            ax.text(ex + (ex - ox) * 0.12, ey + (ey - oy) * 0.12,
                    label, color=color, fontsize=7, fontweight="bold",
                    ha="center", va="center", zorder=9)

        ax.plot(ox, oy, "r+", markersize=8, markeredgewidth=1.5, zorder=9)

    def _fit_view(
        self,
        ax,
        wx: list[float],
        wy: list[float],
        wz: list[float],
    ) -> None:
        """Set 2-D axis limits so that all projected points are visible."""
        if not wx:
            ax.set_xlim(*_DEFAULT_SX)
            ax.set_ylim(*_DEFAULT_SY)
            return

        sxs, sys_ = _proj_arrays(wx, wy, wz)
        sx_min, sx_max = float(sxs.min()), float(sxs.max())
        sy_min, sy_max = float(sys_.min()), float(sys_.max())
        mx = max((sx_max - sx_min) * 0.07, 3.0)
        my = max((sy_max - sy_min) * 0.07, 3.0)
        ax.set_xlim(sx_min - mx, sx_max + mx)
        ax.set_ylim(sy_min - my, sy_max + my)

    def _update_dims_label(self, cut_segs: list) -> None:
        """Show workpiece dimensions (G1/G2/G3 moves only) in the info label."""
        if not cut_segs:
            self._dims_label.hide()
            return

        xs: list[float] = []
        ys: list[float] = []
        zs: list[float] = []
        for s in cut_segs:
            if s.arc_points:
                xs.extend(p[0] for p in s.arc_points)
                ys.extend(p[1] for p in s.arc_points)
                zs.extend(p[2] for p in s.arc_points)
            else:
                xs.extend([s.start_x, s.end_x])
                ys.extend([s.start_y, s.end_y])
                zs.extend([s.start_z, s.end_z])

        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        depth = max(zs) - min(zs)
        self._dims_label.setText(
            f"Werkstück  ·  X: {width:.2f} mm   Y: {height:.2f} mm   Z: {depth:.2f} mm"
        )
        self._dims_label.show()
