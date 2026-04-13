"""Main entry point for the GRBL Visualizer application."""

import sys

from PyQt6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main() -> None:
    """Create and launch the GRBL Visualizer application."""
    app = QApplication(sys.argv)
    app.setApplicationName("GRBL Visualizer")
    app.setApplicationVersion("0.1.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
