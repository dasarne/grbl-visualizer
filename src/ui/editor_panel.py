"""G-Code editor panel."""

import re
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QTextEdit
from PyQt6.QtCore import pyqtSignal, QEvent, Qt
from PyQt6.QtGui import (
    QTextCharFormat,
    QColor,
    QTextCursor,
    QTextFormat,
    QSyntaxHighlighter,
    QFont,
    QTextDocument,
    QKeyEvent,
    QMouseEvent,
    QPalette,
    QGuiApplication,
)
from PyQt6.QtCore import QRegularExpression

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity
from .widgets import GCodeEditor

_SEVERITY_COLORS: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "#FFCCCC",
    WarningSeverity.WARNING: "#FFF3CC",
    WarningSeverity.INFO: "#CCE5FF",
}

_CURRENT_LINE_COLOR = "#D9E8FF"
_MULTI_LINE_SELECTION_COLOR = "#FFE3B8"
_SEARCH_SCOPE_COLOR = "#FFF4BF"
_SEARCH_MATCH_COLOR = "#CCF5CC"


class _GCodeSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for G-code commands and axis words."""

    def __init__(self, document) -> None:
        super().__init__(document)

        self._cmd_re = QRegularExpression(
            r"^\s*(?:N\d+\s+)?([GMT]\d+(?:\.\d+)?)",
            QRegularExpression.PatternOption.CaseInsensitiveOption,
        )
        self._x_re = QRegularExpression(
            r"\bX[-+]?\d*\.?\d+\b",
            QRegularExpression.PatternOption.CaseInsensitiveOption,
        )
        self._y_re = QRegularExpression(
            r"\bY[-+]?\d*\.?\d+\b",
            QRegularExpression.PatternOption.CaseInsensitiveOption,
        )
        self._z_re = QRegularExpression(
            r"\bZ[-+]?\d*\.?\d+\b",
            QRegularExpression.PatternOption.CaseInsensitiveOption,
        )

        self._cmd_fmt = QTextCharFormat()
        self._cmd_fmt.setForeground(QColor("#0B3D91"))
        self._cmd_fmt.setFontWeight(QFont.Weight.Bold)

        self._x_fmt = QTextCharFormat()
        self._x_fmt.setForeground(QColor("#CC3333"))

        self._y_fmt = QTextCharFormat()
        self._y_fmt.setForeground(QColor("#33AA33"))

        self._z_fmt = QTextCharFormat()
        self._z_fmt.setForeground(QColor("#3366CC"))

    def highlightBlock(self, text: str) -> None:
        cmd_match = self._cmd_re.match(text)
        if cmd_match.hasMatch():
            start = cmd_match.capturedStart(1)
            length = cmd_match.capturedLength(1)
            self.setFormat(start, length, self._cmd_fmt)

        self._apply_regex(text, self._x_re, self._x_fmt)
        self._apply_regex(text, self._y_re, self._y_fmt)
        self._apply_regex(text, self._z_re, self._z_fmt)

    def _apply_regex(
        self,
        text: str,
        regex: QRegularExpression,
        fmt: QTextCharFormat,
    ) -> None:
        it = regex.globalMatch(text)
        while it.hasNext():
            match = it.next()
            self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class EditorPanel(QWidget):
    """Side-panel showing the raw G-Code text with line highlighting."""

    line_selected = pyqtSignal(int)
    lines_selected = pyqtSignal(list)   # list[int] – all 1-based line numbers in selection
    content_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_line: int | None = None
        self._warning_severity: dict[int, WarningSeverity] = {}
        self._search_scope: tuple[int, int] | None = None
        self._search_matches: list[tuple[int, int]] = []
        self._multi_selected_lines: set[int] = set()
        self._suppress_cursor_events = False
        self._suppress_text_change = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the editor layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._text_edit = GCodeEditor()
        self._text_edit.setReadOnly(False)
        self._text_edit.setLineWrapMode(GCodeEditor.LineWrapMode.NoWrap)
        doc = self._text_edit.document()
        doc.setUndoRedoEnabled(True)
        self._syntax = _GCodeSyntaxHighlighter(doc)
        # Selection highlight colour – same warm yellow as the canvas multi-selection.
        palette = self._text_edit.palette()
        hl_color = QColor(_MULTI_LINE_SELECTION_COLOR)
        palette.setColor(QPalette.ColorGroup.Active,   QPalette.ColorRole.Highlight, hl_color)
        palette.setColor(QPalette.ColorGroup.Active,   QPalette.ColorRole.HighlightedText, QColor("#000000"))
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, hl_color)
        palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText, QColor("#000000"))
        self._text_edit.setPalette(palette)

        self._text_edit.installEventFilter(self)
        self._text_edit.viewport().installEventFilter(self)
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_moved)
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)

    def eventFilter(self, obj, event) -> bool:
        """Handle keyboard and mouse events for multi-line canvas selection."""
        # Ctrl+Click on the text area toggles the clicked line in the multi-selection.
        if (
            obj is self._text_edit.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            cursor = self._text_edit.cursorForPosition(event.position().toPoint())
            line_number = cursor.blockNumber() + 1
            if line_number in self._multi_selected_lines:
                self._multi_selected_lines.discard(line_number)
            else:
                self._multi_selected_lines.add(line_number)
            self._suppress_cursor_events = True
            self._text_edit.setTextCursor(cursor)
            self._suppress_cursor_events = False
            self._apply_extra_selections(cursor)
            self.lines_selected.emit(sorted(self._multi_selected_lines))
            return True  # block default – prevents normal click from clearing selection

        if (
            obj is self._text_edit
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and self._multi_selected_lines
            and not self._text_edit.textCursor().hasSelection()
        ):
            key = event.key()
            mods = event.modifiers()

            if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self._delete_multi_selected_lines()
                return True

            if bool(mods & Qt.KeyboardModifier.ControlModifier):
                if key == Qt.Key.Key_C:
                    self._copy_multi_selected_lines()
                    return True
                if key == Qt.Key.Key_X:
                    self._copy_multi_selected_lines()
                    self._delete_multi_selected_lines()
                    return True

            # Printable character → replace selected lines with that character.
            text = event.text()
            if text and text.isprintable() and not bool(mods & Qt.KeyboardModifier.ControlModifier):
                self._delete_multi_selected_lines()
                # Fall through so QTextEdit inserts the character normally.
                return False

        return super().eventFilter(obj, event)

    def load_content(self, content: str) -> None:
        """Load G-Code text into the editor."""
        self._suppress_text_change = True
        self._text_edit.setPlainText(content)
        self._text_edit.document().setModified(False)
        self._warning_severity.clear()
        self._search_scope = None
        self._search_matches = []
        self._multi_selected_lines.clear()
        self._apply_extra_selections()
        self._suppress_text_change = False

    def get_content(self) -> str:
        """Return the full editor content."""
        return self._text_edit.toPlainText()

    def is_modified(self) -> bool:
        """Return whether the editor document has unsaved changes."""
        return self._text_edit.document().isModified()

    def set_modified(self, modified: bool) -> None:
        """Set document modified flag."""
        self._text_edit.document().setModified(modified)

    def highlight_line(self, line_number: int) -> None:
        """Scroll to and select the given 1-based line in the editor."""
        doc = self._text_edit.document()
        block = doc.findBlockByLineNumber(line_number - 1)
        if not block.isValid():
            return
        self._multi_selected_lines.clear()
        self._selected_line = line_number
        cursor = QTextCursor(block)
        # Select the full line so a canvas/comment click produces a real text selection.
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        self._text_edit.setTextCursor(cursor)
        self._text_edit.centerCursor()
        self._apply_extra_selections(cursor)

    def highlight_lines(self, line_numbers: list[int]) -> None:
        """Highlight a non-contiguous set of 1-based line numbers."""
        if not line_numbers:
            self._multi_selected_lines.clear()
            self._apply_extra_selections()
            return
        if len(line_numbers) == 1:
            self.highlight_line(line_numbers[0])
            return
        doc = self._text_edit.document()
        valid_lines = sorted({ln for ln in line_numbers if ln > 0})
        if not valid_lines:
            return
        first = valid_lines[0]
        first_block = doc.findBlockByLineNumber(first - 1)
        if not first_block.isValid():
            return
        self._selected_line = first
        self._multi_selected_lines = set(valid_lines)
        cursor = QTextCursor(first_block)
        cursor.clearSelection()
        self._suppress_cursor_events = True
        self._text_edit.setTextCursor(cursor)
        self._suppress_cursor_events = False
        self._text_edit.centerCursor()
        self._apply_extra_selections(cursor)
        # Keep canvas/editor in sync without collapsing to a contiguous range.
        self.lines_selected.emit(valid_lines)

    def _delete_multi_selected_lines(self) -> None:
        """Delete all currently multi-selected lines as full logical blocks."""
        doc = self._text_edit.document()
        lines = sorted(self._multi_selected_lines, reverse=True)
        if not lines:
            return

        self._suppress_cursor_events = True
        edit_cursor = self._text_edit.textCursor()
        edit_cursor.beginEditBlock()
        for line_number in lines:
            block = doc.findBlockByLineNumber(line_number - 1)
            if not block.isValid():
                continue
            start = block.position()
            end = start + block.length()
            del_cursor = QTextCursor(doc)
            del_cursor.setPosition(start)
            del_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            del_cursor.removeSelectedText()
        edit_cursor.endEditBlock()
        self._suppress_cursor_events = False

        self._multi_selected_lines.clear()
        self._search_scope = None
        self._search_matches = []
        self._apply_extra_selections()
        self.lines_selected.emit([])

    def mark_warning_lines(self, warnings: list[AnalysisWarning]) -> None:
        """Apply warning highlights as non-destructive extra selections."""
        line_severity: dict[int, WarningSeverity] = {}
        for w in warnings:
            if w.line_number is None:
                continue
            existing = line_severity.get(w.line_number)
            if existing is None or w.severity.value > existing.value:
                line_severity[w.line_number] = w.severity
        self._warning_severity = line_severity
        self._apply_extra_selections()

    def copy(self) -> None:
        if self._multi_selected_lines and not self._text_edit.textCursor().hasSelection():
            self._copy_multi_selected_lines()
        else:
            self._text_edit.copy()

    def _copy_multi_selected_lines(self) -> None:
        doc = self._text_edit.document()
        lines_text: list[str] = []
        for line_number in sorted(self._multi_selected_lines):
            block = doc.findBlockByLineNumber(line_number - 1)
            if block.isValid():
                lines_text.append(block.text())
        QGuiApplication.clipboard().setText("\n".join(lines_text))

    def paste(self) -> None:
        self._text_edit.paste()

    def undo(self) -> None:
        """Undo last edit."""
        self._text_edit.undo()

    def redo(self) -> None:
        """Redo last undone edit."""
        self._text_edit.redo()

    def can_undo(self) -> bool:
        """Return whether undo is available."""
        return self._text_edit.document().isUndoAvailable()

    def can_redo(self) -> bool:
        """Return whether redo is available."""
        return self._text_edit.document().isRedoAvailable()

    def get_selected_text(self) -> str:
        """Return currently selected text."""
        cursor = self._text_edit.textCursor()
        return cursor.selectedText()

    def get_selected_lines(self) -> list[int]:
        """Return currently active selected lines (1-based)."""
        if self._multi_selected_lines:
            return sorted(self._multi_selected_lines)

        cursor = self._text_edit.textCursor()
        if cursor.hasSelection():
            doc = self._text_edit.document()
            sel_start = cursor.selectionStart()
            sel_end = cursor.selectionEnd()
            start_block = doc.findBlock(sel_start).blockNumber()
            end_block = doc.findBlock(max(sel_start, sel_end - 1)).blockNumber()
            return list(range(start_block + 1, end_block + 2))

        return [cursor.blockNumber() + 1]

    def clear_search_highlights(self) -> None:
        """Clear search-scope and match overlays."""
        self._search_scope = None
        self._search_matches = []
        self._apply_extra_selections()

    def find_next(self, term: str, use_regex: bool = False, search_in_selection: bool = False) -> bool:
        """Find next occurrence with optional regex support and wrap-around."""
        if not term:
            self._search_matches = []
            self._apply_extra_selections()
            return False
        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        self._update_search_matches(term, use_regex, cursor, search_in_selection)
        if not self._search_matches:
            return False

        anchor = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()
        for start, end in self._search_matches:
            if start >= anchor:
                self._select_range(start, end)
                return True
        self._select_range(*self._search_matches[0])
        return True

    def find_previous(self, term: str, use_regex: bool = False, search_in_selection: bool = False) -> bool:
        """Find previous occurrence with optional regex support and wrap-around."""
        if not term:
            self._search_matches = []
            self._apply_extra_selections()
            return False
        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        self._update_search_matches(term, use_regex, cursor, search_in_selection)
        if not self._search_matches:
            return False

        anchor = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        for start, end in reversed(self._search_matches):
            if end <= anchor:
                self._select_range(start, end)
                return True
        self._select_range(*self._search_matches[-1])
        return True

    def preview_search(
        self,
        term: str,
        use_regex: bool = False,
        search_in_selection: bool = False,
    ) -> tuple[bool, int]:
        """Incremental search preview: keep match selected and return hit count."""
        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        if not term:
            self._search_matches = []
            self._apply_extra_selections()
            return (False, 0)

        content = self.get_content()
        ranges = self._get_search_ranges(content, cursor, search_in_selection)
        if ranges is None:
            self._search_matches = []
            self._apply_extra_selections()
            return (False, 0)

        self._search_matches = self._compute_match_ranges(term, use_regex, content, ranges)
        self._apply_extra_selections()
        count = len(self._search_matches)
        # Do not move the text cursor during incremental preview typing.
        # This keeps the user's current selection/scope intact.
        return (count > 0, count)

    def replace_next(
        self,
        needle: str,
        replacement: str,
        use_regex: bool = False,
        search_in_selection: bool = False,
    ) -> bool:
        """Replace next occurrence and move to next. Returns True if replacement made."""
        if not needle:
            return False
        cursor = self._text_edit.textCursor()
        if use_regex:
            return self._replace_regex_next(needle, replacement, cursor, search_in_selection)
        if not self.find_next(needle, use_regex=False, search_in_selection=search_in_selection):
            return False
        cursor = self._text_edit.textCursor()
        cursor.removeSelectedText()
        cursor.insertText(replacement)
        self._text_edit.setTextCursor(cursor)
        return True

    def replace_previous(
        self,
        needle: str,
        replacement: str,
        use_regex: bool = False,
        search_in_selection: bool = False,
    ) -> bool:
        """Replace previous occurrence and move to previous. Returns True if replacement made."""
        if not needle:
            return False
        cursor = self._text_edit.textCursor()
        if use_regex:
            return self._replace_regex_previous(needle, replacement, cursor, search_in_selection)
        if not self.find_previous(needle, use_regex=False, search_in_selection=search_in_selection):
            return False
        cursor = self._text_edit.textCursor()
        cursor.removeSelectedText()
        cursor.insertText(replacement)
        self._text_edit.setTextCursor(cursor)
        return True

    def replace_all(
        self,
        needle: str,
        replacement: str,
        use_regex: bool = False,
        search_in_selection: bool = False,
    ) -> int:
        """Replace all occurrences and return replacement count."""
        if not needle:
            return 0
        content = self.get_content()

        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        ranges = self._get_search_ranges(content, cursor, search_in_selection)
        if ranges is None:
            return 0

        try:
            new_content = content
            count = 0
            for start_bound, end_bound in reversed(ranges):
                target = new_content[start_bound:end_bound]
                if use_regex:
                    new_target, local_count = re.subn(
                        needle,
                        replacement,
                        target,
                        flags=re.MULTILINE,
                    )
                else:
                    local_count = target.count(needle)
                    new_target = target.replace(needle, replacement)
                if local_count == 0:
                    continue
                count += local_count
                new_content = (
                    new_content[:start_bound]
                    + new_target
                    + new_content[end_bound:]
                )
        except re.error:
            return 0
        if count == 0:
            return 0

        # Keep the user's context stable (cursor + visible source viewport).
        prev_cursor = self._text_edit.textCursor()
        prev_anchor = prev_cursor.anchor()
        prev_pos = prev_cursor.position()
        prev_vscroll = self._text_edit.verticalScrollBar().value()
        prev_hscroll = self._text_edit.horizontalScrollBar().value()

        self._suppress_text_change = True
        edit_cursor = QTextCursor(self._text_edit.document())
        edit_cursor.beginEditBlock()
        edit_cursor.select(QTextCursor.SelectionType.Document)
        edit_cursor.insertText(new_content)
        edit_cursor.endEditBlock()

        max_pos = len(new_content)
        restore_anchor = max(0, min(prev_anchor, max_pos))
        restore_pos = max(0, min(prev_pos, max_pos))
        restore_cursor = self._text_edit.textCursor()
        restore_cursor.setPosition(restore_anchor)
        restore_cursor.setPosition(restore_pos, QTextCursor.MoveMode.KeepAnchor)
        self._suppress_cursor_events = True
        self._text_edit.setTextCursor(restore_cursor)
        self._suppress_cursor_events = False
        self._text_edit.verticalScrollBar().setValue(prev_vscroll)
        self._text_edit.horizontalScrollBar().setValue(prev_hscroll)

        self._apply_extra_selections(restore_cursor)
        self._suppress_text_change = False
        return count

    def _find_literal(
        self,
        term: str,
        forward: bool,
        cursor: QTextCursor,
        search_in_selection: bool,
    ) -> bool:
        content = self.get_content()
        bounds = self._get_search_bounds(content, cursor, search_in_selection)
        if bounds is None:
            return False
        start_bound, end_bound = bounds

        if forward:
            search_from = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()
            search_from = max(start_bound, min(search_from, end_bound))
            found = content.find(term, search_from, end_bound)
            if found == -1:
                found = content.find(term, start_bound, search_from)
        else:
            search_to = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
            search_to = max(start_bound, min(search_to, end_bound))
            found = content.rfind(term, start_bound, search_to)
            if found == -1:
                found = content.rfind(term, search_to, end_bound)

        if found == -1:
            return False

        self._select_range(found, found + len(term))
        return True

    def _find_regex(
        self,
        pattern: str,
        forward: bool = True,
        cursor: QTextCursor | None = None,
        search_in_selection: bool = False,
    ) -> bool:
        """Find regex pattern from current cursor position."""
        if cursor is None:
            cursor = self._text_edit.textCursor()
        content = self.get_content()
        try:
            regex = re.compile(pattern, re.MULTILINE)
        except re.error:
            return False

        bounds = self._get_search_bounds(content, cursor, search_in_selection)
        if bounds is None:
            return False
        start_bound, end_bound = bounds

        if forward:
            start_pos = cursor.position()
            if cursor.hasSelection():
                start_pos = cursor.selectionEnd()
            start_pos = max(start_bound, min(start_pos, end_bound))

            matches = list(regex.finditer(content[start_pos:end_bound]))
            if matches:
                match = matches[0]
                self._select_range(start_pos + match.start(), start_pos + match.end())
                return True

            matches = list(regex.finditer(content[start_bound:start_pos]))
            if matches:
                match = matches[0]
                self._select_range(start_bound + match.start(), start_bound + match.end())
                return True
            return False

        end_pos = cursor.position()
        if cursor.hasSelection():
            end_pos = cursor.selectionStart()
        end_pos = max(start_bound, min(end_pos, end_bound))

        if end_pos > start_bound:
            matches = list(regex.finditer(content[start_bound:end_pos]))
            if cursor.hasSelection():
                end_pos = cursor.selectionStart()
            if matches:
                match = matches[-1]
                self._select_range(start_bound + match.start(), start_bound + match.end())
                return True

        matches = list(regex.finditer(content[end_pos:end_bound]))
        if matches:
            match = matches[-1]
            self._select_range(end_pos + match.start(), end_pos + match.end())
            return True
        return False

    def _replace_regex_next(
        self,
        pattern: str,
        replacement: str,
        cursor: QTextCursor,
        search_in_selection: bool,
    ) -> bool:
        """Replace next regex match and move cursor."""
        try:
            regex = re.compile(pattern, re.MULTILINE)
        except re.error:
            return False
        if not self.find_next(pattern, use_regex=True, search_in_selection=search_in_selection):
            return False
        cursor = self._text_edit.textCursor()
        match_text = cursor.selectedText()
        new_text = regex.sub(replacement, match_text, count=1)
        cursor.removeSelectedText()
        cursor.insertText(new_text)
        self._text_edit.setTextCursor(cursor)
        return True

    def _replace_regex_previous(
        self,
        pattern: str,
        replacement: str,
        cursor: QTextCursor,
        search_in_selection: bool,
    ) -> bool:
        """Replace previous regex match and move cursor."""
        try:
            regex = re.compile(pattern, re.MULTILINE)
        except re.error:
            return False
        if not self.find_previous(pattern, use_regex=True, search_in_selection=search_in_selection):
            return False
        cursor = self._text_edit.textCursor()
        match_text = cursor.selectedText()
        new_text = regex.sub(replacement, match_text, count=1)
        cursor.removeSelectedText()
        cursor.insertText(new_text)
        self._text_edit.setTextCursor(cursor)
        return True

    def _get_search_bounds(
        self,
        content: str,
        cursor: QTextCursor,
        search_in_selection: bool,
    ) -> tuple[int, int] | None:
        if not search_in_selection:
            return (0, len(content))
        if self._search_scope is not None:
            return self._search_scope
        if not cursor.hasSelection():
            return None
        return (cursor.selectionStart(), cursor.selectionEnd())

    def _get_search_ranges(
        self,
        content: str,
        cursor: QTextCursor,
        search_in_selection: bool,
    ) -> list[tuple[int, int]] | None:
        """Return search ranges; supports non-contiguous multi-line selections."""
        if not search_in_selection:
            return [(0, len(content))]

        if self._multi_selected_lines:
            doc = self._text_edit.document()
            ranges: list[tuple[int, int]] = []
            for line_number in sorted(self._multi_selected_lines):
                block = doc.findBlockByLineNumber(line_number - 1)
                if not block.isValid():
                    continue
                start = block.position()
                end = start + block.length()
                ranges.append((start, end))
            return ranges if ranges else None

        bounds = self._get_search_bounds(content, cursor, search_in_selection)
        if bounds is None:
            return None
        return [bounds]

    def _update_search_scope(self, cursor: QTextCursor, search_in_selection: bool) -> None:
        if not search_in_selection:
            if self._search_scope is not None:
                self._search_scope = None
                self._apply_extra_selections(cursor)
            return

        if self._multi_selected_lines:
            if self._search_scope is not None:
                self._search_scope = None
                self._apply_extra_selections(cursor)
            return

        if cursor.hasSelection():
            new_scope = (cursor.selectionStart(), cursor.selectionEnd())
            if self._search_scope != new_scope:
                self._search_scope = new_scope
                self._apply_extra_selections(cursor)
            return

        # Selection mode is active but there is no current selection anymore.
        if self._search_scope is not None:
            self._search_scope = None
            self._search_matches = []
            self._apply_extra_selections(cursor)

    def _count_matches(
        self,
        term: str,
        use_regex: bool,
        content: str,
        bounds: tuple[int, int],
    ) -> int:
        return len(self._compute_match_ranges(term, use_regex, content, [bounds]))

    def _update_search_matches(
        self,
        term: str,
        use_regex: bool,
        cursor: QTextCursor,
        search_in_selection: bool,
    ) -> None:
        content = self.get_content()
        ranges = self._get_search_ranges(content, cursor, search_in_selection)
        if not term or ranges is None:
            self._search_matches = []
            self._apply_extra_selections(cursor)
            return
        self._search_matches = self._compute_match_ranges(term, use_regex, content, ranges)
        self._apply_extra_selections(cursor)

    def _compute_match_ranges(
        self,
        term: str,
        use_regex: bool,
        content: str,
        ranges: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        results: list[tuple[int, int]] = []
        for start_bound, end_bound in ranges:
            target = content[start_bound:end_bound]

            if use_regex:
                try:
                    for match in re.finditer(term, target, flags=re.MULTILINE):
                        results.append((start_bound + match.start(), start_bound + match.end()))
                except re.error:
                    return []
                continue

            start = 0
            while True:
                index = target.find(term, start)
                if index == -1:
                    break
                begin = start_bound + index
                end = begin + len(term)
                results.append((begin, end))
                start = index + len(term)
        return results

    def _select_range(self, start: int, end: int) -> None:
        new_cursor = self._text_edit.textCursor()
        new_cursor.setPosition(start)
        new_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self._suppress_cursor_events = True
        self._text_edit.setTextCursor(new_cursor)
        self._suppress_cursor_events = False
        self._selected_line = new_cursor.blockNumber() + 1
        self._apply_extra_selections(new_cursor)

    def _on_cursor_moved(self) -> None:
        """Emit the current 1-based line number whenever the cursor moves."""
        if self._suppress_cursor_events:
            return
        cursor = self._text_edit.textCursor()
        line_number = cursor.blockNumber() + 1
        self._selected_line = line_number

        if cursor.hasSelection():
            self._multi_selected_lines.clear()
        elif self._multi_selected_lines:
            # Manual cursor move/click exits non-contiguous multi-selection mode.
            self._multi_selected_lines.clear()

        self._apply_extra_selections(cursor)
        self.line_selected.emit(line_number)

        if self._multi_selected_lines:
            lines = sorted(self._multi_selected_lines)
        elif cursor.hasSelection():
            doc = self._text_edit.document()
            sel_start = cursor.selectionStart()
            sel_end   = cursor.selectionEnd()
            start_block = doc.findBlock(sel_start).blockNumber()
            # Use sel_end-1 so a selection ending exactly at a block boundary
            # does not accidentally include the next (unselected) line.
            end_block = doc.findBlock(max(sel_start, sel_end - 1)).blockNumber()
            lines: list[int] = list(range(start_block + 1, end_block + 2))
        else:
            lines = [line_number]
        self.lines_selected.emit(lines)

    def _on_text_changed(self) -> None:
        if self._suppress_text_change:
            return
        self.content_changed.emit(self.get_content())

    def _apply_extra_selections(self, cursor: QTextCursor | None = None) -> None:
        """Apply warning-line and current-line overlays."""
        if cursor is None:
            cursor = self._text_edit.textCursor()

        selections: list[QTextEdit.ExtraSelection] = []

        if self._search_scope is not None:
            scope_start, scope_end = self._search_scope
            scope_selection = QTextEdit.ExtraSelection()
            scope_cursor = QTextCursor(self._text_edit.document())
            scope_cursor.setPosition(scope_start)
            scope_cursor.setPosition(scope_end, QTextCursor.MoveMode.KeepAnchor)
            scope_selection.cursor = scope_cursor
            scope_selection.format.setBackground(QColor(_SEARCH_SCOPE_COLOR))
            selections.append(scope_selection)

        for match_start, match_end in self._search_matches:
            match_selection = QTextEdit.ExtraSelection()
            match_cursor = QTextCursor(self._text_edit.document())
            match_cursor.setPosition(match_start)
            match_cursor.setPosition(match_end, QTextCursor.MoveMode.KeepAnchor)
            match_selection.cursor = match_cursor
            match_selection.format.setBackground(QColor(_SEARCH_MATCH_COLOR))
            selections.append(match_selection)

        doc = self._text_edit.document()
        for line_number, severity in self._warning_severity.items():
            block = doc.findBlockByLineNumber(line_number - 1)
            if not block.isValid():
                continue
            warning_selection = QTextEdit.ExtraSelection()
            warning_selection.cursor = QTextCursor(block)
            warning_selection.cursor.clearSelection()
            warning_selection.format.setBackground(QColor(_SEVERITY_COLORS[severity]))
            warning_selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection,
                True,
            )
            selections.append(warning_selection)

        if self._multi_selected_lines:
            for line_number in sorted(self._multi_selected_lines):
                block = doc.findBlockByLineNumber(line_number - 1)
                if not block.isValid():
                    continue
                multi_selection = QTextEdit.ExtraSelection()
                multi_selection.cursor = QTextCursor(block)
                multi_selection.cursor.clearSelection()
                multi_selection.format.setBackground(QColor(_MULTI_LINE_SELECTION_COLOR))
                multi_selection.format.setProperty(
                    QTextFormat.Property.FullWidthSelection,
                    True,
                )
                selections.append(multi_selection)

        selection = QTextEdit.ExtraSelection()
        selection.cursor = QTextCursor(cursor)
        selection.cursor.clearSelection()
        selection.format.setBackground(QColor(_CURRENT_LINE_COLOR))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selections.append(selection)

        self._text_edit.setExtraSelections(selections)
