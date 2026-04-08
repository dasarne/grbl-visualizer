"""G-Code editor panel."""

from PyQt6.QtWidgets import QVBoxLayout, QPlainTextEdit, QWidget
from PyQt6.QtCore import pyqtSignal


class EditorPanel(QWidget):
    """Side-panel showing the raw G-Code text with line highlighting."""

    line_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the editor layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text_edit)

    def load_content(self, content: str) -> None:
        """Load G-Code text into the editor."""
        self._text_edit.setPlainText(content)

    def highlight_line(self, line_number: int) -> None:
        """Scroll to and highlight the given 1-based line number.

        TODO: Implement QTextCursor-based line highlighting.
        """
        pass
