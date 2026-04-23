"""Floating warnings dialog with clickable line navigation."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..analyzer.analyzer import AnalysisWarning, WarningSeverity


def _create_severity_icon(severity: WarningSeverity) -> QIcon:
    """Create a colored square icon for severity level."""
    color_map = {
        WarningSeverity.ERROR: "#FF6B6B",
        WarningSeverity.WARNING: "#FFB800",
        WarningSeverity.INFO: "#4A9EFF",
    }
    
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(color_map[severity]))
    return QIcon(pixmap)


_SEVERITY_ICON: dict[WarningSeverity, QIcon] = {
    WarningSeverity.ERROR: _create_severity_icon(WarningSeverity.ERROR),
    WarningSeverity.WARNING: _create_severity_icon(WarningSeverity.WARNING),
    WarningSeverity.INFO: _create_severity_icon(WarningSeverity.INFO),
}

_SEVERITY_LABEL: dict[WarningSeverity, str] = {
    WarningSeverity.ERROR: "Error",
    WarningSeverity.WARNING: "Warning",
    WarningSeverity.INFO: "Info",
}


class WarningsDialog(QDialog):
    """Floating warning table with sorting/filtering and line navigation."""

    line_selected = pyqtSignal(int)

    def __init__(self, parent=None, language: str = "de") -> None:
        super().__init__(parent)
        self._language = language
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setModal(False)
        self.setMinimumWidth(760)
        self.setMinimumHeight(340)
        self._warnings: list[AnalysisWarning] = []

        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        self._type_filter = QComboBox()
        self._type_filter.currentTextChanged.connect(self._apply_filters)
        self._text_filter = QLineEdit()
        self._text_filter.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self._type_filter)
        filter_row.addWidget(self._text_filter)
        layout.addLayout(filter_row)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Type", "Message", "Line"])
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        self._apply_language()

    def set_language(self, language: str) -> None:
        self._language = language
        self._apply_language()

    def set_warnings(self, warnings: list[AnalysisWarning]) -> None:
        self._warnings = list(warnings)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for warning in self._warnings:
            row = self._table.rowCount()
            self._table.insertRow(row)

            severity = warning.severity
            type_item = QTableWidgetItem()
            type_item.setIcon(_SEVERITY_ICON[severity])
            type_item.setText(_SEVERITY_LABEL[severity])
            type_item.setData(Qt.ItemDataRole.UserRole, severity.name)

            message_item = QTableWidgetItem(warning.message)
            message_item.setData(Qt.ItemDataRole.UserRole, warning.line_number)

            line_number = warning.line_number
            if line_number is None:
                line_item = QTableWidgetItem("-")
                line_item.setData(Qt.ItemDataRole.UserRole, -1)
            else:
                line_item = QTableWidgetItem(str(line_number))
                line_item.setData(Qt.ItemDataRole.UserRole, line_number)

            self._table.setItem(row, 0, type_item)
            self._table.setItem(row, 1, message_item)
            self._table.setItem(row, 2, line_item)

        self._table.setSortingEnabled(True)
        self._apply_filters()

    def _apply_language(self) -> None:
        if self._language == "de":
            self.setWindowTitle("Meldungen")
            self._type_filter.blockSignals(True)
            self._type_filter.clear()
            self._type_filter.addItems(["Alle", "Error", "Warning", "Info"])
            self._type_filter.blockSignals(False)
            self._text_filter.setPlaceholderText("Filter nach Meldungstext...")
        else:
            self.setWindowTitle("Messages")
            self._type_filter.blockSignals(True)
            self._type_filter.clear()
            self._type_filter.addItems(["All", "Error", "Warning", "Info"])
            self._type_filter.blockSignals(False)
            self._text_filter.setPlaceholderText("Filter by message text...")

    def _apply_filters(self) -> None:
        selected_type = self._type_filter.currentText().lower()
        query = self._text_filter.text().strip().lower()

        for row in range(self._table.rowCount()):
            type_item = self._table.item(row, 0)
            message_item = self._table.item(row, 1)
            if type_item is None or message_item is None:
                self._table.setRowHidden(row, True)
                continue

            severity_name = str(type_item.data(Qt.ItemDataRole.UserRole) or "").lower()
            message_text = message_item.text().lower()

            type_match = selected_type in {"all", "alle", ""} or severity_name == selected_type
            query_match = not query or query in message_text
            self._table.setRowHidden(row, not (type_match and query_match))

    def _on_selection_changed(self) -> None:
        selected = self._table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        line_item = self._table.item(row, 2)
        if line_item is None:
            return

        line_number = line_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(line_number, int):
            if line_number > 0:
                self.line_selected.emit(line_number)
