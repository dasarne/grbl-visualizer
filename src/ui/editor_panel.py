"""G-Code editor panel."""

import re
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QTextEdit
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import (
    QTextCharFormat,
    QColor,
    QTextCursor,
    QTextFormat,
    QSyntaxHighlighter,
    QFont,
    QTextDocument,
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
    content_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._selected_line: int | None = None
        self._warning_severity: dict[int, WarningSeverity] = {}
        self._search_scope: tuple[int, int] | None = None
        self._search_matches: list[tuple[int, int]] = []
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
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_moved)
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)

    def load_content(self, content: str) -> None:
        """Load G-Code text into the editor."""
        self._suppress_text_change = True
        self._text_edit.setPlainText(content)
        self._text_edit.document().setModified(False)
        self._warning_severity.clear()
        self._search_scope = None
        self._search_matches = []
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
        """Scroll to and highlight the given 1-based line number."""
        doc = self._text_edit.document()
        block = doc.findBlockByLineNumber(line_number - 1)
        if not block.isValid():
            return
        self._selected_line = line_number
        cursor = QTextCursor(block)
        self._text_edit.setTextCursor(cursor)
        self._text_edit.centerCursor()
        self._apply_extra_selections(cursor)

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
        self._text_edit.copy()

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
        if use_regex:
            return self._find_regex(term, forward=True, cursor=cursor, search_in_selection=search_in_selection)
        return self._find_literal(term, forward=True, cursor=cursor, search_in_selection=search_in_selection)

    def find_previous(self, term: str, use_regex: bool = False, search_in_selection: bool = False) -> bool:
        """Find previous occurrence with optional regex support and wrap-around."""
        if not term:
            self._search_matches = []
            self._apply_extra_selections()
            return False
        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        self._update_search_matches(term, use_regex, cursor, search_in_selection)
        if use_regex:
            return self._find_regex(term, forward=False, cursor=cursor, search_in_selection=search_in_selection)
        return self._find_literal(term, forward=False, cursor=cursor, search_in_selection=search_in_selection)

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
        bounds = self._get_search_bounds(content, cursor, search_in_selection)
        if bounds is None:
            self._search_matches = []
            self._apply_extra_selections()
            return (False, 0)

        self._search_matches = self._compute_match_ranges(term, use_regex, content, bounds)
        self._apply_extra_selections()
        count = len(self._search_matches)
        if count == 0:
            return (False, 0)

        found = self.find_next(term, use_regex, search_in_selection)
        return (found, count)

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
        start_bound = 0
        end_bound = len(content)
        if search_in_selection:
            if self._search_scope is None:
                return 0
            start_bound, end_bound = self._search_scope

        target = content[start_bound:end_bound]
        try:
            if use_regex:
                new_target, count = re.subn(needle, replacement, target, flags=re.MULTILINE)
            else:
                count = target.count(needle)
                new_target = target.replace(needle, replacement)
        except re.error:
            return 0
        if count == 0:
            return 0

        new_content = content[:start_bound] + new_target + content[end_bound:]
        self._suppress_text_change = True
        cursor = self._text_edit.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(new_content)
        cursor.endEditBlock()
        self._text_edit.setTextCursor(cursor)
        self._apply_extra_selections()
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
        if not self._find_regex(pattern, forward=True, cursor=cursor, search_in_selection=search_in_selection):
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
        if not self._find_regex(pattern, forward=False, cursor=cursor, search_in_selection=search_in_selection):
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

    def _update_search_scope(self, cursor: QTextCursor, search_in_selection: bool) -> None:
        if not search_in_selection:
            if self._search_scope is not None:
                self._search_scope = None
                self._apply_extra_selections(cursor)
            return

        if self._search_scope is None and cursor.hasSelection():
            self._search_scope = (cursor.selectionStart(), cursor.selectionEnd())
            self._apply_extra_selections(cursor)

    def _count_matches(
        self,
        term: str,
        use_regex: bool,
        content: str,
        bounds: tuple[int, int],
    ) -> int:
        return len(self._compute_match_ranges(term, use_regex, content, bounds))

    def _update_search_matches(
        self,
        term: str,
        use_regex: bool,
        cursor: QTextCursor,
        search_in_selection: bool,
    ) -> None:
        content = self.get_content()
        bounds = self._get_search_bounds(content, cursor, search_in_selection)
        if not term or bounds is None:
            self._search_matches = []
            self._apply_extra_selections(cursor)
            return
        self._search_matches = self._compute_match_ranges(term, use_regex, content, bounds)
        self._apply_extra_selections(cursor)

    def _compute_match_ranges(
        self,
        term: str,
        use_regex: bool,
        content: str,
        bounds: tuple[int, int],
    ) -> list[tuple[int, int]]:
        start_bound, end_bound = bounds
        target = content[start_bound:end_bound]
        ranges: list[tuple[int, int]] = []

        if use_regex:
            try:
                for match in re.finditer(term, target, flags=re.MULTILINE):
                    ranges.append((start_bound + match.start(), start_bound + match.end()))
            except re.error:
                return []
            return ranges

        start = 0
        while True:
            index = target.find(term, start)
            if index == -1:
                break
            begin = start_bound + index
            end = begin + len(term)
            ranges.append((begin, end))
            start = index + len(term)
        return ranges

    def _select_range(self, start: int, end: int) -> None:
        new_cursor = self._text_edit.textCursor()
        new_cursor.setPosition(start)
        new_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self._text_edit.setTextCursor(new_cursor)

    def _on_cursor_moved(self) -> None:
        """Emit the current 1-based line number whenever the cursor moves."""
        cursor = self._text_edit.textCursor()
        line_number = cursor.blockNumber() + 1
        self._selected_line = line_number
        self._apply_extra_selections(cursor)
        self.line_selected.emit(line_number)

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

        selection = QTextEdit.ExtraSelection()
        selection.cursor = QTextCursor(cursor)
        selection.cursor.clearSelection()
        selection.format.setBackground(QColor(_CURRENT_LINE_COLOR))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selections.append(selection)

        self._text_edit.setExtraSelections(selections)
