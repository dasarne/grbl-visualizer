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
from pathlib import Path
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QLineF, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QMouseEvent, QPaintEvent, QPainter, QPen,
    QPolygonF, QResizeEvent, QWheelEvent, QPixmap,
)
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity
from ..geometry.path import PathType, ToolPath
from .warnings_dialog import WarningsDialog

# ---------------------------------------------------------------------------
# Isometric projection
# ---------------------------------------------------------------------------

_C30 = math.cos(math.radians(30))   # ≈ 0.866
_S30 = math.sin(math.radians(30))   # ≈ 0.500


def _proj(x: float, y: float, z: float) -> QPointF:
    """Map world (x, y, z) → Qt screen point via axonometric projection."""
    return QPointF(x + y * _C30, -(z + y * _S30))


def _camera_transform(
    x: float,
    y: float,
    z: float,
    yaw_deg: float,
    pitch_deg: float,
) -> tuple[float, float, float]:
    """Rotate a world point into camera coordinates (x, depth, z)."""
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)

    x1 = x * cy - y * sy
    y1 = x * sy + y * cy
    z1 = z

    x2 = x1
    y2 = y1 * cp - z1 * sp
    z2 = y1 * sp + z1 * cp
    return x2, y2, z2


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


def _nice_integer_step(min_step: float) -> int:
    """Return a human-friendly integer step >= min_step."""
    if min_step <= 1.0:
        return 1

    magnitude = 10 ** math.floor(math.log10(min_step))
    for factor in (1, 2, 5, 10):
        step = factor * magnitude
        if step >= min_step:
            return int(step)
    return int(10 * magnitude)


def _axis_tick_steps(
    start: int,
    end: int,
    unit_screen_px: float,
    max_ticks: int = 20,
) -> tuple[int, int | None]:
    """Return major/minor integer tick steps for an axis span and screen length."""
    span = max(end - start, 1)
    min_major_step = max(1, math.ceil(28.0 / max(unit_screen_px, 1e-6)))
    major_step = max(
        _nice_integer_step(span / max(max_ticks / 2, 1)),
        _nice_integer_step(min_major_step),
    )

    minor_step: int | None = None
    for divisor in (5, 2):
        if major_step % divisor != 0:
            continue
        candidate = major_step // divisor
        if candidate < 1:
            continue
        if candidate * unit_screen_px < 12.0:
            continue
        tick_count = span / candidate + 1
        if tick_count <= max_ticks:
            minor_step = candidate
            break

    return major_step, minor_step


# ---------------------------------------------------------------------------
# Viewport widget (pure drawing — no labels)
# ---------------------------------------------------------------------------

