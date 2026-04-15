"""Floating warnings dialog with clickable line navigation."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity

_SEVERITY_ICON: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "✕",
    WarningSeverity.WARNING: "▲",
    WarningSeverity.INFO: "ℹ",
}


class WarningsDialog(QDialog):
    """Floating list of warnings that can jump to source lines."""

    line_selected = pyqtSignal(int)

    def __init__(self, parent=None, language: str = "de") -> None:
        super().__init__(parent)
        self._language = language
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(460)
        self.setMinimumHeight(280)

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)
        self._apply_language()

    def set_language(self, language: str) -> None:
        self._language = language
        self._apply_language()

    def set_warnings(self, warnings: list[AnalysisWarning]) -> None:
        self._list.clear()
        for warning in warnings:
            icon = _SEVERITY_ICON[warning.severity]
            line_number = warning.line_number
            if line_number is None:
                text = f"{icon} {warning.message}"
            else:
                if self._language == "de":
                    text = f"{icon} Zeile {line_number}: {warning.message}"
                else:
                    text = f"{icon} Line {line_number}: {warning.message}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, line_number)
            self._list.addItem(item)

    def _apply_language(self) -> None:
        if self._language == "de":
            self.setWindowTitle("Meldungen")
        else:
            self.setWindowTitle("Messages")

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        line_number = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(line_number, int):
            self.line_selected.emit(line_number)
