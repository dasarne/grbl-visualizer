"""G-Code editor panel."""

from PyQt6.QtWidgets import QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity
from .widgets import GCodeEditor

_SEVERITY_COLORS: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "#FFCCCC",
    WarningSeverity.WARNING: "#FFF3CC",
    WarningSeverity.INFO: "#CCE5FF",
}


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

        self._text_edit = GCodeEditor()
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(GCodeEditor.LineWrapMode.NoWrap)
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_moved)
        layout.addWidget(self._text_edit)

    def load_content(self, content: str) -> None:
        """Load G-Code text into the editor."""
        self._text_edit.setPlainText(content)

    def highlight_line(self, line_number: int) -> None:
        """Scroll to and highlight the given 1-based line number."""
        doc = self._text_edit.document()
        block = doc.findBlockByLineNumber(line_number - 1)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        self._text_edit.setTextCursor(cursor)
        self._text_edit.centerCursor()

    def mark_warning_lines(self, warnings: list[AnalysisWarning]) -> None:
        """Apply background colour highlights to lines that carry warnings.

        ERROR lines get a red tint; WARNING lines get an amber tint.
        Call after load_content() to apply warning decorations.
        """
        # Build a mapping from 1-based line number to the most-severe warning.
        line_severity: dict[int, WarningSeverity] = {}
        for w in warnings:
            if w.line_number is None:
                continue
            existing = line_severity.get(w.line_number)
            if existing is None or w.severity.value > existing.value:
                line_severity[w.line_number] = w.severity

        if not line_severity:
            return

        doc = self._text_edit.document()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()

        for line_number, severity in line_severity.items():
            block = doc.findBlockByLineNumber(line_number - 1)
            if not block.isValid():
                continue

            fmt = QTextCharFormat()
            fmt.setBackground(QColor(_SEVERITY_COLORS[severity]))

            block_cursor = QTextCursor(block)
            block_cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            block_cursor.mergeCharFormat(fmt)

        cursor.endEditBlock()

    def _on_cursor_moved(self) -> None:
        """Emit the current 1-based line number whenever the cursor moves."""
        line_number = self._text_edit.textCursor().blockNumber() + 1
        self.line_selected.emit(line_number)