class _IsometricViewport(QWidget):
    """Renders the isometric toolpath view via QPainter."""

    segment_selected = pyqtSignal(int)
    view_orientation_changed = pyqtSignal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(160, 120)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # No setMouseTracking — we only need move events while a button is held.
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._empty_logo = QPixmap()
        assets_dir = Path(__file__).resolve().parents[2] / "assets"
        for name in ("Liza_gray.svg", "Lisa_gray.svg"):
            candidate = assets_dir / name
            if candidate.exists():
                self._empty_logo = QPixmap(str(candidate))
                break

        self._segs: list[_SegGeom] = []
        self._highlighted: int | None = None
        self._grid_lines: list[QLineF] = []
        self._grid_world: list[
            tuple[tuple[float, float, float], tuple[float, float, float]]
        ] = []
        self._wp_poly: QPolygonF | None = None
        self._wp_world: list[tuple[float, float, float]] = []
        self._cut_bounds: tuple[float, float, float, float, float, float] | None = None
        self._axis_overlay_lines: list[tuple[QLineF, QColor]] = []
        self._axis_labels: list[tuple[str, QPointF, QColor]] = []

        # World bounding rect in projected (screen) coords before zoom/pan.
        self._world_rect = QRectF(-10.0, -30.0, 60.0, 40.0)

        # View state.
        self._zoom: float = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._drag_start: QPointF | None = None
        self._pan_at_drag: QPointF | None = None
        self._left_press_pos: QPointF | None = None

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

    def set_view_angles(self, yaw_deg: float, pitch_deg: float, fit: bool = False) -> None:
        """Set the current camera orientation in degrees."""
        self._yaw_deg = yaw_deg
        self._pitch_deg = max(-89.0, min(89.0, pitch_deg))
        self._reproject_geometry()
        if fit:
            self.fit_view()
        else:
            self.update()
        self.view_orientation_changed.emit(self._yaw_deg, self._pitch_deg)

    def set_standard_view(self, face: str) -> None:
        """Switch to a standard orthographic view and fit the toolpath."""
        orientations = {
            "xp": (-90.0, 0.0),
            "xn": (90.0, 0.0),
            "yp": (180.0, 0.0),
            "yn": (0.0, 0.0),
            "zp": (0.0, 89.0),
            "zn": (0.0, -89.0),
            "iso": (30.0, 35.26438968),
        }
        yaw_deg, pitch_deg = orientations.get(face, orientations["iso"])
        self.set_view_angles(yaw_deg, pitch_deg, fit=True)

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
        self.setFocus()

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

        if event.button() == Qt.MouseButton.MiddleButton:
            self._drag_start = event.position()
            self._pan_at_drag = QPointF(self._pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._left_press_pos = QPointF(event.position())
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
            self.view_orientation_changed.emit(self._yaw_deg, self._pitch_deg)
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

        if event.button() == Qt.MouseButton.MiddleButton:
            self._drag_start = None
            self._pan_at_drag = None
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            press_pos = self._left_press_pos
            self._left_press_pos = None
            if press_pos is not None:
                delta = event.position() - press_pos
                if delta.x() * delta.x() + delta.y() * delta.y() <= 16.0:
                    line_number = self._pick_segment_line(event.position())
                    if line_number is not None:
                        self.set_highlight(line_number)
                        self.segment_selected.emit(line_number)
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Home:
            self.set_standard_view("iso")
            event.accept()
            return

        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), _BG_COLOR)

        if not self._segs:
            if not self._empty_logo.isNull():
                target = self.rect().adjusted(24, 24, -24, -24)
                logo = self._empty_logo.scaled(
                    target.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = target.center().x() - logo.width() // 2
                y = target.center().y() - logo.height() // 2
                p.drawPixmap(x, y, logo)
            else:
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

        # Axis overlay is painted in screen space so text and tick size stay readable.
        self._paint_axis_overlay(p)
        p.end()

    # ------------------------------------------------------------------
    # Geometry build (called once per toolpath load)
    # ------------------------------------------------------------------

    def _project(self, x: float, y: float, z: float) -> QPointF:
        """Project world point using current yaw/pitch (orthographic)."""
        x2, _depth, z2 = _camera_transform(x, y, z, self._yaw_deg, self._pitch_deg)
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

    def _pick_segment_line(self, screen_pos: QPointF) -> int | None:
        """Pick the nearest visible segment line within a small screen threshold."""
        if not self._segs or self._zoom == 0.0:
            return None

        px = (screen_pos.x() - self._pan.x()) / self._zoom
        py = (screen_pos.y() - self._pan.y()) / self._zoom
        click = QPointF(px, py)

        best_dist2 = float("inf")
        best_line: int | None = None
        threshold2 = (8.0 / self._zoom) ** 2

        for seg in self._segs:
            if seg.line_number is None or len(seg.points) < 2:
                continue
            for index in range(len(seg.points) - 1):
                a = seg.points[index]
                b = seg.points[index + 1]
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
                    best_dist2 = dist2
                    best_line = seg.line_number

        if best_dist2 <= threshold2:
            return best_line
        return None

    def _reproject_geometry(self) -> None:
        """Rebuild projected geometry from cached world-space points."""
        if not self._segs:
            self._grid_lines = []
            self._wp_poly = None
            self._axis_overlay_lines = []
            self._axis_labels = []
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
            wz_min, wz_max = min(cut_wz), max(cut_wz)
            self._cut_bounds = (wx_min, wx_max, wy_min, wy_max, wz_min, wz_max)

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
        """Draw bounded X/Y/Z axes with unit tick marks from object extents."""
        self._axis_overlay_lines = []
        self._axis_labels = []
        if self._cut_bounds is not None:
            wx_min, wx_max, wy_min, wy_max, wz_min, wz_max = self._cut_bounds
        else:
            wx_min = wy_min = wz_min = 0.0
            wx_max = wy_max = wz_max = 5.0

        def axis_limits(min_value: float, max_value: float) -> tuple[int, int]:
            neg_extent = abs(min(0.0, min_value))
            pos_extent = max(0.0, max_value)

            if neg_extent > pos_extent:
                dominant_extent = max(neg_extent, 1.0)
                pad = max(dominant_extent * 0.05, 1.0)
                start = -math.ceil(dominant_extent + pad)
                end = 0
            else:
                dominant_extent = max(pos_extent, 1.0)
                pad = max(dominant_extent * 0.05, 1.0)
                start = 0
                end = math.ceil(dominant_extent + pad)

            if start == end:
                end += 1
            return start, end

        def to_screen(point: QPointF) -> QPointF:
            return QPointF(
                point.x() * self._zoom + self._pan.x(),
                point.y() * self._zoom + self._pan.y(),
            )

        if self._cut_bounds is not None:
            center_world = (
                (wx_min + wx_max) * 0.5,
                (wy_min + wy_max) * 0.5,
                (wz_min + wz_max) * 0.5,
            )
        else:
            center_world = (0.0, 0.0, 0.0)
        object_center_screen = to_screen(self._project(*center_world))

        def choose_label_position(
            base: QPointF,
            perp_dx: float,
            perp_dy: float,
            distance: float,
            forward_dx: float = 0.0,
            forward_dy: float = 0.0,
        ) -> QPointF:
            margin = 12.0
            candidates = [
                QPointF(
                    base.x() + forward_dx + perp_dx * distance,
                    base.y() + forward_dy + perp_dy * distance,
                ),
                QPointF(
                    base.x() + forward_dx - perp_dx * distance,
                    base.y() + forward_dy - perp_dy * distance,
                ),
            ]

            def score(point: QPointF) -> tuple[int, float]:
                inside = (
                    margin <= point.x() <= self.width() - margin
                    and margin <= point.y() <= self.height() - margin
                )
                dist_to_object = math.hypot(
                    point.x() - object_center_screen.x(),
                    point.y() - object_center_screen.y(),
                )
                return (1 if inside else 0, dist_to_object)

            return max(candidates, key=score)

        for label, start, end, pen, color, point_on_axis, unit_point in (
            (
                "X",
                *axis_limits(wx_min, wx_max),
                _PEN_AX_X,
                _AX_X_COLOR,
                lambda value: (value, 0.0, 0.0),
                (1.0, 0.0, 0.0),
            ),
            (
                "Y",
                *axis_limits(wy_min, wy_max),
                _PEN_AX_Y,
                _AX_Y_COLOR,
                lambda value: (0.0, value, 0.0),
                (0.0, 1.0, 0.0),
            ),
            (
                "Z",
                *axis_limits(wz_min, wz_max),
                _PEN_AX_Z,
                _AX_Z_COLOR,
                lambda value: (0.0, 0.0, value),
                (0.0, 0.0, 1.0),
            ),
        ):
            start_point = self._project(*point_on_axis(start))
            end_point = self._project(*point_on_axis(end))
            p.setPen(pen)
            p.drawLine(start_point, end_point)

            unit_origin = self._project(0.0, 0.0, 0.0)
            unit_step = self._project(*unit_point)
            dir_x = (unit_step.x() - unit_origin.x()) * self._zoom
            dir_y = (unit_step.y() - unit_origin.y()) * self._zoom
            dir_len = math.hypot(dir_x, dir_y) or 1.0
            perp_x = -dir_y / dir_len
            perp_y = dir_x / dir_len
            major_tick_half = 4.0
            minor_tick_half = 2.5
            label_offset = 10.0

            major_step, minor_step = _axis_tick_steps(start, end, dir_len)
            tick_values = range(start, end + 1, minor_step or major_step)

            for value in tick_values:
                is_major = (value % major_step) == 0
                tick_half = major_tick_half if is_major else minor_tick_half
                tick_proj = self._project(*point_on_axis(float(value)))
                tick_screen = to_screen(tick_proj)
                tick_line = QLineF(
                    QPointF(
                        tick_screen.x() - perp_x * tick_half,
                        tick_screen.y() - perp_y * tick_half,
                    ),
                    QPointF(
                        tick_screen.x() + perp_x * tick_half,
                        tick_screen.y() + perp_y * tick_half,
                    ),
                )
                self._axis_overlay_lines.append((tick_line, color))

                if is_major and value != 0:
                    self._axis_labels.append((
                        str(value),
                        choose_label_position(
                            tick_screen,
                            perp_x,
                            perp_y,
                            major_tick_half + label_offset,
                        ),
                        color,
                    ))

            end_screen = to_screen(end_point)
            self._axis_labels.append((
                label,
                choose_label_position(
                    end_screen,
                    perp_x,
                    perp_y,
                    12.0,
                    dir_x / dir_len * 10.0,
                    dir_y / dir_len * 10.0,
                ),
                color,
            ))

    def _paint_axis_overlay(self, p: QPainter) -> None:
        """Paint axis tick marks and labels in viewport pixel coordinates."""
        if not self._axis_overlay_lines and not self._axis_labels:
            return

        for line, color in self._axis_overlay_lines:
            p.setPen(_cosmetic_pen(color, 1.0))
            p.drawLine(line)

        for label, world_pt, color in self._axis_labels:
            fm = p.fontMetrics()
            text_rect = fm.boundingRect(label)
            draw_rect = QRectF(
                world_pt.x() - text_rect.width() / 2.0,
                world_pt.y() - text_rect.height() / 2.0,
                text_rect.width() + 2.0,
                text_rect.height() + 2.0,
            )
            p.fillRect(draw_rect.adjusted(-1.0, -1.0, 1.0, 1.0), QColor(245, 245, 245, 220))
            p.setPen(_cosmetic_pen(color, 1.0))
            p.drawText(draw_rect, Qt.AlignmentFlag.AlignCenter, label)


class _ViewCubeWidget(QWidget):
    """Clickable mini view cube for switching to standard orthographic views."""

    face_selected = pyqtSignal(str)

    _FACE_COLORS = {
        "xp": QColor("#f2f2f2"),
        "xn": QColor("#dcdcdc"),
        "yp": QColor("#ededed"),
        "yn": QColor("#d7d7d7"),
        "zp": QColor("#ffffff"),
        "zn": QColor("#cfcfcf"),
    }
    _FACE_LABELS = {
        "xp": ("X", _AX_X_COLOR),
        "xn": ("X", _AX_X_COLOR),
        "yp": ("Y", _AX_Y_COLOR),
        "yn": ("Y", _AX_Y_COLOR),
        "zp": ("Z", _AX_Z_COLOR),
        "zn": ("Z", _AX_Z_COLOR),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(72, 72)
        self.setToolTip("Ansichtswuerfel: Flaeche klicken fuer Standardansicht")
        self._yaw_deg = 30.0
        self._pitch_deg = 35.26438968
        self._face_polygons: list[tuple[str, QPolygonF]] = []

    def set_orientation(self, yaw_deg: float, pitch_deg: float) -> None:
        """Update the cube to reflect the current viewport orientation."""
        self._yaw_deg = yaw_deg
        self._pitch_deg = pitch_deg
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        for face, polygon in reversed(self._face_polygons):
            if polygon.containsPoint(event.position(), Qt.FillRule.WindingFill):
                self.face_selected.emit(face)
                event.accept()
                return

        self.face_selected.emit("iso")
        event.accept()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#2F3645"))

        self._face_polygons = []
        center = QPointF(self.width() / 2.0, self.height() / 2.0 - 6.0)
        scale = 18.0

        vertices = {
            "lbf": (-1.0, -1.0, -1.0),
            "lbn": (-1.0, -1.0, 1.0),
            "ltf": (-1.0, 1.0, -1.0),
            "ltn": (-1.0, 1.0, 1.0),
            "rbf": (1.0, -1.0, -1.0),
            "rbn": (1.0, -1.0, 1.0),
            "rtf": (1.0, 1.0, -1.0),
            "rtn": (1.0, 1.0, 1.0),
        }
        projected: dict[str, QPointF] = {}
        for key, coords in vertices.items():
            x2, _depth, z2 = _camera_transform(*coords, self._yaw_deg, self._pitch_deg)
            projected[key] = QPointF(center.x() + x2 * scale, center.y() - z2 * scale)

        faces = [
            ("xp", ["rbf", "rtf", "rtn", "rbn"], (1.0, 0.0, 0.0)),
            ("xn", ["lbf", "lbn", "ltn", "ltf"], (-1.0, 0.0, 0.0)),
            ("yp", ["ltf", "ltn", "rtn", "rtf"], (0.0, 1.0, 0.0)),
            ("yn", ["lbf", "rbf", "rbn", "lbn"], (0.0, -1.0, 0.0)),
            ("zp", ["lbn", "rbn", "rtn", "ltn"], (0.0, 0.0, 1.0)),
            ("zn", ["lbf", "ltf", "rtf", "rbf"], (0.0, 0.0, -1.0)),
        ]

        visible_faces: list[tuple[float, str, QPolygonF]] = []
        for face, keys, normal in faces:
            nx, depth, nz = _camera_transform(*normal, self._yaw_deg, self._pitch_deg)
            if depth >= 0.0:
                continue
            polygon = QPolygonF([projected[key] for key in keys])
            depth_sum = 0.0
            for key in keys:
                _px, py, _pz = _camera_transform(*vertices[key], self._yaw_deg, self._pitch_deg)
                depth_sum += py
            visible_faces.append((depth_sum / len(keys), face, polygon))

        visible_faces.sort(key=lambda item: item[0])
        for _depth, face, polygon in visible_faces:
            painter.setPen(QPen(QColor("#495062"), 1.2))
            painter.setBrush(QBrush(self._FACE_COLORS[face]))
            painter.drawPolygon(polygon)
            label, color = self._FACE_LABELS[face]
            painter.setPen(color)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(polygon.boundingRect(), Qt.AlignmentFlag.AlignCenter, label)
            self._face_polygons.append((face, polygon))

        painter.setPen(QColor("#c8d0df"))
        painter.drawText(
            QRectF(0.0, self.height() - 18.0, self.width(), 14.0),
            Qt.AlignmentFlag.AlignCenter,
            "3D",
        )
        painter.end()


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
    warning_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = "de"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._warnings: list[AnalysisWarning] = []
        self._warnings_dialog: WarningsDialog | None = None

        # --- toolbar row with view cube ---
        toolbar = QWidget()
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(4, 2, 4, 2)
        tb.setSpacing(4)
        self._view_cube = _ViewCubeWidget()
        tb.addWidget(self._view_cube)
        tb.addStretch(1)
        layout.addWidget(toolbar)

        # --- drawing viewport ---
        self._viewport = _IsometricViewport()
        self._viewport.segment_selected.connect(self.segment_selected)
        self._viewport.view_orientation_changed.connect(self._view_cube.set_orientation)
        self._view_cube.face_selected.connect(self._viewport.set_standard_view)
        layout.addWidget(self._viewport, stretch=1)

        self.set_language(self._language)

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
        """Store analysis warnings and update floating dialog contents."""
        self._warnings = warnings
        if not self._warnings:
            if self._warnings_dialog is not None:
                self._warnings_dialog.set_warnings([])
                self._warnings_dialog.close()
            return
        if self._warnings_dialog is not None:
            self._warnings_dialog.set_warnings(self._warnings)

    def set_language(self, language: str) -> None:
        """Set UI language for panel labels."""
        self._language = language
        if self._warnings_dialog is not None:
            self._warnings_dialog.set_language(self._language)

    def show_warning_dialog(self) -> None:
        """Show floating warnings dialog and keep it in sync."""
        if not self._warnings:
            return
        if self._warnings_dialog is None:
            self._warnings_dialog = WarningsDialog(parent=self, language=self._language)
            self._warnings_dialog.line_selected.connect(self.warning_selected)
        self._warnings_dialog.set_language(self._language)
        self._warnings_dialog.set_warnings(self._warnings)
        self._warnings_dialog.show()
        self._warnings_dialog.raise_()
        self._warnings_dialog.activateWindow()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

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
        if self._language == "de":
            self._dims_label.setText(
                f"Werkstueck  -  X: {w:.2f} mm   Y: {h:.2f} mm   Z: {d:.2f} mm"
            )
        else:
            self._dims_label.setText(
                f"Workpiece  -  X: {w:.2f} mm   Y: {h:.2f} mm   Z: {d:.2f} mm"
            )
        self._dims_label.show()
