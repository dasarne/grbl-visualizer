"""Settings dialog for GRBL version selection."""

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..gcode.grbl_versions import GRBL_VERSIONS, DEFAULT_VERSION, get_version


class SettingsDialog(QDialog):
    """Dialog for selecting the active GRBL version and reviewing its feature set."""

    def __init__(self, parent=None, current_version: str = DEFAULT_VERSION) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._current_version = current_version
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the settings layout."""
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._version_combo = QComboBox()
        self._version_combo.addItems(GRBL_VERSIONS)
        self._version_combo.setCurrentText(self._current_version)
        self._version_combo.currentTextChanged.connect(self._on_version_changed)
        form.addRow("GRBL Version:", self._version_combo)
        layout.addLayout(form)

        self._feature_table = QTableWidget(0, 2)
        self._feature_table.setHorizontalHeaderLabels(["Command", "Supported"])
        layout.addWidget(self._feature_table)

        self._populate_feature_table(self._current_version)

    def get_selected_version(self) -> str:
        """Return the version currently selected in the combo box."""
        return self._version_combo.currentText()

    def _on_version_changed(self, version: str) -> None:
        """Refresh the feature table when the user picks a different version."""
        self._populate_feature_table(version)

    def _populate_feature_table(self, version_id: str) -> None:
        """Fill the feature table for the given GRBL version."""
        version = get_version(version_id)
        commands = sorted(version.supported_commands | version.unsupported_commands)
        self._feature_table.setRowCount(len(commands))
        for row, cmd in enumerate(commands):
            self._feature_table.setItem(row, 0, QTableWidgetItem(cmd))
            supported = "✅" if cmd in version.supported_commands else "❌"
            self._feature_table.setItem(row, 1, QTableWidgetItem(supported))
