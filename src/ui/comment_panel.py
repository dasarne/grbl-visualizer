"""Comment strip panel — shows G-code comments as a navigable outline."""

from PyQt6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import pyqtSignal, Qt


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
        self._line_numbers: list[int] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the comment panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Comments")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet(
            "background: #2b2b2b; color: #cccccc; font-weight: bold;"
            " padding: 4px; font-size: 11px;"
        )
        layout.addWidget(header)

        self._list = QListWidget()
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
        self._list.clear()
        self._line_numbers = []

        for line_number, text in comments:
            item = QListWidgetItem(f"L{line_number}  {text}")
            item.setData(Qt.ItemDataRole.UserRole, line_number)
            item.setToolTip(f"Line {line_number}: {text}")
            self._list.addItem(item)
            self._line_numbers.append(line_number)

    def set_current_line(self, line_number: int) -> None:
        """Highlight the last comment at or before *line_number*.

        This gives a "you are between these two comments" indication: the
        highlighted entry is the most recent comment that the cursor has
        passed, and the next entry (if any) is the upcoming comment.
        """
        if not self._line_numbers:
            return

        active_idx: int | None = None
        for idx, ln in enumerate(self._line_numbers):
            if ln <= line_number:
                active_idx = idx

        if active_idx is None:
            self._list.clearSelection()
            return

        self._list.setCurrentRow(active_idx)
        self._list.scrollToItem(
            self._list.item(active_idx),
            QListWidget.ScrollHint.EnsureVisible,
        )

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """Emit the line number of the clicked comment."""
        line_number = item.data(Qt.ItemDataRole.UserRole)
        self.comment_selected.emit(line_number)
