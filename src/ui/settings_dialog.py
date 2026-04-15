"""Settings dialog for GRBL dialect and UI language."""

from PyQt6.QtWidgets import (
    QDialogButtonBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..gcode.grbl_versions import GRBL_VERSIONS, DEFAULT_VERSION, get_version


class SettingsDialog(QDialog):
    """Dialog for selecting the active GRBL version and reviewing its feature set."""

    def __init__(
        self,
        parent=None,
        current_version: str = DEFAULT_VERSION,
        current_language: str = "de",
    ) -> None:
        super().__init__(parent)
        self._current_version = current_version
        self._current_language = current_language
        self._setup_ui()
        self._apply_language()

    def _setup_ui(self) -> None:
        """Build the settings layout."""
        layout = QVBoxLayout(self)
        self._form = QFormLayout()

        self._version_combo = QComboBox()
        self._version_combo.addItems(GRBL_VERSIONS)
        self._version_combo.setCurrentText(self._current_version)
        self._version_combo.currentTextChanged.connect(self._on_version_changed)

        self._language_combo = QComboBox()
        self._language_combo.addItem("Deutsch", "de")
        self._language_combo.addItem("English", "en")
        idx = self._language_combo.findData(self._current_language)
        self._language_combo.setCurrentIndex(max(0, idx))
        self._language_combo.currentIndexChanged.connect(self._apply_language)

        self._version_label = QLabel("")
        self._language_label = QLabel("")
        self._form.addRow(self._version_label, self._version_combo)
        self._form.addRow(self._language_label, self._language_combo)
        layout.addLayout(self._form)

        self._feature_table = QTableWidget(0, 2)
        layout.addWidget(self._feature_table)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._populate_feature_table(self._current_version)

    def get_selected_version(self) -> str:
        """Return the version currently selected in the combo box."""
        return self._version_combo.currentText()

    def get_selected_language(self) -> str:
        """Return selected UI language code ('de' or 'en')."""
        return self._language_combo.currentData()

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

    def _apply_language(self) -> None:
        lang = self._language_combo.currentData() or self._current_language
        de = {
            "title": "Einstellungen",
            "version": "GRBL-Dialekt:",
            "language": "Sprache:",
            "command": "Befehl",
            "supported": "Unterstuetzt",
            "ok": "OK",
            "cancel": "Abbrechen",
        }
        en = {
            "title": "Settings",
            "version": "GRBL dialect:",
            "language": "Language:",
            "command": "Command",
            "supported": "Supported",
            "ok": "OK",
            "cancel": "Cancel",
        }
        tr = de if lang == "de" else en

        self.setWindowTitle(tr["title"])
        self._version_label.setText(tr["version"])
        self._language_label.setText(tr["language"])
        self._feature_table.setHorizontalHeaderLabels([tr["command"], tr["supported"]])
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr["ok"])
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr["cancel"])
