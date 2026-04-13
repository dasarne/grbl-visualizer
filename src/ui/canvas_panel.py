"""Visualization canvas panel – native QPainter renderer.

Replaces the slow matplotlib backend with a lightweight QWidget that renders
the toolpath directly via Qt's native QPainter.  Benefits over matplotlib:

* **Zero lag on highlight**: ``highlight_segment()`` sets one attribute and
  calls ``update()``.  The next ``paintEvent`` dispatches the highlight colour
  through the already-built line list in microseconds — no re-projection.
* **No size change on click**: the drawing area is the widget's own pixel
  rectangle.  It cannot shrink.
* **Interactive zoom / pan**: mouse wheel zooms around the cursor; left-button
  drag pans.  A "Fit" button resets the view.
* **Fast**: ``QPainter.drawLines()`` is a single native C++ call that renders
  thousands of line segments without Python overhead at render time.

Isometric projection (cabinet / axonometric):
    screen_x =  world_x + world_y × cos(30°)
    screen_y = −(world_z  + world_y × sin(30°))   # Y flipped for Qt coords

X goes to the right, Y recedes to the upper-right at 30°, Z goes up.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QLineF, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QMouseEvent, QPaintEvent, QPainter, QPen,
    QPolygonF, QResizeEvent, QWheelEvent,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity
from ..geometry.path import PathType, ToolPath

# ---------------------------------------------------------------------------
# Isometric projection
# ---------------------------------------------------------------------------

_C30 = math.cos(math.radians(30))   # ≈ 0.866
_S30 = math.sin(math.radians(30))   # ≈ 0.500


def _proj(x: float, y: float, z: float) -> QPointF:
    """Map world (x, y, z) → Qt screen point via axonometric projection."""
    return QPointF(x + y * _C30, -(z + y * _S30))


# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

_BG_COLOR = QColor("#F5F5F5")
_GRID_COLOR = QColor("#CCCCCC")
_WP_FILL = QColor(220, 220, 220, 150)
_WP_EDGE_COLOR = QColor("#AAAAAA")
_RAPID_COLOR = QColor("#FF9900")
_CUT_COLOR = QColor("#2244BB")
_HIGHLIGHT_COLOR = QColor("#EE3300")
_AX_X_COLOR = QColor("#CC3333")
_AX_Y_COLOR = QColor("#33AA33")
_AX_Z_COLOR = QColor("#3366CC")
_TEXT_HINT_COLOR = QColor("#AAAAAA")

_SEVERITY_ICON: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "✕",
    WarningSeverity.WARNING: "▲",
    WarningSeverity.INFO: "ℹ",
}


def _cosmetic_pen(color: QColor, width: float,
                  style: Qt.PenStyle = Qt.PenStyle.SolidLine) -> QPen:
    """Return a cosmetic pen (constant pixel width regardless of zoom)."""
    pen = QPen(color, width, style)
    pen.setCosmetic(True)
    return pen


_PEN_GRID = _cosmetic_pen(_GRID_COLOR, 0.7)
_PEN_WP_EDGE = _cosmetic_pen(_WP_EDGE_COLOR, 1.0)
_PEN_RAPID = _cosmetic_pen(_RAPID_COLOR, 1.2, Qt.PenStyle.DashLine)
_PEN_CUT = _cosmetic_pen(_CUT_COLOR, 1.2)
_PEN_HIGHLIGHT = _cosmetic_pen(_HIGHLIGHT_COLOR, 2.5)
_PEN_AX_X = _cosmetic_pen(_AX_X_COLOR, 1.5)
_PEN_AX_Y = _cosmetic_pen(_AX_Y_COLOR, 1.5)
_PEN_AX_Z = _cosmetic_pen(_AX_Z_COLOR, 1.5)


# ---------------------------------------------------------------------------
# Per-segment geometry cache (projected once, rendered many times)
# ---------------------------------------------------------------------------

@dataclass
class _SegGeom:
    line_number: int | None
    is_rapid: bool
    world_points: list[tuple[float, float, float]]
    points: list[QPointF]   # projected 2-D screen points (2 for linear, N for arc)


# ---------------------------------------------------------------------------
# Grid helper
# ---------------------------------------------------------------------------

def _make_grid_lines(
    xmin: float, xmax: float,
    ymin: float, ymax: float,
    z_floor: float,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Build grid line endpoints in world coords for the XY floor plane."""
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

    lines: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    y = math.floor(gymin / step) * step
    while y <= gymax + step * 0.5:
        lines.append(((gxmin, y, z_floor), (gxmax, y, z_floor)))
        y += step
    x = math.floor(gxmin / step) * step
    while x <= gxmax + step * 0.5:
        lines.append(((x, gymin, z_floor), (x, gymax, z_floor)))
        x += step
    return lines


