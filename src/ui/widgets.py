"""Reusable custom UI widgets."""

from PyQt6.QtWidgets import QComboBox, QLabel, QPlainTextEdit, QWidget
from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QResizeEvent

from ..gcode.grbl_versions import GRBL_VERSIONS


class GRBLVersionSelector(QComboBox):
    """Combo box pre-populated with the supported GRBL versions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.addItems(GRBL_VERSIONS)


class LineNumberBar(QWidget):
    """QPainter-based widget that renders line numbers beside a QPlainTextEdit.

    The bar is sized and positioned by the owning ``GCodeEditor`` via
    ``setViewportMargins`` / ``setGeometry``; it only needs to implement
    ``paintEvent`` and ``sizeHint``.
    """

    _BG_COLOR = QColor("#F0F0F0")
    _FG_COLOR = QColor("#888888")
    _H_PADDING = 6  # pixels right-padding between number and text area

    def __init__(self, editor: "GCodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint 1-based line numbers aligned to each visible text block."""
        painter = QPainter(self)
        painter.fillRect(event.rect(), self._BG_COLOR)
        painter.setPen(self._FG_COLOR)

        font = self._editor.font()
        painter.setFont(font)
        fm = self._editor.fontMetrics()
        line_height = fm.height()

        block = self._editor.firstVisibleBlock()
        block_number = block.blockNumber()
        geo = self._editor.blockBoundingGeometry(block)
        top = round(geo.translated(self._editor.contentOffset()).top())
        bottom = top + round(self._editor.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self.width() - self._H_PADDING,
                    line_height,
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self._editor.blockBoundingRect(block).height())
            block_number += 1


class GCodeEditor(QPlainTextEdit):
    """QPlainTextEdit with an integrated QPainter-based line number bar.

    The line number area is rendered as a permanent left margin by ``LineNumberBar``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_number_bar = LineNumberBar(self)

        self.blockCountChanged.connect(self._update_line_number_width)
        self.updateRequest.connect(self._on_update_request)
        self._update_line_number_width()

    # ------------------------------------------------------------------
    # Width calculation
    # ------------------------------------------------------------------

    def line_number_area_width(self) -> int:
        """Return the pixel width required to render the widest line number."""
        digits = len(str(max(1, self.blockCount())))
        char_w = self.fontMetrics().horizontalAdvance('9')
        return LineNumberBar._H_PADDING + char_w * digits + LineNumberBar._H_PADDING

    def _update_line_number_width(self, _block_count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_bar.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def _on_update_request(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_bar.scroll(0, dy)
        else:
            self._line_number_bar.update(
                0, rect.y(), self._line_number_bar.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self._update_line_number_width()


class StatusIndicator(QLabel):
    """A colored status label for showing connection/parse state."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_ok(self, message: str = "OK") -> None:
        """Display a green OK status with a text and icon indicator."""
        self.setText(f"● {message}")
        self.setStyleSheet("color: green; font-weight: bold;")

    def set_warning(self, message: str = "Warning") -> None:
        """Display an amber warning status with a text and icon indicator."""
        self.setText(f"▲ {message}")
        self.setStyleSheet("color: orange; font-weight: bold;")

    def set_error(self, message: str = "Error") -> None:
        """Display a red error status with a text and icon indicator."""
        self.setText(f"✕ {message}")
        self.setStyleSheet("color: red; font-weight: bold;")
