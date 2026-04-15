"""About dialog for GCode Lisa."""

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
	QDialog,
	QDialogButtonBox,
	QFrame,
	QGridLayout,
	QLabel,
	QTabWidget,
	QVBoxLayout,
	QWidget,
)


class AboutDialog(QDialog):
	"""Shows project information, contributors, license and privacy notes."""

	def __init__(self, parent=None, language: str = "de") -> None:
		super().__init__(parent)
		self._language = language
		self._build_ui()

	def _build_ui(self) -> None:
		t = self._tr_map()
		self.setWindowTitle(t["title"])
		self.resize(760, 520)

		root = QVBoxLayout(self)
		tabs = QTabWidget()
		root.addWidget(tabs, stretch=1)

		tabs.addTab(self._build_info_tab(t), t["tab.info"])
		tabs.addTab(self._build_text_tab(t["contributors.text"]), t["tab.contributors"])
		tabs.addTab(self._build_text_tab(t["license.text"]), t["tab.license"])
		tabs.addTab(self._build_text_tab(t["libraries.text"]), t["tab.libraries"])
		tabs.addTab(self._build_text_tab(t["privacy.text"]), t["tab.privacy"])

		buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
		buttons.accepted.connect(self.accept)
		root.addWidget(buttons)

	def _build_info_tab(self, t: dict[str, str]) -> QWidget:
		w = QWidget()
		layout = QVBoxLayout(w)

		card = QFrame()
		card.setFrameShape(QFrame.Shape.StyledPanel)
		card_layout = QVBoxLayout(card)

		logo = QLabel()
		logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
		logo_path = Path(__file__).resolve().parents[2] / "assets" / "Lisa.svg"
		pixmap = QPixmap(str(logo_path))
		if not pixmap.isNull():
			logo.setPixmap(
				pixmap.scaled(
					360,
					140,
					Qt.AspectRatioMode.KeepAspectRatio,
					Qt.TransformationMode.SmoothTransformation,
				)
			)
		card_layout.addWidget(logo)

		claim = QLabel("Cut with confidence.")
		claim.setAlignment(Qt.AlignmentFlag.AlignCenter)
		subclaim = QLabel("Waste less.")
		subclaim.setAlignment(Qt.AlignmentFlag.AlignCenter)
		claim.setStyleSheet("font-weight: bold; font-size: 15px;")
		subclaim.setStyleSheet("font-size: 13px;")
		card_layout.addWidget(claim)
		card_layout.addWidget(subclaim)

		link = QLabel('<a href="https://github.com/dasarne/grbl-visualizer">github.com/dasarne/grbl-visualizer</a>')
		link.setOpenExternalLinks(False)
		link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
		link.setAlignment(Qt.AlignmentFlag.AlignCenter)
		card_layout.addWidget(link)

		layout.addWidget(card)

		grid = QGridLayout()
		info_rows = [
			(t["label.version"], "0.1.0"),
			(t["label.python"], "3.10+"),
			(t["label.qt"], "PyQt6"),
			(t["label.license"], "GPL-3.0"),
		]
		for row, (name, value) in enumerate(info_rows):
			grid.addWidget(QLabel(name), row, 0)
			grid.addWidget(QLabel(value), row, 1)
		layout.addLayout(grid)
		layout.addStretch(1)
		return w

	def _build_text_tab(self, text: str) -> QWidget:
		w = QWidget()
		layout = QVBoxLayout(w)
		label = QLabel(text)
		label.setWordWrap(True)
		label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
		layout.addWidget(label)
		return w

	def _tr_map(self) -> dict[str, str]:
		de = {
			"title": "Info GCode Lisa",
			"tab.info": "Info",
			"tab.contributors": "Mitwirkende",
			"tab.license": "Lizenz",
			"tab.libraries": "Bibliotheken",
			"tab.privacy": "Datenschutz",
			"label.version": "Version",
			"label.python": "Python",
			"label.qt": "Qt",
			"label.license": "Lizenz",
			"contributors.text": (
				"GCode Lisa wird als fokussiertes G-Code-Werkzeug fuer CNC entwickelt.\n\n"
				"Entwicklung: Arne von Irmer und ChatGPT.\n"
				"Das Projekt lebt im oeffentlichen Repository unter github.com/dasarne/grbl-visualizer.\n"
				"Beitraege sind willkommen."
			),
			"license.text": (
				"GCode Lisa wird unter der GPL-3.0-Lizenz veroeffentlicht.\n\n"
				"Die vollstaendige Lizenz steht in der Datei LICENSE im Repository."
			),
			"libraries.text": (
				"Verwendete Kernbibliotheken:\n"
				"- PyQt6\n"
				"- pytest\n"
				"- numpy (optional)\n"
				"- matplotlib (optional, legacy)"
			),
			"privacy.text": (
				"GCode Lisa ist eine lokale Desktop-Anwendung und uebertraegt keine G-Code-Dateien an Cloud-Dienste.\n\n"
				"Dateiverlauf und Einstellungen werden lokal gespeichert."
			),
		}
		en = {
			"title": "About GCode Lisa",
			"tab.info": "Info",
			"tab.contributors": "Contributors",
			"tab.license": "License",
			"tab.libraries": "Libraries",
			"tab.privacy": "Privacy",
			"label.version": "Version",
			"label.python": "Python",
			"label.qt": "Qt",
			"label.license": "License",
			"contributors.text": (
				"GCode Lisa is developed as a focused G-Code tool for CNC workflows.\n\n"
				"Development: Arne von Irmer and ChatGPT.\n"
				"The project lives in the public repository github.com/dasarne/grbl-visualizer.\n"
				"Contributions are welcome."
			),
			"license.text": (
				"GCode Lisa is released under GPL-3.0.\n\n"
				"See the LICENSE file in the repository root for details."
			),
			"libraries.text": (
				"Core libraries in use:\n"
				"- PyQt6\n"
				"- pytest\n"
				"- numpy (optional)\n"
				"- matplotlib (optional, legacy)"
			),
			"privacy.text": (
				"GCode Lisa is a local desktop application and does not upload G-Code files to cloud services.\n\n"
				"Recent files and settings are stored locally."
			),
		}
		return de if self._language == "de" else en
