"""Main entry point for the GCode Lisa application."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from .ui.main_window import MainWindow


def main() -> None:
    """Create and launch the GCode Lisa application."""
    app = QApplication(sys.argv)
    app.setApplicationName("GCode Lisa")
    app.setApplicationVersion("0.1.0")

    logo_path = Path(__file__).resolve().parents[1] / "assets" / "Lisa.svg"
    if logo_path.exists():
        icon = QIcon(str(logo_path))
        app.setWindowIcon(icon)

    window = MainWindow()
    if logo_path.exists():
        window.setWindowIcon(QIcon(str(logo_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
