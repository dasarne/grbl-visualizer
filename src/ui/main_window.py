"""Main application window for GCode Lisa."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolButton,
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence

from .editor_panel import EditorPanel
from .canvas_panel import CanvasPanel
from .comment_panel import CommentPanel
from .settings_dialog import SettingsDialog
from .about_dialog import AboutDialog
from .find_replace_dialog import FindReplaceDialog
from ..gcode.grbl_versions import DEFAULT_VERSION
from ..gcode.parser import GCodeParser
from ..analyzer.analyzer import GCodeAnalyzer, WarningSeverity
from ..geometry.path import build_toolpath


class MainWindow(QMainWindow):
    """Dual-view main window: G-Code editor + visualization canvas."""

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("dasarne", "GCodeLisa")
        self._language = self._settings.value("ui/language", "de", str)
        self._current_version = self._settings.value("grbl/version", DEFAULT_VERSION, str)
        self._recent_files: list[str] = list(
            self._settings.value("recent/files", [], list) or []
        )
        self._max_recent_files = 8

        self.setWindowTitle("GCode Lisa")
        self.resize(1200, 800)

        self._editor_panel = EditorPanel()
        self._comment_panel = CommentPanel()
        self._canvas_panel = CanvasPanel()
        self._loaded_content: str = ""
        self._loaded_path: str | None = None
        self._is_dirty = False
        self._find_replace_dialog: FindReplaceDialog | None = None
        self._issues_total = 0
        self._issues_errors = 0
        self._issues_warnings = 0

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._connect_signals()
        self._apply_language()

    def _setup_ui(self) -> None:
        """Build the central three-pane splitter layout."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._comment_panel)
        splitter.addWidget(self._editor_panel)
        splitter.addWidget(self._canvas_panel)
        splitter.setSizes([220, 480, 700])
        self.setCentralWidget(splitter)

    def _setup_menu(self) -> None:
        """Create the application menu bar."""
        menu_bar = self.menuBar()

        self._file_menu = menu_bar.addMenu("")
        self._new_action = QAction("", self)
        self._new_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_action.triggered.connect(self.new_file)
        self._file_menu.addAction(self._new_action)

        self._open_action = QAction("", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self.open_file)
        self._file_menu.addAction(self._open_action)

        self._save_action = QAction("", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self.save_file)
        self._file_menu.addAction(self._save_action)

        self._save_as_action = QAction("", self)
        self._save_as_action.triggered.connect(self.save_file_as)
        self._file_menu.addAction(self._save_as_action)

        self._file_menu.addSeparator()

        self._settings_action = QAction("", self)
        self._settings_action.triggered.connect(self.open_settings)
        self._file_menu.addAction(self._settings_action)

        self._about_action = QAction("", self)
        self._about_action.triggered.connect(self.open_about)
        self._file_menu.addAction(self._about_action)

        self._recent_separator = self._file_menu.addSeparator()
        self._recent_actions: list[QAction] = []
        self._refresh_recent_menu()

        self._file_menu.addSeparator()

        self._exit_action = QAction("", self)
        self._exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self._exit_action.triggered.connect(self.close)
        self._file_menu.addAction(self._exit_action)

        self._edit_menu = menu_bar.addMenu("")
        self._undo_action = QAction("", self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._editor_panel.undo)
        self._edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("", self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._editor_panel.redo)
        self._edit_menu.addAction(self._redo_action)

        self._edit_menu.addSeparator()

        self._copy_action = QAction("", self)
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self._copy_action.triggered.connect(self._editor_panel.copy)
        self._edit_menu.addAction(self._copy_action)

        self._paste_action = QAction("", self)
        self._paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self._paste_action.triggered.connect(self._editor_panel.paste)
        self._edit_menu.addAction(self._paste_action)

        self._edit_menu.addSeparator()

        self._find_action = QAction("", self)
        self._find_action.setShortcut(QKeySequence.StandardKey.Find)
        self._find_action.triggered.connect(self._on_find_replace)
        self._edit_menu.addAction(self._find_action)

        self._replace_action = QAction("", self)
        self._replace_action.setShortcut(QKeySequence("Ctrl+H"))
        self._replace_action.triggered.connect(self._on_find_replace)
        self._edit_menu.addAction(self._replace_action)

        self._messages_action = QAction("", self)
        self._messages_action.setShortcut(QKeySequence("Ctrl+I"))
        self._messages_action.triggered.connect(self._canvas_panel.show_warning_dialog)
        self._edit_menu.addAction(self._messages_action)

    def _setup_statusbar(self) -> None:
        """Initialise the status bar."""
        self._issues_button = QToolButton(self)
        self._issues_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._issues_button.clicked.connect(self._canvas_panel.show_warning_dialog)
        self._issues_button.hide()
        self.statusBar().addPermanentWidget(self._issues_button)
        self.statusBar().showMessage(self._tr("status.ready"))

    def _connect_signals(self) -> None:
        """Wire editor ↔ comment panel ↔ canvas bidirectional signals."""
        self._editor_panel.line_selected.connect(self._on_editor_line_selected)
        self._editor_panel.line_selected.connect(self._comment_panel.set_current_line)
        self._editor_panel.content_changed.connect(self._on_editor_content_changed)
        self._comment_panel.comment_selected.connect(self._editor_panel.highlight_line)
        self._comment_panel.comment_selected.connect(self._canvas_panel.highlight_segment)
        self._canvas_panel.segment_selected.connect(self._on_canvas_segment_selected)
        self._canvas_panel.segment_selected.connect(self._comment_panel.set_current_line)
        self._canvas_panel.warning_selected.connect(self._editor_panel.highlight_line)
        self._canvas_panel.warning_selected.connect(self._canvas_panel.highlight_segment)
        self._canvas_panel.warning_selected.connect(self._comment_panel.set_current_line)

    def open_file(self) -> None:
        """Open a G-Code file, parse it, analyse it, and display warnings."""
        if not self._maybe_save_before_destructive_action():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._tr("file.open_title"),
            "",
            "G-Code Files (*.gcode *.nc *.ngc *.tap);;All Files (*)",
        )
        if path:
            self._open_file_path(path)

    def new_file(self) -> None:
        """Clear editor for a new G-Code document."""
        if not self._maybe_save_before_destructive_action():
            return
        self._loaded_path = None
        self._loaded_content = ""
        self._load_content("")
        self._set_dirty(False)
        self._update_window_title()

    def save_file(self) -> bool:
        """Save the currently loaded G-Code to a file chosen by the user."""
        if not self._loaded_content:
            QMessageBox.information(
                self,
                self._tr("file.save"),
                self._tr("file.save_nothing"),
            )
            return False

        if self._loaded_path is None:
            return self.save_file_as()

        with open(self._loaded_path, "w", encoding="utf-8") as fh:
            fh.write(self._loaded_content)
        self._set_dirty(False)
        self.statusBar().showMessage(self._tr("status.saved").format(path=self._loaded_path))
        return True

    def save_file_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self,
            self._tr("file.save_title"),
            self._loaded_path or "",
            "G-Code Files (*.gcode *.nc *.ngc *.tap);;All Files (*)",
        )
        if not path:
            return False

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self._loaded_content)

        self._loaded_path = path
        self._add_recent_file(path)
        self._set_dirty(False)
        self.statusBar().showMessage(self._tr("status.saved").format(path=path))
        return True

    def open_settings(self) -> None:
        """Open application settings dialog."""
        dialog = SettingsDialog(
            parent=self,
            current_version=self._current_version,
            current_language=self._language,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self._current_version = dialog.get_selected_version()
        self._language = dialog.get_selected_language()
        self._settings.setValue("grbl/version", self._current_version)
        self._settings.setValue("ui/language", self._language)

        if self._find_replace_dialog is not None:
            self._find_replace_dialog.set_language(self._language)

        if self._loaded_content:
            self._load_content(
                self._loaded_content,
                label=self._loaded_path or "",
                reparse=True,
            )
        self._apply_language()

    def open_about(self) -> None:
        """Open about dialog."""
        dialog = AboutDialog(parent=self, language=self._language)
        dialog.exec()

    def _open_file_path(self, path: str) -> None:
        if not self._maybe_save_before_destructive_action():
            return
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        self._loaded_path = path
        self._add_recent_file(path)
        self._load_content(content, label=path)
        self._set_dirty(False)

    def _load_content(self, content: str, label: str = "", reparse: bool = False) -> None:
        """Parse content, run analysis, and update all UI panels."""
        self._loaded_content = content
        if not reparse:
            self._editor_panel.load_content(content)

        parser = GCodeParser(version_id=self._current_version)
        try:
            program = parser.parse_text(content)
            analyzer = GCodeAnalyzer(version_id=self._current_version)
            warnings = analyzer.analyze(program)
        except Exception as exc:
            warnings = []
            program = parser.parse_text("")
            self.statusBar().showMessage(self._tr("status.parse_error").format(msg=str(exc)))

        self._editor_panel.mark_warning_lines(warnings)
        self._canvas_panel.show_warnings(warnings)

        toolpath = build_toolpath(program)
        self._canvas_panel.render_toolpath(toolpath)

        # Populate the comment strip with every line that carries a comment.
        comments = [
            (line.line_number, line.comment)
            for line in program.lines
            if line.comment
        ]
        self._comment_panel.load_comments(comments)

        error_count = sum(1 for w in warnings if w.severity == WarningSeverity.ERROR)
        warning_count = sum(1 for w in warnings if w.severity == WarningSeverity.WARNING)
        issue_count = error_count + warning_count
        self._update_issues_button(issue_count, error_count, warning_count)

        parts: list[str] = []
        if label and not self._is_dirty:
            parts.append(self._tr("status.loaded").format(path=label))
        if not issue_count:
            parts.append(self._tr("status.no_issues"))

        self.statusBar().showMessage("  |  ".join(parts))
        self._canvas_panel.set_language(self._language)
        self._comment_panel.set_language(self._language)

    def _on_editor_content_changed(self, content: str) -> None:
        self._loaded_content = content
        self._set_dirty(True)
        self._load_content(content, label=self._loaded_path or self._tr("title.untitled"), reparse=True)

    def _on_version_changed(self, version_id: str) -> None:
        """Re-run analysis when the GRBL version selector changes."""
        self._current_version = version_id

    def _on_editor_line_selected(self, line_number: int) -> None:
        """Highlight the canvas segment corresponding to the selected editor line."""
        self._canvas_panel.highlight_segment(line_number)

    def _on_canvas_segment_selected(self, line_number: int) -> None:
        """Scroll the editor to the line corresponding to the selected canvas segment."""
        self._editor_panel.highlight_line(line_number)

    def _on_find_replace(self) -> None:
        """Open the floating Find and Replace dialog."""
        if self._find_replace_dialog is None:
            self._find_replace_dialog = FindReplaceDialog(
                parent=self,
                language=self._language,
            )
            self._find_replace_dialog.find_next_requested.connect(self._on_find_next_requested)
            self._find_replace_dialog.find_previous_requested.connect(self._on_find_previous_requested)
            self._find_replace_dialog.replace_next_requested.connect(self._on_replace_next_requested)
            self._find_replace_dialog.replace_previous_requested.connect(self._on_replace_previous_requested)
            self._find_replace_dialog.replace_all_requested.connect(self._on_replace_all_requested)
            self._find_replace_dialog.search_updated.connect(self._on_search_updated)
            self._find_replace_dialog.dialog_closed.connect(self._on_find_replace_closed)
        self._find_replace_dialog.show()
        self._find_replace_dialog.raise_()
        self._find_replace_dialog.activateWindow()

    def _on_find_replace_closed(self) -> None:
        self._editor_panel.clear_search_highlights()

    def _on_search_updated(self, term: str, use_regex: bool, search_in_selection: bool) -> None:
        found, count = self._editor_panel.preview_search(term, use_regex, search_in_selection)
        if not term:
            self._find_replace_dialog.set_status("")
        elif found:
            self._find_replace_dialog.set_status(self._tr("status.search_matches").format(count=count))
        else:
            self._find_replace_dialog.set_status(self._tr("status.search_not_found").format(term=term))

    def _on_find_next_requested(self, term: str, use_regex: bool, search_in_selection: bool) -> None:
        if self._editor_panel.find_next(term, use_regex, search_in_selection):
            self._find_replace_dialog.set_status(f"Found: {term}")
        else:
            self._find_replace_dialog.set_status(f"Not found: {term}")

    def _on_find_previous_requested(self, term: str, use_regex: bool, search_in_selection: bool) -> None:
        if self._editor_panel.find_previous(term, use_regex, search_in_selection):
            self._find_replace_dialog.set_status(f"Found: {term}")
        else:
            self._find_replace_dialog.set_status(f"Not found: {term}")

    def _on_replace_next_requested(self, needle: str, replacement: str, use_regex: bool, search_in_selection: bool) -> None:
        if self._editor_panel.replace_next(needle, replacement, use_regex, search_in_selection):
            self._find_replace_dialog.set_status(f"Replaced: {needle}")
            self._loaded_content = self._editor_panel.get_content()
            self._set_dirty(True)
            self._load_content(
                self._loaded_content,
                label=self._loaded_path or self._tr("title.untitled"),
                reparse=True,
            )
        else:
            self._find_replace_dialog.set_status(f"Not found: {needle}")

    def _on_replace_previous_requested(self, needle: str, replacement: str, use_regex: bool, search_in_selection: bool) -> None:
        if self._editor_panel.replace_previous(needle, replacement, use_regex, search_in_selection):
            self._find_replace_dialog.set_status(f"Replaced: {needle}")
            self._loaded_content = self._editor_panel.get_content()
            self._set_dirty(True)
            self._load_content(
                self._loaded_content,
                label=self._loaded_path or self._tr("title.untitled"),
                reparse=True,
            )
        else:
            self._find_replace_dialog.set_status(f"Not found: {needle}")

    def _on_replace_all_requested(self, needle: str, replacement: str, use_regex: bool, search_in_selection: bool) -> None:
        count = self._editor_panel.replace_all(needle, replacement, use_regex, search_in_selection)
        if count > 0:
            self._find_replace_dialog.set_status(f"Replaced {count} occurrence(s)")
            self._loaded_content = self._editor_panel.get_content()
            self._set_dirty(True)
            self._load_content(
                self._loaded_content,
                label=self._loaded_path or self._tr("title.untitled"),
                reparse=True,
            )
        else:
            self._find_replace_dialog.set_status(f"Not found: {needle}")

    def _refresh_recent_menu(self) -> None:
        for action in self._recent_actions:
            self._file_menu.removeAction(action)
        self._recent_actions.clear()

        has_recent = bool(self._recent_files)
        self._recent_separator.setVisible(has_recent)
        if not has_recent:
            return

        for path in self._recent_files[: self._max_recent_files]:
            action = QAction(path, self)
            action.triggered.connect(lambda _checked=False, p=path: self._open_file_path(p))
            self._file_menu.insertAction(self._recent_separator, action)
            self._recent_actions.append(action)

    def _add_recent_file(self, path: str) -> None:
        normalized = str(Path(path))
        self._recent_files = [p for p in self._recent_files if p != normalized]
        self._recent_files.insert(0, normalized)
        self._recent_files = self._recent_files[: self._max_recent_files]
        self._settings.setValue("recent/files", self._recent_files)
        self._refresh_recent_menu()

    def _apply_language(self) -> None:
        self._file_menu.setTitle(self._tr("menu.file"))
        self._edit_menu.setTitle(self._tr("menu.edit"))
        self._new_action.setText(self._tr("file.new"))
        self._open_action.setText(self._tr("file.open"))
        self._save_action.setText(self._tr("file.save"))
        self._save_as_action.setText(self._tr("file.save_as"))
        self._settings_action.setText(self._tr("file.settings"))
        self._about_action.setText(self._tr("file.about"))
        self._exit_action.setText(self._tr("file.quit"))
        self._undo_action.setText(self._tr("edit.undo"))
        self._redo_action.setText(self._tr("edit.redo"))
        self._copy_action.setText(self._tr("edit.copy"))
        self._paste_action.setText(self._tr("edit.paste"))
        self._find_action.setText(self._tr("edit.find"))
        self._replace_action.setText(self._tr("edit.replace"))
        self._messages_action.setText(self._tr("edit.messages"))
        self._update_issues_button(self._issues_total, self._issues_errors, self._issues_warnings)
        self._update_window_title()
        self._canvas_panel.set_language(self._language)
        self._comment_panel.set_language(self._language)

    def _update_issues_button(self, total: int, errors: int, warnings: int) -> None:
        self._issues_total = total
        self._issues_errors = errors
        self._issues_warnings = warnings
        if total <= 0:
            self._issues_button.hide()
            return
        self._issues_button.show()
        self._issues_button.setText(
            self._tr("status.issues_button").format(
                total=total,
                errors=errors,
                warnings=warnings,
            )
        )

    def _update_window_title(self) -> None:
        base = self._tr("title.untitled")
        if self._loaded_path:
            base = Path(self._loaded_path).name
        dirty = "*" if self._is_dirty else ""
        self.setWindowTitle(f"{base}{dirty} - {self._tr('app.title')}")

    def _set_dirty(self, dirty: bool) -> None:
        self._is_dirty = dirty
        self._editor_panel.set_modified(dirty)
        self._update_window_title()

    def _maybe_save_before_destructive_action(self) -> bool:
        if not self._is_dirty:
            return True
        answer = QMessageBox.question(
            self,
            self._tr("confirm.unsaved_title"),
            self._tr("confirm.unsaved_message"),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save_file()
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return False

    def closeEvent(self, event) -> None:
        if self._maybe_save_before_destructive_action():
            event.accept()
        else:
            event.ignore()

    def _tr(self, key: str) -> str:
        de = {
            "app.title": "GCode Lisa",
            "menu.file": "&Datei",
            "menu.edit": "&Bearbeiten",
            "file.new": "&Neu",
            "file.open": "&Oeffnen...",
            "file.save": "&Speichern",
            "file.save_as": "Speichern &unter...",
            "file.settings": "&Einstellungen",
            "file.about": "&Info",
            "file.quit": "&Beenden",
            "file.open_title": "G-Code-Datei oeffnen",
            "file.save_title": "G-Code-Datei speichern",
            "file.save_nothing": "Keine geladene G-Code-Datei zum Speichern.",
            "status.ready": "Bereit",
            "status.saved": "Gespeichert: {path}",
            "status.loaded": "Geladen: {path}",
            "status.errors": "{count} Fehler",
            "status.warnings": "{count} Warnungen",
            "status.no_issues": "Keine Probleme gefunden",
            "status.issues_button": "Meldungen/Fehler: {total} (E:{errors}, W:{warnings})",
            "status.parse_error": "Parserfehler: {msg}",
            "status.replaced": "{count} Treffer ersetzt",
            "status.search_matches": "{count} Treffer",
            "status.search_not_found": "Nicht gefunden: {term}",
            "edit.undo": "&Rueckgaengig",
            "edit.redo": "&Wiederherstellen",
            "edit.copy": "&Kopieren",
            "edit.paste": "&Einfuegen",
            "edit.find": "&Suchen",
            "edit.replace": "&Ersetzen",
            "edit.messages": "&Meldungen",
            "edit.find_prompt": "Suchbegriff:",
            "edit.find_not_found": "Kein Treffer gefunden.",
            "edit.replace_find": "Suche:",
            "edit.replace_with": "Ersetzen durch:",
            "title.untitled": "Unbenannt",
            "confirm.unsaved_title": "Ungespeicherte Aenderungen",
            "confirm.unsaved_message": "Die Datei wurde geaendert. Vor dem Fortfahren speichern?",
        }
        en = {
            "app.title": "GCode Lisa",
            "menu.file": "&File",
            "menu.edit": "&Edit",
            "file.new": "&New",
            "file.open": "&Open...",
            "file.save": "&Save",
            "file.save_as": "Save &As...",
            "file.settings": "&Settings",
            "file.about": "&Info",
            "file.quit": "&Quit",
            "file.open_title": "Open G-Code File",
            "file.save_title": "Save G-Code File",
            "file.save_nothing": "No G-Code loaded to save.",
            "status.ready": "Ready",
            "status.saved": "Saved: {path}",
            "status.loaded": "Loaded: {path}",
            "status.errors": "{count} error(s)",
            "status.warnings": "{count} warning(s)",
            "status.no_issues": "No issues found",
            "status.issues_button": "Messages/Errors: {total} (E:{errors}, W:{warnings})",
            "status.parse_error": "Parse error: {msg}",
            "status.replaced": "Replaced {count} occurrence(s)",
            "status.search_matches": "{count} match(es)",
            "status.search_not_found": "Not found: {term}",
            "edit.undo": "&Undo",
            "edit.redo": "&Redo",
            "edit.copy": "&Copy",
            "edit.paste": "&Paste",
            "edit.find": "&Find",
            "edit.replace": "&Replace",
            "edit.messages": "&Messages",
            "edit.find_prompt": "Find:",
            "edit.find_not_found": "No match found.",
            "edit.replace_find": "Find:",
            "edit.replace_with": "Replace with:",
            "title.untitled": "Untitled",
            "confirm.unsaved_title": "Unsaved changes",
            "confirm.unsaved_message": "The file has unsaved changes. Save before continuing?",
        }
        return (de if self._language == "de" else en).get(key, key)
