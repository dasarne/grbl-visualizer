"""G-Code editor panel."""

import re
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QTextEdit, QToolTip
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
from ..gcode.commands import EXTENDED_COMMAND_DESCRIPTIONS
from ..gcode.dialects import get_profile
from .search_service import (
    compute_match_ranges,
    find_next_match,
    find_previous_match,
    replace_all_in_ranges,
)
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

_CMD_TOKEN_RE = re.compile(r"\b([GMT]\d+(?:\.\d+)?)\b", re.IGNORECASE)
_PARAM_TOKEN_RE = re.compile(r"\b([A-Z])([-+]?\d*\.?\d+)\b", re.IGNORECASE)
_PAREN_COMMENT_RE = re.compile(r"\([^)]*\)")

_PARAM_EXPLANATIONS_DE: dict[str, str] = {
    "X": "X-Koordinate",
    "Y": "Y-Koordinate",
    "Z": "Z-Koordinate",
    "A": "A-Achse (Mehrachsensystem)",
    "B": "B-Achse (Mehrachsensystem)",
    "C": "C-Achse (Mehrachsensystem)",
    "I": "Relativer Kreismittelpunkt I (X-Anteil)",
    "J": "Relativer Kreismittelpunkt J (Y-Anteil)",
    "F": "Vorschub",
}

_PARAM_EXPLANATIONS_EN: dict[str, str] = {
    "X": "X coordinate",
    "Y": "Y coordinate",
    "Z": "Z coordinate",
    "A": "A axis (multi-axis system)",
    "B": "B axis (multi-axis system)",
    "C": "C axis (multi-axis system)",
    "I": "Arc centre offset I (X component)",
    "J": "Arc centre offset J (Y component)",
    "F": "Feed rate",
}