# ---------------------------------------------------------------------------
# Viewport widget (pure drawing — no labels)
# ---------------------------------------------------------------------------

class _IsometricViewport(QWidget):
    """Renders the isometric toolpath view via QPainter."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(160, 120)
        # No setMouseTracking — we only need move events while a button is held.
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._segs: list[_SegGeom] = []
        self._highlighted: int | None = None
        self._grid_lines: list[QLineF] = []
        self._grid_world: list[
            tuple[tuple[float, float, float], tuple[float, float, float]]
        ] = []
        self._wp_poly: QPolygonF | None = None
        self._wp_world: list[tuple[float, float, float]] = []
        self._cut_bounds: tuple[float, float, float, float, float] | None = None

        # World bounding rect in projected (screen) coords before zoom/pan.
        self._world_rect = QRectF(-10.0, -30.0, 60.0, 40.0)

        # View state.
        self._zoom: float = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._drag_start: QPointF | None = None
        self._pan_at_drag: QPointF | None = None

        # Ctrl + right mouse drag rotates the view like a 3D viewport.
        self._yaw_deg: float = 30.0
        self._pitch_deg: float = 35.26438968
        self._rot_drag_start: QPointF | None = None
        self._yaw_at_drag: float | None = None
        self._pitch_at_drag: float | None = None
        self._rot_anchor_world: tuple[float, float, float] | None = None
        self._rot_anchor_screen: QPointF | None = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_toolpath(self, toolpath: ToolPath) -> None:
        """Pre-project all segments and reset the view."""
        self._build_geometry(toolpath)
        self.fit_view()   # also calls update()

    def set_highlight(self, line_number: int | None) -> None:
        """Change the highlighted line and trigger a repaint."""
        if self._highlighted == line_number:
            return
        self._highlighted = line_number
        self.update()

    def fit_view(self) -> None:
        """Reset zoom/pan so the full toolpath fits in the widget."""
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            return
        r = self._world_rect
        if r.isEmpty():
            self._zoom = 1.0
            self._pan = QPointF(w / 2.0, h / 2.0)
        else:
            margin = max(r.width(), r.height()) * 0.08 + 5.0
            rp = r.adjusted(-margin, -margin, margin, margin)
            self._zoom = min(w / rp.width(), h / rp.height())
            cx = rp.center().x() * self._zoom
            cy = rp.center().y() * self._zoom
            self._pan = QPointF(w / 2.0 - cx, h / 2.0 - cy)
        self.update()

    # ------------------------------------------------------------------
    # Qt events
    # ------------------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fit_view()

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        pos = event.position()
        self._pan = QPointF(
            pos.x() - factor * (pos.x() - self._pan.x()),
            pos.y() - factor * (pos.y() - self._pan.y()),
        )
        self._zoom *= factor
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.RightButton
            and (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            self._rot_drag_start = event.position()
            self._yaw_at_drag = self._yaw_deg
            self._pitch_at_drag = self._pitch_deg
            self._rot_anchor_screen = QPointF(event.position())
            self._rot_anchor_world = self._pick_world_anchor(event.position())
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position()
            self._pan_at_drag = QPointF(self._pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._rot_drag_start is not None
            and self._yaw_at_drag is not None
            and self._pitch_at_drag is not None
        ):
            delta = event.position() - self._rot_drag_start
            sensitivity = 0.35  # degrees per pixel
            self._yaw_deg = self._yaw_at_drag + delta.x() * sensitivity
            self._pitch_deg = self._pitch_at_drag - delta.y() * sensitivity
            self._pitch_deg = max(-89.0, min(89.0, self._pitch_deg))
            self._reproject_geometry()
            if self._rot_anchor_world is not None and self._rot_anchor_screen is not None:
                anchor_proj = self._project(*self._rot_anchor_world)
                self._pan = QPointF(
                    self._rot_anchor_screen.x() - anchor_proj.x() * self._zoom,
                    self._rot_anchor_screen.y() - anchor_proj.y() * self._zoom,
                )
            self.update()
            event.accept()
            return

        if self._drag_start is not None and self._pan_at_drag is not None:
            delta = event.position() - self._drag_start
            self._pan = QPointF(
                self._pan_at_drag.x() + delta.x(),
                self._pan_at_drag.y() + delta.y(),
            )
            self.update()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._rot_drag_start = None
            self._yaw_at_drag = None
            self._pitch_at_drag = None
            self._rot_anchor_world = None
            self._rot_anchor_screen = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self._pan_at_drag = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), _BG_COLOR)

        if not self._segs:
            p.setPen(_cosmetic_pen(_TEXT_HINT_COLOR, 1.0))
            p.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "G-Code Laden um Vorschau zu sehen",
            )
            p.end()
            return

        # Apply view transform (zoom + pan) for all world-space drawing.
        p.save()
        p.translate(self._pan)
        p.scale(self._zoom, self._zoom)

        # Layer 1: grid.
        if self._grid_lines:
            p.setPen(_PEN_GRID)
            p.drawLines(self._grid_lines)

        # Layer 2: workpiece surface.
        if self._wp_poly is not None:
            p.setPen(_PEN_WP_EDGE)
            p.setBrush(QBrush(_WP_FILL))
            p.drawPolygon(self._wp_poly)
            p.setBrush(Qt.BrushStyle.NoBrush)

        # Layer 3: axis arrows.
        self._paint_axes(p)

        # Layer 4: toolpath lines — split into three buckets.
        rapid: list[QLineF] = []
        cut: list[QLineF] = []
        hi: list[QLineF] = []
        hl = self._highlighted
        for seg in self._segs:
            pts = seg.points
            is_hl = seg.line_number == hl
            for i in range(len(pts) - 1):
                ln = QLineF(pts[i], pts[i + 1])
                if is_hl:
                    hi.append(ln)
                elif seg.is_rapid:
                    rapid.append(ln)
                else:
                    cut.append(ln)

        if rapid:
            p.setPen(_PEN_RAPID)
            p.drawLines(rapid)
        if cut:
            p.setPen(_PEN_CUT)
            p.drawLines(cut)
        if hi:
            p.setPen(_PEN_HIGHLIGHT)
            p.drawLines(hi)

        p.restore()
        p.end()

    # ------------------------------------------------------------------
    # Geometry build (called once per toolpath load)
    # ------------------------------------------------------------------

    def _project(self, x: float, y: float, z: float) -> QPointF:
        """Project world point using current yaw/pitch (orthographic)."""
        yaw = math.radians(self._yaw_deg)
        pitch = math.radians(self._pitch_deg)

        cy, sy = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)

        # Yaw around Z axis.
        x1 = x * cy - y * sy
        y1 = x * sy + y * cy
        z1 = z

        # Pitch around X axis.
        x2 = x1
        y2 = y1 * cp - z1 * sp
        z2 = y1 * sp + z1 * cp
        return QPointF(x2, -z2)

    def _pick_world_anchor(self, screen_pos: QPointF) -> tuple[float, float, float] | None:
        """Pick the nearest world point on projected segment polylines."""
        if not self._segs or self._zoom == 0.0:
            return None

        px = (screen_pos.x() - self._pan.x()) / self._zoom
        py = (screen_pos.y() - self._pan.y()) / self._zoom
        click = QPointF(px, py)

        best_dist2 = float("inf")
        best_world: tuple[float, float, float] | None = None

        for seg in self._segs:
            ppts = seg.points
            wpts = seg.world_points
            if len(ppts) < 2 or len(wpts) < 2:
                continue
            for i in range(min(len(ppts), len(wpts)) - 1):
                a = ppts[i]
                b = ppts[i + 1]
                dx = b.x() - a.x()
                dy = b.y() - a.y()
                denom = dx * dx + dy * dy
                if denom <= 1e-12:
                    t = 0.0
                else:
                    t = ((click.x() - a.x()) * dx + (click.y() - a.y()) * dy) / denom
                    t = max(0.0, min(1.0, t))

                qx = a.x() + t * dx
                qy = a.y() + t * dy
                dist2 = (click.x() - qx) ** 2 + (click.y() - qy) ** 2

                if dist2 < best_dist2:
                    wa = wpts[i]
                    wb = wpts[i + 1]
                    best_dist2 = dist2
                    best_world = (
                        wa[0] + t * (wb[0] - wa[0]),
                        wa[1] + t * (wb[1] - wa[1]),
                        wa[2] + t * (wb[2] - wa[2]),
                    )

        return best_world

    def _reproject_geometry(self) -> None:
        """Rebuild projected geometry from cached world-space points."""
        if not self._segs:
            self._grid_lines = []
            self._wp_poly = None
            self._world_rect = QRectF(-10.0, -30.0, 60.0, 40.0)
            return

        all_proj: list[QPointF] = [self._project(0.0, 0.0, 0.0)]

        for seg in self._segs:
            seg.points = [self._project(x, y, z) for (x, y, z) in seg.world_points]
            all_proj.extend(seg.points)

        self._grid_lines = [
            QLineF(self._project(*a), self._project(*b))
            for (a, b) in self._grid_world
        ]

        self._wp_poly = (
            QPolygonF([self._project(*p) for p in self._wp_world])
            if self._wp_world else None
        )

        min_sx = min(q.x() for q in all_proj)
        max_sx = max(q.x() for q in all_proj)
        min_sy = min(q.y() for q in all_proj)
        max_sy = max(q.y() for q in all_proj)
        self._world_rect = QRectF(
            min_sx, min_sy,
            max(max_sx - min_sx, 1.0),
            max(max_sy - min_sy, 1.0),
        )

    def _build_geometry(self, toolpath: ToolPath) -> None:
        """Cache world geometry and project it with the current view rotation."""
        self._segs = []
        self._grid_lines = []
        self._grid_world = []
        self._wp_poly = None
        self._wp_world = []
        self._cut_bounds = None

        if not toolpath or not toolpath.segments:
            self._world_rect = QRectF(-10.0, -30.0, 60.0, 40.0)
            return

        cut_wx: list[float] = []
        cut_wy: list[float] = []
        cut_wz: list[float] = []

        for seg in toolpath.segments:
            is_rapid = seg.type == PathType.RAPID
            if seg.arc_points:
                world_pts = [(p[0], p[1], p[2]) for p in seg.arc_points]
                if not is_rapid:
                    cut_wx.extend(p[0] for p in seg.arc_points)
                    cut_wy.extend(p[1] for p in seg.arc_points)
                    cut_wz.extend(p[2] for p in seg.arc_points)
            else:
                world_pts = [
                    (seg.start_x, seg.start_y, seg.start_z),
                    (seg.end_x, seg.end_y, seg.end_z),
                ]
                if not is_rapid:
                    cut_wx.extend([seg.start_x, seg.end_x])
                    cut_wy.extend([seg.start_y, seg.end_y])
                    cut_wz.extend([seg.start_z, seg.end_z])
            self._segs.append(_SegGeom(
                line_number=seg.line_number,
                is_rapid=is_rapid,
                world_points=world_pts,
                points=[],
            ))

        if cut_wx:
            z_floor = min(cut_wz)
            wx_min, wx_max = min(cut_wx), max(cut_wx)
            wy_min, wy_max = min(cut_wy), max(cut_wy)
            self._cut_bounds = (wx_min, wx_max, wy_min, wy_max, z_floor)

            self._grid_world = _make_grid_lines(wx_min, wx_max, wy_min, wy_max, z_floor)

            if wx_min < wx_max and wy_min < wy_max:
                self._wp_world = [
                    (wx_min, wy_min, z_floor),
                    (wx_max, wy_min, z_floor),
                    (wx_max, wy_max, z_floor),
                    (wx_min, wy_max, z_floor),
                ]

        self._reproject_geometry()

    def _paint_axes(self, p: QPainter) -> None:
        """Draw X / Y / Z axis arrows at the world origin."""
        if self._cut_bounds is not None:
            wx_min, wx_max, wy_min, wy_max, z_floor = self._cut_bounds
            arrow_len = max((wx_max - wx_min) * 0.08, (wy_max - wy_min) * 0.08, 5.0)
        else:
            z_floor, arrow_len = 0.0, 5.0

        o = self._project(0.0, 0.0, z_floor)
        for dx, dy, dz, pen in (
            (arrow_len, 0.0, 0.0, _PEN_AX_X),
            (0.0, arrow_len, 0.0, _PEN_AX_Y),
            (0.0, 0.0, arrow_len, _PEN_AX_Z),
        ):
            e = self._project(dx, dy, dz + z_floor)
            p.setPen(pen)
            p.drawLine(o, e)


# ---------------------------------------------------------------------------
# CanvasPanel  (public widget used by MainWindow — same interface as before)
# ---------------------------------------------------------------------------

class CanvasPanel(QWidget):
    """Tool-path visualization panel using a native QPainter renderer.

    The previous matplotlib backend caused two problems: the canvas shrank a
    little on every editor click (tight_layout + colorbar resizing bug) and
    rendering was slow for complex toolpaths (one ``plot()`` call per segment).

    This implementation uses Qt's own QPainter so that all line segments are
    drawn in a single C++ call per layer.  Interactive zoom and pan are built
    in at zero cost.
    """

    segment_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- toolbar row with Fit button ---
        toolbar = QWidget()
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(4, 2, 4, 2)
        tb.setSpacing(4)
        self._fit_btn = QPushButton("⊞ Fit")
        self._fit_btn.setToolTip("Zoom Zurücksetzen / Alles anzeigen")
        self._fit_btn.setFixedHeight(24)
        self._fit_btn.clicked.connect(self._on_fit)
        tb.addWidget(self._fit_btn)
        tb.addStretch(1)
        layout.addWidget(toolbar)

        # --- drawing viewport ---
        self._viewport = _IsometricViewport()
        layout.addWidget(self._viewport, stretch=1)

        # --- warning label ---
        self._warning_label = QLabel("")
        self._warning_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._warning_label.setWordWrap(True)
        self._warning_label.setStyleSheet(
            "color: #CC6600; font-size: 11px; padding: 4px;"
        )
        layout.addWidget(self._warning_label, stretch=0)

        # --- dimensions label ---
        self._dims_label = QLabel("")
        self._dims_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._dims_label.setStyleSheet(
            "background: #1E1E2E; color: #CDD6F4; font-size: 12px; "
            "font-weight: bold; padding: 6px 8px; border-radius: 4px;"
        )
        self._dims_label.hide()
        layout.addWidget(self._dims_label, stretch=0)

    # ------------------------------------------------------------------
    # Public API  (identical signatures to the old matplotlib CanvasPanel)
    # ------------------------------------------------------------------

    def render_toolpath(self, toolpath: ToolPath) -> None:
        """Render *toolpath* onto the canvas."""
        self._viewport.load_toolpath(toolpath)
        self._update_dims_label(toolpath)

    def highlight_segment(self, line_number: int) -> None:
        """Highlight the segment corresponding to the given G-Code line."""
        self._viewport.set_highlight(line_number)

    def show_warnings(self, warnings: list[AnalysisWarning]) -> None:
        """Display analysis warnings below the canvas."""
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
    # Private
    # ------------------------------------------------------------------

    def _on_fit(self) -> None:
        self._viewport.fit_view()

    def _update_dims_label(self, toolpath: ToolPath | None) -> None:
        """Show workpiece dimensions (G1/G2/G3 only) in the dims label."""
        if not toolpath or not toolpath.segments:
            self._dims_label.hide()
            return
        cut_segs = [s for s in toolpath.segments if s.type != PathType.RAPID]
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
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        d = max(zs) - min(zs)
        self._dims_label.setText(
            f"Werkstück  ·  X: {w:.2f} mm   Y: {h:.2f} mm   Z: {d:.2f} mm"
        )
        self._dims_label.show()
