"""Main application window for GCode Lisa."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QLabel,
    QComboBox,
    QSplitter,
    QToolButton,
)
from PyQt6.QtCore import Qt, QSettings, QProcess
from PyQt6.QtGui import QAction, QKeySequence, QCursor
from .resources import get_string

from .editor_panel import EditorPanel
from .canvas_panel import CanvasPanel
from .comment_panel import CommentPanel
from .settings_dialog import SettingsDialog
from .about_dialog import AboutDialog
from .find_replace_dialog import FindReplaceDialog
from .navigation_service import NAV_STYLE_CAD
from ..gcode.grbl_versions import DEFAULT_VERSION
from ..gcode.dialects import get_profile, list_profiles
from ..gcode.parser import GCodeParser
from ..gcode.detection import DetectionResult, detect_dialect
from ..analyzer.analyzer import GCodeAnalyzer, WarningSeverity
from ..geometry.path import build_toolpath


class MainWindow(QMainWindow):
    """Dual-view main window: G-Code editor + visualization canvas."""

    _DIALECT_PROFILE_KEY = "dialect/profile"
    _LEGACY_GRBL_VERSION_KEY = "grbl/version"
    _AUTO_PROFILE_ID = "__auto__"

    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings("dasarne", "GCodeLisa")
        self._language = self._settings.value("ui/language", "de", str)
        self._current_version = self._settings.value(
            self._DIALECT_PROFILE_KEY,
            self._settings.value(self._LEGACY_GRBL_VERSION_KEY, DEFAULT_VERSION, str),
            str,
        )
        self._auto_detect_profile = self._settings.value("dialect/auto_detect", False, bool)
        self._mouse_nav_style = self._settings.value("ui/mouse_navigation", NAV_STYLE_CAD, str)
        self._recent_files: list[str] = list(
            self._settings.value("recent/files", [], list) or []
        )
        self._max_recent_files = 8

        self.setWindowTitle("GCode Lisa")
        self.resize(1200, 800)

        self._editor_panel = EditorPanel()
        self._comment_panel = CommentPanel()
        self._canvas_panel = CanvasPanel()
        self._canvas_panel.set_navigation_style(self._mouse_nav_style)
        self._loaded_content: str = ""
        self._loaded_path: str | None = None
        self._is_dirty = False
        self._find_replace_dialog: FindReplaceDialog | None = None
        self._issues_total = 0
        self._issues_errors = 0
        self._issues_warnings = 0
        self._issues_infos = 0
        self._detected_dialect: DetectionResult | None = None
        self._effective_profile_id: str = self._current_version
        self._status_dialect_label: QLabel | None = None
        self._status_profile_label: QLabel | None = None
        self._status_profile_combo: QComboBox | None = None
        self._issues_button: QToolButton | None = None
        self._syncing_profile_combo = False

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

        # --- Datei-Menü ---
        self._file_menu = menu_bar.addMenu("")

        self._new_action = QAction("", self)
        self._new_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_action.triggered.connect(self.new_file)
        self._file_menu.addAction(self._new_action)

        self._open_action = QAction("", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self.open_file)
        self._file_menu.addAction(self._open_action)

        # Untermenü "Letzte Dateien" direkt unter Öffnen
        self._recent_menu = self._file_menu.addMenu("")
        self._refresh_recent_menu()

        self._file_menu.addSeparator()

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

        self._file_menu.addSeparator()

        self._exit_action = QAction("", self)
        self._exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self._exit_action.triggered.connect(self.close)
        self._file_menu.addAction(self._exit_action)

        # --- Bearbeiten-Menü ---
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

        # --- Info-Menü (neben Bearbeiten) ---
        self._info_menu = menu_bar.addMenu("")

        self._about_action = QAction("", self)
        self._about_action.triggered.connect(self.open_about)
        self._info_menu.addAction(self._about_action)

    def _setup_statusbar(self) -> None:
        """Initialise the status bar."""
        self._issues_button = QToolButton(self)
        self._issues_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._issues_button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._issues_button.setToolTip(self._tr("status.issues_tooltip"))
        self._issues_button.clicked.connect(self._canvas_panel.show_warning_dialog)
        self._issues_button.hide()
        self.statusBar().addPermanentWidget(self._issues_button)

        self._status_dialect_label = QLabel(self)
        self.statusBar().addPermanentWidget(self._status_dialect_label)

        self._status_profile_label = QLabel(self)
        self._status_profile_combo = QComboBox(self)
        self._status_profile_combo.currentIndexChanged.connect(self._on_status_profile_selection_changed)
        self._refresh_status_profile_combo()
        self.statusBar().addPermanentWidget(self._status_profile_label)
        self.statusBar().addPermanentWidget(self._status_profile_combo)
        self.statusBar().showMessage(self._tr("status.ready"))

    def _connect_signals(self) -> None:
        """Wire editor ↔ comment panel ↔ canvas bidirectional signals."""
        # line_selected (single int): only drives the comment-strip cursor
        self._editor_panel.line_selected.connect(self._comment_panel.set_current_line)
        # lines_selected (list[int]): drives canvas multi-highlight
        self._editor_panel.lines_selected.connect(self._on_editor_lines_selected)
        self._editor_panel.content_changed.connect(self._on_editor_content_changed)
        self._comment_panel.comment_selected.connect(self._editor_panel.highlight_line)
        self._comment_panel.comment_selected.connect(self._canvas_panel.highlight_segment)
        self._canvas_panel.segment_selected.connect(self._on_canvas_segment_selected)
        self._canvas_panel.segment_selected.connect(self._comment_panel.set_current_line)
        self._canvas_panel.warning_selected.connect(self._editor_panel.highlight_line)
        self._canvas_panel.warning_selected.connect(self._canvas_panel.highlight_segment)
        self._canvas_panel.warning_selected.connect(self._comment_panel.set_current_line)
        self._canvas_panel.segments_selected.connect(self._on_canvas_segments_selected)

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
        """Open a new application instance."""
        started = QProcess.startDetached(sys.executable, ["-m", "src.main"])
        if not started:
            QMessageBox.warning(
                self,
                self._tr("file.new"),
                self._tr("status.new_instance_failed"),
            )

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
            current_profile_id=self._current_version,
            current_auto_apply_detected_profile=self._auto_detect_profile,
            current_language=self._language,
            current_mouse_nav_style=self._mouse_nav_style,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self._current_version = dialog.get_selected_profile_id()
        self._auto_detect_profile = dialog.get_auto_apply_detected_profile()
        self._language = dialog.get_selected_language()
        self._mouse_nav_style = dialog.get_selected_mouse_nav_style()
        self._settings.setValue(self._DIALECT_PROFILE_KEY, self._current_version)
        self._settings.setValue("dialect/auto_detect", self._auto_detect_profile)
        self._settings.setValue("ui/language", self._language)
        self._settings.setValue("ui/mouse_navigation", self._mouse_nav_style)
        self._canvas_panel.set_navigation_style(self._mouse_nav_style)

        if self._find_replace_dialog is not None:
            self._find_replace_dialog.set_language(self._language)

        self._refresh_status_profile_combo()

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

        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except FileNotFoundError:
            # Remove stale recent-file entry and inform the user.
            self._recent_files = [p for p in self._recent_files if p != path]
            self._settings.setValue("recent/files", self._recent_files)
            self._refresh_recent_menu()
            msg = self._tr("file.open_missing").format(path=path)
            QMessageBox.warning(self, self._tr("file.open"), msg)
            self.statusBar().showMessage(msg)
            return
        except OSError as exc:
            msg = self._tr("file.open_failed").format(path=path, error=str(exc))
            QMessageBox.warning(self, self._tr("file.open"), msg)
            self.statusBar().showMessage(msg)
            return

        self._loaded_path = path
        self._add_recent_file(path)
        self._load_content(content, label=path)
        self._set_dirty(False)

    def _load_content(self, content: str, label: str = "", reparse: bool = False) -> None:
        """Parse content, run analysis, and update all UI panels."""
        self._loaded_content = content
        self._detected_dialect = detect_dialect(content)
        analysis_profile_id, auto_applied_profile = self._resolve_analysis_profile_id()
        self._effective_profile_id = analysis_profile_id
        if not reparse:
            self._editor_panel.load_content(content)

        parser = GCodeParser(version_id=analysis_profile_id)
        try:
            program = parser.parse_text(content)
            analyzer = GCodeAnalyzer(version_id=analysis_profile_id)
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
        info_count = sum(1 for w in warnings if w.severity == WarningSeverity.INFO)
        issue_count = error_count + warning_count + info_count
        message_count = len(warnings)
        self._update_issues_button(message_count, error_count, warning_count, info_count)

        self._update_detected_dialect_label()
        self.statusBar().showMessage(self._tr("status.no_issues") if issue_count == 0 else "")
        self._refresh_status_profile_combo()
        self._canvas_panel.set_language(self._language)
        self._comment_panel.set_language(self._language)
        self._editor_panel.set_language(self._language)
        self._editor_panel.set_profile_id(analysis_profile_id)

    def _on_editor_content_changed(self, content: str) -> None:
        self._loaded_content = content
        self._set_dirty(True)
        self._load_content(content, label=self._loaded_path or self._tr("title.untitled"), reparse=True)

    def _on_profile_changed(self, profile_id: str) -> None:
        """Re-run analysis when the profile selector changes."""
        self._current_version = profile_id

    def _resolve_analysis_profile_id(self) -> tuple[str, bool]:
        """Return active profile id and whether auto mode applied it."""
        if (
            self._auto_detect_profile
            and self._detected_dialect is not None
            and self._detected_dialect.profile_id is not None
        ):
            return self._detected_dialect.profile_id, True
        return self._current_version, False

    def _refresh_status_profile_combo(self) -> None:
        """Populate and sync the profile selector in the status bar."""
        if self._status_profile_combo is None or self._status_profile_label is None:
            return

        active_profile_id, auto_applied = self._resolve_analysis_profile_id()
        self._effective_profile_id = active_profile_id

        self._syncing_profile_combo = True
        try:
            self._status_profile_label.setText(self._tr("status.profile_active"))
            self._status_profile_combo.clear()
            self._status_profile_combo.addItem(self._tr("status.profile_auto_option"), self._AUTO_PROFILE_ID)
            for profile in list_profiles():
                self._status_profile_combo.addItem(profile.name, profile.profile_id)

            selected_data = self._AUTO_PROFILE_ID if self._auto_detect_profile else self._current_version
            index = self._status_profile_combo.findData(selected_data)
            if index < 0:
                index = self._status_profile_combo.findData(self._AUTO_PROFILE_ID)
            self._status_profile_combo.setCurrentIndex(index)

            if auto_applied:
                try:
                    detected_name = get_profile(active_profile_id).name
                except ValueError:
                    detected_name = active_profile_id
                self._status_profile_combo.setToolTip(
                    self._tr("status.profile_auto_tooltip").format(profile=detected_name)
                )
            else:
                self._status_profile_combo.setToolTip("")
        finally:
            self._syncing_profile_combo = False

    def _update_detected_dialect_label(self) -> None:
        """Show detected dialect as a fixed right-side status widget."""
        if self._status_dialect_label is None:
            return

        if self._detected_dialect is None or self._detected_dialect.dialect == "unknown":
            self._status_dialect_label.setText("")
            self._status_dialect_label.setToolTip("")
            return

        text = self._tr("status.dialect_detected").format(
            dialect=self._tr(f"dialect.{self._detected_dialect.dialect}"),
            confidence=round(self._detected_dialect.confidence * 100),
        )
        self._status_dialect_label.setText(text)
        self._status_dialect_label.setToolTip(text)

    def _on_status_profile_selection_changed(self, _index: int) -> None:
        """Handle direct profile selection from status bar combobox."""
        if self._syncing_profile_combo or self._status_profile_combo is None:
            return

        selected = self._status_profile_combo.currentData()
        if selected == self._AUTO_PROFILE_ID:
            self._auto_detect_profile = True
            self._settings.setValue("dialect/auto_detect", True)
        else:
            self._auto_detect_profile = False
            self._current_version = str(selected)
            self._settings.setValue("dialect/auto_detect", False)
            self._settings.setValue(self._DIALECT_PROFILE_KEY, self._current_version)

        if self._loaded_content:
            self._load_content(
                self._loaded_content,
                label=self._loaded_path or "",
                reparse=True,
            )

    def _on_version_changed(self, version_id: str) -> None:
        """Backward-compatible alias for profile change handler."""
        self._on_profile_changed(version_id)

    def _on_editor_line_selected(self, line_number: int) -> None:
        """Kept for compatibility – canvas routing now via lines_selected."""

    def _on_editor_lines_selected(self, line_numbers: list[int]) -> None:
        """Highlight canvas segments for all selected editor lines."""
        self._canvas_panel.highlight_segments(line_numbers)
        if len(line_numbers) == 1:
            self._comment_panel.set_current_line(line_numbers[0])
        elif len(line_numbers) > 1:
            self._comment_panel.set_current_line(None)

    def _on_canvas_segment_selected(self, line_number: int) -> None:
        """Scroll the editor to the line corresponding to the selected canvas segment."""
        self._editor_panel.highlight_line(line_number)

    def _on_canvas_segments_selected(self, line_numbers: list[int]) -> None:
        """Select the editor text range for a lasso / Shift multi-selection."""
        self._editor_panel.highlight_lines(line_numbers)
        if len(line_numbers) == 1:
            self._comment_panel.set_current_line(min(line_numbers))
        elif len(line_numbers) > 1:
            self._comment_panel.set_current_line(None)

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

    def _on_search_updated(self, term: str, use_regex: bool, search_in_selection: bool, case_sensitive: bool) -> None:
        found, count = self._editor_panel.preview_search(term, use_regex, search_in_selection, case_sensitive)
        if not term:
            self._find_replace_dialog.set_status("")
        elif found:
            self._find_replace_dialog.set_status(self._tr("status.search_matches").format(count=count))
        else:
            self._find_replace_dialog.set_status(self._tr("status.search_not_found").format(term=term))

    def _on_find_next_requested(self, term: str, use_regex: bool, search_in_selection: bool, case_sensitive: bool) -> None:
        if self._editor_panel.find_next(term, use_regex, search_in_selection, case_sensitive):
            count = self._editor_panel.get_search_match_count()
            self._find_replace_dialog.set_status(self._tr("status.search_matches").format(count=count))
        else:
            self._find_replace_dialog.set_status(self._tr("status.search_not_found").format(term=term))

    def _on_find_previous_requested(self, term: str, use_regex: bool, search_in_selection: bool, case_sensitive: bool) -> None:
        if self._editor_panel.find_previous(term, use_regex, search_in_selection, case_sensitive):
            count = self._editor_panel.get_search_match_count()
            self._find_replace_dialog.set_status(self._tr("status.search_matches").format(count=count))
        else:
            self._find_replace_dialog.set_status(self._tr("status.search_not_found").format(term=term))

    def _on_replace_next_requested(self, needle: str, replacement: str, use_regex: bool, search_in_selection: bool, case_sensitive: bool) -> None:
        if self._editor_panel.replace_next(needle, replacement, use_regex, search_in_selection, case_sensitive):
            self._find_replace_dialog.set_status(self._tr("status.replaced_one").format(term=needle))
            self._post_replace_refresh()
        else:
            self._find_replace_dialog.set_status(self._tr("status.search_not_found").format(term=needle))

    def _on_replace_previous_requested(self, needle: str, replacement: str, use_regex: bool, search_in_selection: bool, case_sensitive: bool) -> None:
        if self._editor_panel.replace_previous(needle, replacement, use_regex, search_in_selection, case_sensitive):
            self._find_replace_dialog.set_status(self._tr("status.replaced_one").format(term=needle))
            self._post_replace_refresh()
        else:
            self._find_replace_dialog.set_status(self._tr("status.search_not_found").format(term=needle))

    def _on_replace_all_requested(self, needle: str, replacement: str, use_regex: bool, search_in_selection: bool, case_sensitive: bool) -> None:
        count = self._editor_panel.replace_all(needle, replacement, use_regex, search_in_selection, case_sensitive)
        if count > 0:
            self._find_replace_dialog.set_status(self._tr("status.replaced").format(count=count))
            self._post_replace_refresh()
        else:
            self._find_replace_dialog.set_status(self._tr("status.search_not_found").format(term=needle))

    def _post_replace_refresh(self) -> None:
        """Refresh parsed panels and re-sync selection after replace operations."""
        self._loaded_content = self._editor_panel.get_content()
        self._set_dirty(True)
        self._load_content(
            self._loaded_content,
            label=self._loaded_path or self._tr("title.untitled"),
            reparse=True,
        )
        self._on_editor_lines_selected(self._editor_panel.get_selected_lines())

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        if not self._recent_files:
            empty = QAction(self._tr("file.recent_empty"), self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return
        for path in self._recent_files[: self._max_recent_files]:
            action = QAction(path, self)
            action.triggered.connect(lambda _checked=False, p=path: self._open_file_path(p))
            self._recent_menu.addAction(action)

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
        self._info_menu.setTitle(self._tr("menu.info"))
        self._recent_menu.setTitle(self._tr("file.recent"))
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
        self._update_issues_button(
            self._issues_total,
            self._issues_errors,
            self._issues_warnings,
            self._issues_infos,
        )
        self._update_detected_dialect_label()
        self._refresh_status_profile_combo()
        self._update_window_title()
        self._canvas_panel.set_language(self._language)
        self._comment_panel.set_language(self._language)
        self._editor_panel.set_language(self._language)

    def _update_issues_button(self, total: int, errors: int, warnings: int, infos: int) -> None:
        if self._issues_button is None:
            return

        self._issues_total = total
        self._issues_errors = errors
        self._issues_warnings = warnings
        self._issues_infos = infos
        if total <= 0:
            self._issues_button.hide()
            return

        self._issues_button.show()

        parts: list[str] = []
        if errors > 0:
            parts.append(f"Error:{errors}")
        if warnings > 0:
            parts.append(f"Warning:{warnings}")
        if infos > 0:
            parts.append(f"Info:{infos}")

        if not parts:
            self._issues_button.hide()
            return

        self._issues_button.setStyleSheet(
            "QToolButton {"
            " border: 1px solid #a9a9a9;"
            " border-radius: 4px;"
            " padding: 2px 6px;"
            " background: #f4f4f4;"
            "}"
            "QToolButton:hover { background: #ececec; }"
        )
        self._issues_button.setText(", ".join(parts))

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
        return get_string(self._language, key)