class _GCodeSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for G-code commands, axis words, and comments."""

    def __init__(self, document) -> None:
        super().__init__(document)
        # Commands known to the active dialect profile (None = accept any command)
        self._known_commands: set[str] | None = None

        _ci = QRegularExpression.PatternOption.CaseInsensitiveOption

        self._cmd_re = QRegularExpression(
            r"^\s*(?:N\d+\s+)?([GMT]\d+(?:\.\d+)?)", _ci,
        )
        self._x_re  = QRegularExpression(r"\bX[-+]?\d*\.?\d+\b", _ci)
        self._y_re  = QRegularExpression(r"\bY[-+]?\d*\.?\d+\b", _ci)
        self._z_re  = QRegularExpression(r"\bZ[-+]?\d*\.?\d+\b", _ci)
        self._ij_re = QRegularExpression(r"\b[IJ][-+]?\d*\.?\d+\b", _ci)
        self._f_re  = QRegularExpression(r"\bF[-+]?\d*\.?\d+\b", _ci)
        # Parenthetical comment: ( ... )
        self._paren_comment_re = QRegularExpression(r"\([^)]*\)")
        # Semicolon comment: ; to end of line
        self._semi_comment_re  = QRegularExpression(r";.*$")

        self._cmd_fmt = QTextCharFormat()
        self._cmd_fmt.setForeground(QColor("#0B3D91"))
        self._cmd_fmt.setFontWeight(QFont.Weight.Bold)

        # Unknown / unsupported command in the active dialect
        self._cmd_unknown_fmt = QTextCharFormat()
        self._cmd_unknown_fmt.setForeground(QColor("#AA3300"))
        self._cmd_unknown_fmt.setFontWeight(QFont.Weight.Bold)
        self._cmd_unknown_fmt.setFontUnderline(True)

        self._x_fmt = QTextCharFormat()
        self._x_fmt.setForeground(QColor("#CC3333"))

        self._y_fmt = QTextCharFormat()
        self._y_fmt.setForeground(QColor("#33AA33"))

        self._z_fmt = QTextCharFormat()
        self._z_fmt.setForeground(QColor("#3366CC"))

        self._ij_fmt = QTextCharFormat()
        self._ij_fmt.setForeground(QColor("#CC6600"))

        self._f_fmt = QTextCharFormat()
        self._f_fmt.setForeground(QColor("#9933CC"))

        self._comment_fmt = QTextCharFormat()
        self._comment_fmt.setForeground(QColor("#6A9955"))
        self._comment_fmt.setFontWeight(QFont.Weight.Bold)

    def update_profile(self, profile_id: str | None) -> None:
        """Set the active dialect profile; rehighlights all blocks."""
        if profile_id is None:
            self._known_commands = None
        else:
            try:
                profile = get_profile(profile_id)
                self._known_commands = {c.upper() for c in profile.known_commands}
            except ValueError:
                self._known_commands = None
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        # Commands first (highest visual priority)
        cmd_match = self._cmd_re.match(text)
        if cmd_match.hasMatch():
            start = cmd_match.capturedStart(1)
            length = cmd_match.capturedLength(1)
            command = cmd_match.captured(1).upper()
            if self._known_commands is not None and command not in self._known_commands:
                fmt = self._cmd_unknown_fmt
            else:
                fmt = self._cmd_fmt
            self.setFormat(start, length, fmt)

        self._apply_regex(text, self._x_re,  self._x_fmt)
        self._apply_regex(text, self._y_re,  self._y_fmt)
        self._apply_regex(text, self._z_re,  self._z_fmt)
        self._apply_regex(text, self._ij_re, self._ij_fmt)
        self._apply_regex(text, self._f_re,  self._f_fmt)

        # Comments last — override everything they cover
        self._apply_regex(text, self._paren_comment_re, self._comment_fmt)
        self._apply_regex(text, self._semi_comment_re,  self._comment_fmt)

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
        self._language = "de"
        self._profile_id: str | None = None
        self._selected_line: int | None = None
        self._warning_severity: dict[int, WarningSeverity] = {}
        self._line_warnings: dict[int, list[AnalysisWarning]] = {}
        self._search_scope: tuple[int, int] | None = None
        self._search_matches: list[tuple[int, int]] = []
        self._multi_selected_lines: set[int] = set()
        self._selection_anchor_line: int | None = None
        self._mouse_drag_active = False
        self._mouse_drag_mode: str | None = None
        self._mouse_drag_anchor_line: int | None = None
        self._mouse_drag_base_selection: set[int] = set()
        # Stores the key modifiers from the most recent navigation keypress so
        # _on_cursor_moved can react correctly.  None = cursor was NOT moved by
        # a navigation key (e.g. moved by a mouse event that we later released).
        self._key_nav_mods: Qt.KeyboardModifier | None = None
        self._suppress_cursor_events = False
        self._suppress_text_change = False
        self._managed_search_edit = False
        self._setup_ui()

    def set_language(self, language: str) -> None:
        self._language = language

    def set_profile_id(self, profile_id: str | None) -> None:
        """Update the active dialect profile and refresh syntax highlighting."""
        self._profile_id = profile_id
        self._syntax.update_profile(profile_id)

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
        self._text_edit.viewport().setMouseTracking(True)

        self._text_edit.installEventFilter(self)
        self._text_edit.viewport().installEventFilter(self)
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_moved)
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)

    def eventFilter(self, obj, event) -> bool:
        """Handle keyboard and mouse events for unified line-level multi-select."""
        if (
            obj is self._text_edit.viewport()
            and event.type() == QEvent.Type.MouseButtonDblClick
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            # Treat double-click like a normal single-line select.
            cursor = self._text_edit.cursorForPosition(event.position().toPoint())
            line_number = cursor.blockNumber() + 1
            self._multi_selected_lines = {line_number}
            self._selection_anchor_line = line_number
            self._mouse_drag_active = False
            self._suppress_cursor_events = True
            self._text_edit.setTextCursor(cursor)
            self._suppress_cursor_events = False
            self._apply_extra_selections(cursor)
            self.lines_selected.emit(sorted(self._multi_selected_lines))
            return True

        if (
            obj is self._text_edit.viewport()
            and event.type() == QEvent.Type.MouseMove
            and isinstance(event, QMouseEvent)
        ):
            self._update_hover_tooltip(event)
            # Drag: extend range selection while left button is held.
            if bool(event.buttons() & Qt.MouseButton.LeftButton) and self._mouse_drag_active:
                cursor = self._text_edit.cursorForPosition(event.position().toPoint())
                line_number = cursor.blockNumber() + 1

                anchor = self._mouse_drag_anchor_line if self._mouse_drag_anchor_line is not None else line_number
                lo = min(anchor, line_number)
                hi = max(anchor, line_number)
                dragged_range = set(range(lo, hi + 1))

                if self._mouse_drag_mode == "ctrl":
                    # Ctrl+drag adds a contiguous range to the selection.
                    self._multi_selected_lines = self._mouse_drag_base_selection | dragged_range
                else:
                    self._multi_selected_lines = dragged_range

                self._suppress_cursor_events = True
                self._text_edit.setTextCursor(cursor)
                self._suppress_cursor_events = False
                self._apply_extra_selections(cursor)
                self.lines_selected.emit(sorted(self._multi_selected_lines))
                return True
            return False

        if obj is self._text_edit.viewport() and event.type() == QEvent.Type.Leave:
            QToolTip.hideText()
            return False

        # Intercept ALL left-click presses – convert to line-level multi-select.
        if (
            obj is self._text_edit.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            cursor = self._text_edit.cursorForPosition(event.position().toPoint())
            line_number = cursor.blockNumber() + 1
            mods = event.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

            self._mouse_drag_active = True
            self._mouse_drag_anchor_line = line_number
            self._mouse_drag_base_selection = set(self._multi_selected_lines)

            if ctrl:
                # Ctrl+Click: toggle the clicked line.
                self._mouse_drag_mode = "ctrl"
                if line_number in self._multi_selected_lines:
                    self._multi_selected_lines.discard(line_number)
                else:
                    self._multi_selected_lines.add(line_number)
                    self._selection_anchor_line = line_number
            elif shift and self._selection_anchor_line is not None:
                # Shift+Click: range-extend from anchor to clicked line.
                self._mouse_drag_mode = "shift"
                start = min(self._selection_anchor_line, line_number)
                end = max(self._selection_anchor_line, line_number)
                self._multi_selected_lines = set(range(start, end + 1))
            else:
                # Plain click: if the line is already selected keep the whole
                # multi-selection intact (avoids accidental deselect on tremor).
                # Only reset when clicking on a line that is NOT selected.
                self._mouse_drag_mode = "plain"
                if line_number not in self._multi_selected_lines:
                    self._multi_selected_lines = {line_number}
                    self._selection_anchor_line = line_number

            self._suppress_cursor_events = True
            self._text_edit.setTextCursor(cursor)
            self._suppress_cursor_events = False
            self._apply_extra_selections(cursor)
            self.lines_selected.emit(sorted(self._multi_selected_lines))
            return True  # block native character-level selection

        if (
            obj is self._text_edit.viewport()
            and event.type() == QEvent.Type.MouseButtonRelease
            and isinstance(event, QMouseEvent)
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._mouse_drag_active = False
            self._mouse_drag_mode = None
            self._mouse_drag_anchor_line = None
            self._mouse_drag_base_selection = set()
            # Return False so Qt can deliver the MouseButtonDblClick event that
            # follows a double-click (consuming Release blocks DblClick delivery).
            return False

        # Navigation keys (Arrow / Home / End / Page): record the modifier state
        # so _on_cursor_moved can apply the right selection logic, then let
        # native Qt move the cursor (return False).
        if (
            obj in (self._text_edit, self._text_edit.viewport())
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in {
                Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down,
                Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
            }
        ):
            self._key_nav_mods = event.modifiers()
            return False  # let native handle → _on_cursor_moved fires

        # Ctrl+A: select all lines.
        if (
            obj in (self._text_edit, self._text_edit.viewport())
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() == Qt.Key.Key_A
            and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ):
            doc = self._text_edit.document()
            total = doc.blockCount()
            self._multi_selected_lines = set(range(1, total + 1))
            self._selection_anchor_line = 1
            self._apply_extra_selections()
            self.lines_selected.emit(sorted(self._multi_selected_lines))
            return True

        if (
            obj in (self._text_edit, self._text_edit.viewport())
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and self._multi_selected_lines
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
                first_line = min(self._multi_selected_lines)
                self._delete_multi_selected_lines()
                doc = self._text_edit.document()
                block = doc.findBlockByLineNumber(max(0, first_line - 1))
                insert_cursor = self._text_edit.textCursor()
                if block.isValid():
                    insert_cursor.setPosition(block.position())
                self._suppress_cursor_events = True
                self._text_edit.setTextCursor(insert_cursor)
                self._suppress_cursor_events = False
                self._text_edit.insertPlainText(text)
                return True

        return super().eventFilter(obj, event)

    def load_content(self, content: str) -> None:
        """Load G-Code text into the editor."""
        self._suppress_text_change = True
        self._text_edit.setPlainText(content)
        self._text_edit.document().setModified(False)
        self._warning_severity.clear()
        self._line_warnings.clear()
        self._search_scope = None
        self._search_matches = []
        self._multi_selected_lines.clear()
        self._selection_anchor_line = None
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
        self._multi_selected_lines = {line_number}
        self._selection_anchor_line = line_number
        self._selected_line = line_number
        cursor = QTextCursor(block)
        cursor.clearSelection()
        self._suppress_cursor_events = True
        self._text_edit.setTextCursor(cursor)
        self._suppress_cursor_events = False
        self._text_edit.centerCursor()
        self._apply_extra_selections(cursor)

    def highlight_lines(self, line_numbers: list[int]) -> None:
        """Highlight a non-contiguous set of 1-based line numbers."""
        if not line_numbers:
            self._multi_selected_lines.clear()
            self._selection_anchor_line = None
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
        self._selection_anchor_line = first
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
        self._selection_anchor_line = None
        self._search_scope = None
        self._search_matches = []
        self._apply_extra_selections()
        self.lines_selected.emit([])

    def mark_warning_lines(self, warnings: list[AnalysisWarning]) -> None:
        """Apply warning highlights as non-destructive extra selections."""
        line_severity: dict[int, WarningSeverity] = {}
        line_warnings: dict[int, list[AnalysisWarning]] = {}
        for w in warnings:
            if w.line_number is None:
                continue
            line_warnings.setdefault(w.line_number, []).append(w)
            existing = line_severity.get(w.line_number)
            if existing is None or w.severity.value > existing.value:
                line_severity[w.line_number] = w.severity
        self._warning_severity = line_severity
        self._line_warnings = line_warnings
        self._apply_extra_selections()

    def _update_hover_tooltip(self, event: QMouseEvent) -> None:
        """Show a context tooltip for the token under the mouse cursor."""
        cursor = self._text_edit.cursorForPosition(event.position().toPoint())
        block = cursor.block()
        if not block.isValid():
            QToolTip.hideText()
            return

        line_text = block.text()
        line_number = block.blockNumber() + 1
        column = cursor.positionInBlock()

        token_text = self._describe_token_at(line_text, column)
        warning_text = self._describe_line_warnings(line_number)

        if token_text and warning_text:
            tooltip = f"{token_text}\n\n{warning_text}"
        elif token_text:
            tooltip = token_text
        elif warning_text:
            tooltip = warning_text
        else:
            QToolTip.hideText()
            return

        QToolTip.showText(event.globalPosition().toPoint(), tooltip, self._text_edit.viewport())

    def _describe_token_at(self, line_text: str, column: int) -> str | None:
        """Return a short explanation for the token located at the given column."""
        if not line_text:
            return None

        de = self._language != "en"

        semicolon_idx = line_text.find(";")
        if semicolon_idx >= 0 and column >= semicolon_idx:
            comment = line_text[semicolon_idx + 1:].strip()
            comment_text = comment if comment else ("(leer)" if de else "(empty)")
            label = "Kommentar" if de else "Comment"
            return f"{label}: {comment_text}"

        for match in _PAREN_COMMENT_RE.finditer(line_text):
            start, end = match.span()
            if start <= column < end:
                comment = match.group(0)[1:-1].strip()
                comment_text = comment if comment else ("(leer)" if de else "(empty)")
                label = "Kommentar" if de else "Comment"
                return f"{label}: {comment_text}"

        for match in _CMD_TOKEN_RE.finditer(line_text):
            start, end = match.span(1)
            if start <= column < end:
                command = match.group(1).upper()
                description = EXTENDED_COMMAND_DESCRIPTIONS.get(command)
                cmd_label = "Befehl" if de else "Command"
                parts: list[str] = []
                if description:
                    parts.append(f"{cmd_label} {command}: {description}")
                else:
                    parts.append(f"{cmd_label} {command}")
                # Add dialect support hint when a profile is active
                if self._profile_id is not None:
                    try:
                        profile = get_profile(self._profile_id)
                        if command in profile.unsupported_commands:
                            hint = (
                                f"⚠ Nicht unterstützt durch {profile.name}"
                                if de else
                                f"⚠ Not supported by {profile.name}"
                            )
                            parts.append(hint)
                        elif command not in profile.known_commands:
                            hint = (
                                f"⚠ Unbekannt für Dialekt {profile.name}"
                                if de else
                                f"⚠ Unknown for dialect {profile.name}"
                            )
                            parts.append(hint)
                    except ValueError:
                        pass
                return "\n".join(parts)

        for match in _PARAM_TOKEN_RE.finditer(line_text):
            start, end = match.span(0)
            if start <= column < end:
                key = match.group(1).upper()
                raw_value = match.group(2)
                return self._format_parameter_tooltip(key, raw_value)

        return None

    def _format_parameter_tooltip(self, key: str, raw_value: str) -> str:
        """Format tooltip text for a parameter token."""
        de = self._language != "en"
        explanations = _PARAM_EXPLANATIONS_DE if de else _PARAM_EXPLANATIONS_EN
        description = explanations.get(key, f"{key}-Parameter" if de else f"{key} parameter")
        try:
            value = float(raw_value)
        except ValueError:
            value_text = raw_value
        else:
            if key == "F":
                value_text = f"{value:.2f} " + ("Einheit/min" if de else "units/min")
            elif key in {"X", "Y", "Z", "I", "J", "A", "B", "C"}:
                value_text = f"{value:.3f}"
            else:
                value_text = f"{value:g}"
        return f"{description}: {value_text}"

    def _describe_line_warnings(self, line_number: int) -> str | None:
        """Return analyzer warning/error context for a given line, if available."""
        warnings = self._line_warnings.get(line_number)
        if not warnings:
            return None

        de = self._language != "en"
        header = "Analysehinweise:" if de else "Analysis notes:"
        parts: list[str] = [header]
        for warning in warnings[:3]:
            parts.append(f"- {warning.severity.name}: {warning.message}")
            if warning.severity == WarningSeverity.ERROR:
                reason_label = "Grund" if de else "Reason"
                parts.append(f"  {reason_label}: {warning.message}")
            if warning.suggestion:
                suggestion_label = "Vorschlag" if de else "Suggestion"
                parts.append(f"  {suggestion_label}: {warning.suggestion}")

        if len(warnings) > 3:
            more = len(warnings) - 3
            parts.append(f"- ... {more} weitere Hinweise" if de else f"- ... {more} more notes")

        return "\n".join(parts)

    def copy(self) -> None:
        if self._multi_selected_lines:
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
        """Return text of currently selected lines."""
        if self._multi_selected_lines:
            doc = self._text_edit.document()
            lines_text: list[str] = []
            for ln in sorted(self._multi_selected_lines):
                block = doc.findBlockByLineNumber(ln - 1)
                if block.isValid():
                    lines_text.append(block.text())
            return "\n".join(lines_text)
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

    def find_next(self, term: str, use_regex: bool = False, search_in_selection: bool = False, case_sensitive: bool = False) -> bool:
        """Find next occurrence with optional regex support and wrap-around."""
        if not term:
            self._search_matches = []
            self._apply_extra_selections()
            return False
        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        self._update_search_matches(term, use_regex, cursor, search_in_selection, case_sensitive)
        if not self._search_matches:
            return False

        anchor = cursor.selectionEnd() if cursor.hasSelection() else cursor.position()
        match = find_next_match(self._search_matches, anchor)
        if match is None:
            return False
        self._select_range(*match)
        return True

    def find_previous(self, term: str, use_regex: bool = False, search_in_selection: bool = False, case_sensitive: bool = False) -> bool:
        """Find previous occurrence with optional regex support and wrap-around."""
        if not term:
            self._search_matches = []
            self._apply_extra_selections()
            return False
        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        self._update_search_matches(term, use_regex, cursor, search_in_selection, case_sensitive)
        if not self._search_matches:
            return False

        anchor = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
        match = find_previous_match(self._search_matches, anchor)
        if match is None:
            return False
        self._select_range(*match)
        return True

    def get_search_match_count(self) -> int:
        """Return the number of currently cached search matches."""
        return len(self._search_matches)

    def preview_search(
        self,
        term: str,
        use_regex: bool = False,
        search_in_selection: bool = False,
        case_sensitive: bool = False,
    ) -> tuple[bool, int]:
        """Incremental search preview: keep match selected and return hit count."""
        cursor = self._text_edit.textCursor()
        self._update_search_scope(cursor, search_in_selection)
        # When the scope was just locked from the cursor's current selection,
        # that selection (orange QPalette highlight) would cover the green
        # match highlights.  Move the cursor to scope start to make them visible.
        if (
            search_in_selection
            and self._search_scope is not None
            and cursor.hasSelection()
            and cursor.selectionStart() == self._search_scope[0]
            and cursor.selectionEnd() == self._search_scope[1]
        ):
            cleared = QTextCursor(self._text_edit.document())
            cleared.setPosition(self._search_scope[0])
            self._suppress_cursor_events = True
            self._text_edit.setTextCursor(cleared)
            self._suppress_cursor_events = False
            cursor = cleared

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

        self._search_matches = compute_match_ranges(term, use_regex, content, ranges, case_sensitive)
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
        case_sensitive: bool = False,
    ) -> bool:
        """Replace next occurrence and move to next. Returns True if replacement made."""
        if not needle:
            return False
        cursor = self._text_edit.textCursor()
        if use_regex:
            return self._replace_regex_next(needle, replacement, cursor, search_in_selection, case_sensitive)
        if not self.find_next(needle, use_regex=False, search_in_selection=search_in_selection, case_sensitive=case_sensitive):
            return False
        cursor = self._text_edit.textCursor()
        match_start = cursor.selectionStart()
        match_end = cursor.selectionEnd()
        self._managed_search_edit = True
        try:
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.insertText(replacement)
            cursor.endEditBlock()
            self._text_edit.setTextCursor(cursor)
            self._shift_scope_after_replace(match_start, match_end, len(replacement))
        finally:
            self._managed_search_edit = False
        return True

    def replace_previous(
        self,
        needle: str,
        replacement: str,
        use_regex: bool = False,
        search_in_selection: bool = False,
        case_sensitive: bool = False,
    ) -> bool:
        """Replace previous occurrence and move to previous. Returns True if replacement made."""
        if not needle:
            return False
        cursor = self._text_edit.textCursor()
        if use_regex:
            return self._replace_regex_previous(needle, replacement, cursor, search_in_selection, case_sensitive)
        if not self._selection_matches_query(cursor, needle, use_regex=False):
            if not self.find_previous(needle, use_regex=False, search_in_selection=search_in_selection, case_sensitive=case_sensitive):
                return False
            cursor = self._text_edit.textCursor()
        match_start = cursor.selectionStart()
        match_end = cursor.selectionEnd()
        self._managed_search_edit = True
        try:
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.insertText(replacement)
            cursor.endEditBlock()
            self._text_edit.setTextCursor(cursor)
            self._shift_scope_after_replace(match_start, match_end, len(replacement))
        finally:
            self._managed_search_edit = False
        self._move_cursor_to_position(match_start)
        self.find_previous(needle, use_regex=False, search_in_selection=search_in_selection, case_sensitive=case_sensitive)
        return True

    def replace_all(
        self,
        needle: str,
        replacement: str,
        use_regex: bool = False,
        search_in_selection: bool = False,
        case_sensitive: bool = False,
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

        new_content, count = replace_all_in_ranges(
            content,
            ranges,
            needle,
            replacement,
            use_regex,
            case_sensitive,
        )
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
        restore_pos = max(0, min(prev_pos, max_pos))
        restore_cursor = self._text_edit.textCursor()
        # Do NOT restore the selection anchor – after content changed, the old
        # selection offsets are wrong and would leave a stale _search_scope that
        # causes double-replacements on the next operation.
        restore_cursor.setPosition(restore_pos)
        self._suppress_cursor_events = True
        self._text_edit.setTextCursor(restore_cursor)
        self._suppress_cursor_events = False
        self._text_edit.verticalScrollBar().setValue(prev_vscroll)
        self._text_edit.horizontalScrollBar().setValue(prev_hscroll)

        # Invalidate scope and match cache – positions are meaningless in the
        # new content.  The next interaction will re-establish them.
        self._search_scope = None
        self._search_matches = []
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
        case_sensitive: bool = False,
    ) -> bool:
        """Replace next regex match and move cursor."""
        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            return False
        if not self.find_next(pattern, use_regex=True, search_in_selection=search_in_selection, case_sensitive=case_sensitive):
            return False
        cursor = self._text_edit.textCursor()
        match_text = cursor.selectedText()
        new_text = regex.sub(replacement, match_text, count=1)
        match_start = cursor.selectionStart()
        match_end = cursor.selectionEnd()
        self._managed_search_edit = True
        try:
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.insertText(new_text)
            cursor.endEditBlock()
            self._text_edit.setTextCursor(cursor)
            self._shift_scope_after_replace(match_start, match_end, len(new_text))
        finally:
            self._managed_search_edit = False
        return True

    def _replace_regex_previous(
        self,
        pattern: str,
        replacement: str,
        cursor: QTextCursor,
        search_in_selection: bool,
        case_sensitive: bool = False,
    ) -> bool:
        """Replace previous regex match and move cursor."""
        flags = re.MULTILINE
        if not case_sensitive:
            flags |= re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error:
            return False
        if not self._selection_matches_query(cursor, pattern, use_regex=True):
            if not self.find_previous(pattern, use_regex=True, search_in_selection=search_in_selection, case_sensitive=case_sensitive):
                return False
            cursor = self._text_edit.textCursor()
        match_text = cursor.selectedText()
        new_text = regex.sub(replacement, match_text, count=1)
        match_start = cursor.selectionStart()
        match_end = cursor.selectionEnd()
        self._managed_search_edit = True
        try:
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.insertText(new_text)
            cursor.endEditBlock()
            self._text_edit.setTextCursor(cursor)
            self._shift_scope_after_replace(match_start, match_end, len(new_text))
        finally:
            self._managed_search_edit = False
        self._move_cursor_to_position(match_start)
        self.find_previous(pattern, use_regex=True, search_in_selection=search_in_selection, case_sensitive=case_sensitive)
        return True

    def _move_cursor_to_position(self, position: int) -> None:
        """Move the text cursor to a plain insertion point without selection."""
        cursor = self._text_edit.textCursor()
        cursor.setPosition(position)
        self._suppress_cursor_events = True
        self._text_edit.setTextCursor(cursor)
        self._suppress_cursor_events = False

    def _selection_matches_query(
        self,
        cursor: QTextCursor,
        term: str,
        use_regex: bool,
    ) -> bool:
        """Return whether the current selection itself is a match for the query."""
        if not cursor.hasSelection():
            return False
        selected_text = cursor.selectedText()
        if use_regex:
            try:
                return re.fullmatch(term, selected_text, re.MULTILINE) is not None
            except re.error:
                return False
        return selected_text == term

    def _shift_scope_after_replace(
        self, match_start: int, match_end: int, new_len: int
    ) -> None:
        """Adjust _search_scope and _search_matches after a single replacement.

        After replacing text the document length changes by
        ``new_len - (match_end - match_start)``.  The scope end and every
        cached match position that lies after the replacement must be shifted
        by that delta so highlights and subsequent searches stay correct.
        """
        delta = new_len - (match_end - match_start)

        # Shift scope end.
        if self._search_scope is not None:
            scope_start, scope_end = self._search_scope
            if match_end <= scope_end:
                self._search_scope = (scope_start, scope_end + delta)

        # Remove the replaced match and shift all following ones.
        updated: list[tuple[int, int]] = []
        for ms, me in self._search_matches:
            if me <= match_start:
                # Entirely before the replacement – unchanged.
                updated.append((ms, me))
            elif ms >= match_end:
                # Entirely after the replacement – shift by delta.
                updated.append((ms + delta, me + delta))
            # else: this was the replaced match itself – drop it.
        self._search_matches = updated

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

        # Scope already locked from a prior user selection.  Never overwrite
        # it with a (smaller) match selection placed by find_next/_select_range.
        # Released only when search_in_selection becomes False.
        if self._search_scope is not None:
            return

        if cursor.hasSelection():
            self._search_scope = (cursor.selectionStart(), cursor.selectionEnd())
            self._apply_extra_selections(cursor)

    def _count_matches(
        self,
        term: str,
        use_regex: bool,
        content: str,
        bounds: tuple[int, int],
        case_sensitive: bool = False,
    ) -> int:
        return len(compute_match_ranges(term, use_regex, content, [bounds], case_sensitive))

    def _update_search_matches(
        self,
        term: str,
        use_regex: bool,
        cursor: QTextCursor,
        search_in_selection: bool,
        case_sensitive: bool = False,
    ) -> None:
        content = self.get_content()
        ranges = self._get_search_ranges(content, cursor, search_in_selection)
        if not term or ranges is None:
            self._search_matches = []
            self._apply_extra_selections(cursor)
            return
        self._search_matches = compute_match_ranges(term, use_regex, content, ranges, case_sensitive)
        self._apply_extra_selections(cursor)

    def _compute_match_ranges(
        self,
        term: str,
        use_regex: bool,
        content: str,
        ranges: list[tuple[int, int]],
        case_sensitive: bool = False,
    ) -> list[tuple[int, int]]:
        return compute_match_ranges(term, use_regex, content, ranges, case_sensitive)

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

        if self._key_nav_mods is None:
            # Cursor moved for a non-keyboard reason (e.g. mouse Release that we
            # returned False from).  Keep the existing selection, just refresh visuals.
            self._apply_extra_selections(cursor)
            self.line_selected.emit(line_number)
            self.lines_selected.emit(sorted(self._multi_selected_lines))
            return

        # Consume the pending flag – this is a keyboard-navigation move.
        mods = self._key_nav_mods
        self._key_nav_mods = None

        if bool(mods & Qt.KeyboardModifier.ShiftModifier) and self._selection_anchor_line is not None:
            # Shift+Arrow: extend range from anchor to cursor line.
            start = min(self._selection_anchor_line, line_number)
            end = max(self._selection_anchor_line, line_number)
            self._multi_selected_lines = set(range(start, end + 1))
        else:
            # Plain Arrow: move single-line selection to cursor line, reset anchor.
            self._multi_selected_lines = {line_number}
            self._selection_anchor_line = line_number

        # Clear any native text selection – we use _multi_selected_lines for all visuals.
        if cursor.hasSelection():
            bare = QTextCursor(cursor)
            bare.clearSelection()
            self._suppress_cursor_events = True
            self._text_edit.setTextCursor(bare)
            self._suppress_cursor_events = False

        self._apply_extra_selections(cursor)
        self.line_selected.emit(line_number)
        self.lines_selected.emit(sorted(self._multi_selected_lines))

    def _on_text_changed(self) -> None:
        if self._suppress_text_change:
            return
        if not self._managed_search_edit:
            self._invalidate_search_state()
        self.content_changed.emit(self.get_content())

    def _invalidate_search_state(self) -> None:
        """Clear cached search overlays after arbitrary document edits.

        Undo/redo and free typing can move or delete text without going through
        the managed search-replace path, so cached absolute match offsets are no
        longer trustworthy after such edits.
        """
        self._search_scope = None
        self._search_matches = []
        self._apply_extra_selections()

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

        # Only show the current-line (blue) indicator when the cursor is on a
        # line that is NOT already highlighted as a multi-selection (yellow).
        # This makes the yellow selection clearly visible for every selected line,
        # including after plain Arrow-key navigation.
        cursor_line = cursor.blockNumber() + 1
        if cursor_line not in self._multi_selected_lines:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(cursor)
            selection.cursor.clearSelection()
            selection.format.setBackground(QColor(_CURRENT_LINE_COLOR))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selections.append(selection)

        self._text_edit.setExtraSelections(selections)
