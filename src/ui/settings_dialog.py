"""Settings dialog for GRBL dialect and UI language."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..gcode.grbl_versions import DEFAULT_VERSION
from ..gcode.dialects import get_profile, list_profiles
from .navigation_service import (
    NAV_STYLE_BLENDER,
    NAV_STYLE_CAD,
    NAV_STYLE_GESTURE,
    NAV_STYLE_LEGACY,
    NAV_STYLE_MAYA_GESTURE,
    NAV_STYLE_OPEN_CASCADE,
    NAV_STYLE_OPEN_INVENTOR,
    NAV_STYLE_OPEN_SCAD,
    NAV_STYLE_REVIT,
    NAV_STYLE_SIEMENS_NX,
    NAV_STYLE_SOLIDWORKS,
    NAV_STYLE_TINKERCAD,
    NAV_STYLE_TOUCHPAD,
)
from .resources import get_strings


class SettingsDialog(QDialog):
    """Dialog for selecting the active dialect profile and reviewing its commands."""

    def __init__(
        self,
        parent=None,
        current_version: str = DEFAULT_VERSION,
        current_auto_detect_dialect: bool = False,
        current_language: str = "de",
        current_mouse_nav_style: str = NAV_STYLE_CAD,
    ) -> None:
        super().__init__(parent)
        self._current_version = current_version
        self._current_auto_detect_dialect = current_auto_detect_dialect
        self._current_language = current_language
        self._current_mouse_nav_style = current_mouse_nav_style
        self._profiles = list_profiles()
        self._setup_ui()
        self._apply_language()

    def _setup_ui(self) -> None:
        """Build the settings layout."""
        layout = QVBoxLayout(self)
        self._form = QFormLayout()

        self._version_combo = QComboBox()
        for profile in self._profiles:
            self._version_combo.addItem(profile.name, profile.profile_id)
        idx = self._version_combo.findData(self._current_version)
        self._version_combo.setCurrentIndex(max(0, idx))
        self._version_combo.currentTextChanged.connect(self._on_version_changed)

        self._auto_detect_checkbox = QCheckBox()
        self._auto_detect_checkbox.setChecked(self._current_auto_detect_dialect)

        self._language_combo = QComboBox()
        self._language_combo.addItem("Deutsch", "de")
        self._language_combo.addItem("English", "en")
        idx = self._language_combo.findData(self._current_language)
        self._language_combo.setCurrentIndex(max(0, idx))
        self._language_combo.currentIndexChanged.connect(self._apply_language)

        self._mouse_nav_combo = QComboBox()
        self._mouse_nav_combo.addItem("", NAV_STYLE_CAD)
        self._mouse_nav_combo.addItem("", NAV_STYLE_BLENDER)
        self._mouse_nav_combo.addItem("", NAV_STYLE_GESTURE)
        self._mouse_nav_combo.addItem("", NAV_STYLE_MAYA_GESTURE)
        self._mouse_nav_combo.addItem("", NAV_STYLE_OPEN_CASCADE)
        self._mouse_nav_combo.addItem("", NAV_STYLE_OPEN_INVENTOR)
        self._mouse_nav_combo.addItem("", NAV_STYLE_OPEN_SCAD)
        self._mouse_nav_combo.addItem("", NAV_STYLE_REVIT)
        self._mouse_nav_combo.addItem("", NAV_STYLE_SIEMENS_NX)
        self._mouse_nav_combo.addItem("", NAV_STYLE_SOLIDWORKS)
        self._mouse_nav_combo.addItem("", NAV_STYLE_TINKERCAD)
        self._mouse_nav_combo.addItem("", NAV_STYLE_TOUCHPAD)
        self._mouse_nav_combo.addItem("", NAV_STYLE_LEGACY)
        idx = self._mouse_nav_combo.findData(self._current_mouse_nav_style)
        self._mouse_nav_combo.setCurrentIndex(max(0, idx))

        self._version_label = QLabel("")
        self._auto_detect_label = QLabel("")
        self._language_label = QLabel("")
        self._mouse_nav_label = QLabel("")
        self._form.addRow(self._version_label, self._version_combo)
        self._form.addRow(self._auto_detect_label, self._auto_detect_checkbox)
        self._form.addRow(self._language_label, self._language_combo)
        self._form.addRow(self._mouse_nav_label, self._mouse_nav_combo)
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
        return self._version_combo.currentData()

    def get_auto_detect_dialect(self) -> bool:
        """Return whether auto-detection should select profile on load."""
        return self._auto_detect_checkbox.isChecked()

    def get_selected_language(self) -> str:
        """Return selected UI language code ('de' or 'en')."""
        return self._language_combo.currentData()

    def get_selected_mouse_nav_style(self) -> str:
        """Return selected mouse navigation style id."""
        return self._mouse_nav_combo.currentData()

    def _on_version_changed(self, version: str) -> None:
        """Refresh the feature table when the user picks a different version."""
        self._populate_feature_table(self.get_selected_version())

    def _populate_feature_table(self, version_id: str) -> None:
        """Fill the feature table for the given GRBL version."""
        profile = get_profile(version_id)
        commands = sorted(profile.known_commands)
        self._feature_table.setRowCount(len(commands))
        for row, cmd in enumerate(commands):
            self._feature_table.setItem(row, 0, QTableWidgetItem(cmd))
            supported = "✅" if cmd in profile.supported_commands else "❌"
            self._feature_table.setItem(row, 1, QTableWidgetItem(supported))

    def _apply_language(self) -> None:
        lang = self._language_combo.currentData() or self._current_language
        s = get_strings(lang)
        self.setWindowTitle(s["settings.title"])
        self._version_label.setText(s["settings.version"])
        self._auto_detect_label.setText(s["settings.auto_detect"])
        self._language_label.setText(s["settings.language"])
        self._mouse_nav_label.setText(s["settings.mouse_navigation"])
        self._mouse_nav_combo.setItemText(0, s["settings.mouse_navigation.cad"])
        self._mouse_nav_combo.setItemText(1, s["settings.mouse_navigation.blender"])
        self._mouse_nav_combo.setItemText(2, s["settings.mouse_navigation.gesture"])
        self._mouse_nav_combo.setItemText(3, s["settings.mouse_navigation.maya_gesture"])
        self._mouse_nav_combo.setItemText(4, s["settings.mouse_navigation.open_cascade"])
        self._mouse_nav_combo.setItemText(5, s["settings.mouse_navigation.open_inventor"])
        self._mouse_nav_combo.setItemText(6, s["settings.mouse_navigation.open_scad"])
        self._mouse_nav_combo.setItemText(7, s["settings.mouse_navigation.revit"])
        self._mouse_nav_combo.setItemText(8, s["settings.mouse_navigation.siemens_nx"])
        self._mouse_nav_combo.setItemText(9, s["settings.mouse_navigation.solidworks"])
        self._mouse_nav_combo.setItemText(10, s["settings.mouse_navigation.tinkercad"])
        self._mouse_nav_combo.setItemText(11, s["settings.mouse_navigation.touchpad"])
        self._mouse_nav_combo.setItemText(12, s["settings.mouse_navigation.legacy"])
        self._feature_table.setHorizontalHeaderLabels(
            [s["settings.command"], s["settings.supported"]]
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(s["settings.ok"])
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(s["settings.cancel"])
