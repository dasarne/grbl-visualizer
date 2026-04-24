"""Floating Find and Replace dialog for G-Code editor."""

import re
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from .resources import get_strings


class FindReplaceDialog(QDialog):
    """Floating modal-less dialog for finding and replacing text with regex support."""

    find_next_requested = pyqtSignal(str, bool, bool, bool)  # term, use_regex, search_in_selection, case_sensitive
    find_previous_requested = pyqtSignal(str, bool, bool, bool)
    replace_next_requested = pyqtSignal(str, str, bool, bool, bool)  # needle, replacement, use_regex, search_in_selection, case_sensitive
    replace_previous_requested = pyqtSignal(str, str, bool, bool, bool)
    replace_all_requested = pyqtSignal(str, str, bool, bool, bool)
    search_updated = pyqtSignal(str, bool, bool, bool)  # term, use_regex, search_in_selection, case_sensitive
    dialog_closed = pyqtSignal()

    def __init__(self, parent=None, language: str = "en"):
        super().__init__(parent)
        self._language = language
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(500)
        self._setup_ui()
        self._apply_language()

    def _setup_ui(self) -> None:
        """Build the dialog layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Find row
        find_layout = QHBoxLayout()
        self._find_label = QLabel("")
        self._find_input = QLineEdit()
        self._find_input.textChanged.connect(self._on_find_text_changed)
        self._find_input.returnPressed.connect(self._on_find_next)
        find_layout.addWidget(self._find_label)
        find_layout.addWidget(self._find_input)
        layout.addLayout(find_layout)

        # Find buttons row
        find_buttons_layout = QHBoxLayout()
        self._find_prev_btn = QPushButton("")
        self._find_prev_btn.clicked.connect(self._on_find_previous)
        self._find_prev_btn.setShortcut(QKeySequence("Shift+F3"))
        find_buttons_layout.addWidget(self._find_prev_btn)

        self._find_next_btn = QPushButton("")
        self._find_next_btn.clicked.connect(self._on_find_next)
        self._find_next_btn.setShortcut(QKeySequence("F3"))
        find_buttons_layout.addWidget(self._find_next_btn)

        self._regex_check = QCheckBox("Regular Expression")
        self._regex_check.stateChanged.connect(self._on_find_text_changed)
        find_buttons_layout.addWidget(self._regex_check)

        self._selection_check = QCheckBox("In Selection")
        self._selection_check.stateChanged.connect(self._on_find_text_changed)
        find_buttons_layout.addWidget(self._selection_check)

        self._case_check = QCheckBox("Match Case")
        self._case_check.stateChanged.connect(self._on_find_text_changed)
        find_buttons_layout.addWidget(self._case_check)

        find_buttons_layout.addStretch()
        layout.addLayout(find_buttons_layout)

        # Replace row
        replace_layout = QHBoxLayout()
        self._replace_label = QLabel("")
        self._replace_input = QLineEdit()
        self._replace_input.returnPressed.connect(self._on_replace_next)
        replace_layout.addWidget(self._replace_label)
        replace_layout.addWidget(self._replace_input)
        layout.addLayout(replace_layout)

        # Replace buttons row
        replace_buttons_layout = QHBoxLayout()
        self._replace_prev_btn = QPushButton("")
        self._replace_prev_btn.clicked.connect(self._on_replace_previous)
        self._replace_prev_btn.setShortcut(QKeySequence("Shift+Ctrl+H"))
        replace_buttons_layout.addWidget(self._replace_prev_btn)

        self._replace_next_btn = QPushButton("")
        self._replace_next_btn.clicked.connect(self._on_replace_next)
        self._replace_next_btn.setShortcut(QKeySequence("Ctrl+H"))
        replace_buttons_layout.addWidget(self._replace_next_btn)

        self._replace_all_btn = QPushButton("")
        self._replace_all_btn.clicked.connect(self._on_replace_all)
        self._replace_all_btn.setShortcut(QKeySequence("Ctrl+Alt+H"))
        replace_buttons_layout.addWidget(self._replace_all_btn)

        replace_buttons_layout.addStretch()
        layout.addLayout(replace_buttons_layout)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _apply_language(self) -> None:
        """Update all labels and titles based on language."""
        strings = self._get_strings()
        self.setWindowTitle(strings["title"])
        self._find_label.setText(strings["find_label"])
        self._find_prev_btn.setText(strings["find_prev"])
        self._find_next_btn.setText(strings["find_next"])
        self._regex_check.setText(strings["regex"])
        self._replace_label.setText(strings["replace_label"])
        self._replace_prev_btn.setText(strings["replace_prev"])
        self._replace_next_btn.setText(strings["replace_next"])
        self._replace_all_btn.setText(strings["replace_all"])
        self._selection_check.setText(strings["in_selection"])
        self._case_check.setText(strings["case_sensitive"])
        self._find_input.setPlaceholderText(strings["find_placeholder"])
        self._replace_input.setPlaceholderText(strings["replace_placeholder"])

    def set_language(self, language: str) -> None:
        """Update dialog language."""
        self._language = language
        self._apply_language()

    def _get_strings(self) -> dict[str, str]:
        """Get language strings from shared resources."""
        s = get_strings(self._language)
        return {
            "title": s["find.title"],
            "find_label": s["find.find_label"],
            "find_prev": s["find.find_prev"],
            "find_next": s["find.find_next"],
            "regex": s["find.regex"],
            "replace_label": s["find.replace_label"],
            "replace_prev": s["find.replace_prev"],
            "replace_next": s["find.replace_next"],
            "replace_all": s["find.replace_all"],
            "in_selection": s["find.in_selection"],
            "case_sensitive": s["find.case_sensitive"],
            "find_placeholder": s["find.find_placeholder"],
            "replace_placeholder": s["find.replace_placeholder"],
            "status.empty_search": s["find.status.empty_search"],
            "status.regex_error": s["find.status.regex_error"],
        }

    def _emit_search_preview(self) -> None:
        """Emit preview updates and surface regex errors immediately while typing."""
        self._status_label.setText("")
        term = self._find_input.text()
        use_regex = self._regex_check.isChecked()
        search_in_selection = self._selection_check.isChecked()
        case_sensitive = self._case_check.isChecked()
        if use_regex and term and not self._validate_regex(term):
            # Clear highlights when the regex is invalid to avoid stale matches.
            self.search_updated.emit("", False, search_in_selection, case_sensitive)
            return
        self.search_updated.emit(term, use_regex, search_in_selection, case_sensitive)

    def _on_find_text_changed(self) -> None:
        """Refresh match preview when query/options change."""
        self._emit_search_preview()

    def _on_find_next(self) -> None:
        term = self._find_input.text()
        if not term:
            self._status_label.setText(self._get_strings()["status.empty_search"])
            return
        use_regex = self._regex_check.isChecked()
        search_in_selection = self._selection_check.isChecked()
        case_sensitive = self._case_check.isChecked()
        if use_regex and not self._validate_regex(term):
            return
        self.find_next_requested.emit(term, use_regex, search_in_selection, case_sensitive)

    def _on_find_previous(self) -> None:
        term = self._find_input.text()
        if not term:
            self._status_label.setText(self._get_strings()["status.empty_search"])
            return
        use_regex = self._regex_check.isChecked()
        search_in_selection = self._selection_check.isChecked()
        case_sensitive = self._case_check.isChecked()
        if use_regex and not self._validate_regex(term):
            return
        self.find_previous_requested.emit(term, use_regex, search_in_selection, case_sensitive)

    def _on_replace_next(self) -> None:
        term = self._find_input.text()
        replacement = self._replace_input.text()
        if not term:
            self._status_label.setText(self._get_strings()["status.empty_search"])
            return
        use_regex = self._regex_check.isChecked()
        search_in_selection = self._selection_check.isChecked()
        case_sensitive = self._case_check.isChecked()
        if use_regex and not self._validate_regex(term):
            return
        self.replace_next_requested.emit(term, replacement, use_regex, search_in_selection, case_sensitive)

    def _on_replace_previous(self) -> None:
        term = self._find_input.text()
        replacement = self._replace_input.text()
        if not term:
            self._status_label.setText(self._get_strings()["status.empty_search"])
            return
        use_regex = self._regex_check.isChecked()
        search_in_selection = self._selection_check.isChecked()
        case_sensitive = self._case_check.isChecked()
        if use_regex and not self._validate_regex(term):
            return
        self.replace_previous_requested.emit(term, replacement, use_regex, search_in_selection, case_sensitive)

    def _on_replace_all(self) -> None:
        term = self._find_input.text()
        replacement = self._replace_input.text()
        if not term:
            self._status_label.setText(self._get_strings()["status.empty_search"])
            return
        use_regex = self._regex_check.isChecked()
        search_in_selection = self._selection_check.isChecked()
        case_sensitive = self._case_check.isChecked()
        if use_regex and not self._validate_regex(term):
            return
        self.replace_all_requested.emit(term, replacement, use_regex, search_in_selection, case_sensitive)

    def _validate_regex(self, pattern: str) -> bool:
        """Validate regex pattern and show error if invalid."""
        try:
            re.compile(pattern)
            return True
        except re.error as e:
            self._status_label.setText(
                self._get_strings()["status.regex_error"].format(error=str(e))
            )
            return False

    def set_status(self, message: str) -> None:
        """Update status label."""
        self._status_label.setText(message)

    def keyPressEvent(self, event) -> None:
        """Handle Escape to close dialog."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        """Refresh match highlights and focus find input whenever dialog becomes visible."""
        super().showEvent(event)
        self._find_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self._find_input.selectAll()
        self._emit_search_preview()

    def closeEvent(self, event) -> None:
        self.dialog_closed.emit()
        super().closeEvent(event)
