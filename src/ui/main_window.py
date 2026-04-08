"""Main application window for GRBL Visualizer."""

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QToolBar,
    QWidget,
)
from PyQt6.QtCore import Qt

from .editor_panel import EditorPanel
from .canvas_panel import CanvasPanel
from ..gcode.grbl_versions import GRBL_VERSIONS, DEFAULT_VERSION


class MainWindow(QMainWindow):
    """Dual-view main window: G-Code editor + visualization canvas."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GRBL Visualizer")
        self.resize(1200, 800)

        self._editor_panel = EditorPanel()
        self._canvas_panel = CanvasPanel()
        self._current_version = DEFAULT_VERSION

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Build the central splitter layout."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._editor_panel)
        splitter.addWidget(self._canvas_panel)
        splitter.setSizes([500, 700])
        self.setCentralWidget(splitter)

    def _setup_menu(self) -> None:
        """Create the application menu bar."""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction("&Open…", self.open_file)
        file_menu.addAction("&Save")
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)

        menu_bar.addMenu("&View")
        menu_bar.addMenu("&Help")

    def _setup_toolbar(self) -> None:
        """Create the main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.addAction("Open File", self.open_file)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("GRBL Version: "))

        from .widgets import GRBLVersionSelector
        self._version_selector = GRBLVersionSelector()
        self._version_selector.setCurrentText(self._current_version)
        toolbar.addWidget(self._version_selector)

    def _setup_statusbar(self) -> None:
        """Initialise the status bar."""
        self.statusBar().showMessage("Ready")

    def _connect_signals(self) -> None:
        """Wire editor ↔ canvas bidirectional signals."""
        self._editor_panel.line_selected.connect(self._on_editor_line_selected)
        self._canvas_panel.segment_selected.connect(self._on_canvas_segment_selected)

    def open_file(self) -> None:
        """Open a G-Code file via a file dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open G-Code File",
            "",
            "G-Code Files (*.gcode *.nc *.ngc *.tap);;All Files (*)",
        )
        if path:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            self._editor_panel.load_content(content)
            self.statusBar().showMessage(f"Loaded: {path}")

    def _on_editor_line_selected(self, line_number: int) -> None:
        """Highlight the canvas segment corresponding to the selected editor line.

        TODO: Retrieve toolpath and call canvas highlight.
        """
        self._canvas_panel.highlight_segment(line_number)

    def _on_canvas_segment_selected(self, line_number: int) -> None:
        """Scroll the editor to the line corresponding to the selected canvas segment.

        TODO: Map segment back to line number and call editor highlight.
        """
        self._editor_panel.highlight_line(line_number)
