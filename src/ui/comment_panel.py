"""Comment strip panel — shows G-code comments as a navigable outline."""

from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QPaintEvent, QPainter, QPen


class _CommentListWidget(QListWidget):
    """Comment list with an optional marker line drawn between two items."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gap_after_row: int | None = None

    def set_gap_after_row(self, row: int | None) -> None:
        """Set the row after which a marker line should be drawn."""
        if self._gap_after_row == row:
            return
        self._gap_after_row = row
        self.viewport().update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self._gap_after_row is None:
            return

        item = self.item(self._gap_after_row)
        if item is None:
            return

        rect = self.visualItemRect(item)
        if not rect.isValid():
            return

        y = rect.bottom() + 1
        painter = QPainter(self.viewport())
        pen = QPen(QColor("#FF3333"), 2.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLine(6, y, self.viewport().width() - 6, y)
        painter.end()


class CommentPanel(QWidget):
    """Narrow panel displaying all inline comments from the loaded G-Code.

    Comments are listed in program order with their line numbers.  As the
    editor cursor moves, the *last* comment at or before the cursor line is
    highlighted — giving the user a running "where am I in the narrative"
    indicator without having to scroll through the full G-code source.

    Clicking any comment entry scrolls the editor back to that line.
    """

    comment_selected = pyqtSignal(int)  # emits the 1-based line number

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._comments: list[tuple[int, str]] = []
        self._line_numbers: list[int] = []
        self._current_line: int | None = None
        self._language = "de"
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the comment panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("Comments")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header.setStyleSheet(
            "background: #2b2b2b; color: #cccccc; font-weight: bold;"
            " padding: 4px; font-size: 11px;"
        )
        layout.addWidget(self._header)

        self._list = _CommentListWidget()
        self._list.setStyleSheet(
            "QListWidget { font-size: 11px; background: #1e1e1e; color: #d4d4d4; }"
            "QListWidget::item { padding: 3px 6px; border-bottom: 1px solid #333; }"
            "QListWidget::item:selected { background: #3a6ea8; color: white; }"
        )
        self._list.setWordWrap(True)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

    def load_comments(self, comments: list[tuple[int, str]]) -> None:
        """Populate the panel with (line_number, comment_text) pairs.

        Call this after parsing a G-Code program.  Pass an empty list to
        clear the panel.
        """
        self._comments = list(comments)
        self._refresh_items()

    def set_current_line(self, line_number: int) -> None:
        """Highlight the current line, inserting a temporary gap marker if needed."""
        self._current_line = line_number
        self._refresh_items()

    def set_language(self, language: str) -> None:
        """Set panel language for static texts."""
        self._language = language
        self._header.setText("Kommentare" if language == "de" else "Comments")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Emit the line number of the clicked comment."""
        line_number = item.data(Qt.ItemDataRole.UserRole)
        self.comment_selected.emit(line_number)

    def _refresh_items(self) -> None:
        """Rebuild the list and mark gaps between adjacent comments when needed."""
        self._list.clear()
        self._list.set_gap_after_row(None)
        self._line_numbers = []

        current_line = self._current_line
        current_row: int | None = None

        for line_number, text in self._comments:
            row = self._add_comment_item(line_number, text)
            if current_line is not None and line_number == current_line:
                current_row = row

        if current_row is None:
            self._list.clearSelection()
            gap_after_row = self._find_gap_after_row(current_line)
            self._list.set_gap_after_row(gap_after_row)
            if gap_after_row is not None:
                anchor_item = self._list.item(gap_after_row)
                if anchor_item is not None:
                    self._list.scrollToItem(
                        anchor_item,
                        QListWidget.ScrollHint.PositionAtCenter,
                    )
            return

        self._list.setCurrentRow(current_row)
        self._list.scrollToItem(
            self._list.item(current_row),
            QListWidget.ScrollHint.EnsureVisible,
        )
        self._list.set_gap_after_row(None)

    def _add_comment_item(self, line_number: int, text: str) -> int:
        item = QListWidgetItem(f"L{line_number}  {text}")
        item.setData(Qt.ItemDataRole.UserRole, line_number)
        item.setToolTip(f"Line {line_number}: {text}")
        self._list.addItem(item)
        self._line_numbers.append(line_number)
        return self._list.count() - 1

    def _find_gap_after_row(self, line_number: int | None) -> int | None:
        """Return the row after which the current line falls between comments."""
        if line_number is None or len(self._line_numbers) < 2:
            return None

        for idx in range(len(self._line_numbers) - 1):
            left = self._line_numbers[idx]
            right = self._line_numbers[idx + 1]
            if left < line_number < right:
                return idx
        return None
