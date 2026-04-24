"""About dialog for GCode Lisa."""

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from .resources import get_strings
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

		link = QLabel('<a href="https://github.com/dasarne/grbl-visualizer">github.com/dasarne/GCode-Lisa</a>')
		link.setOpenExternalLinks(False)
		link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
		link.setAlignment(Qt.AlignmentFlag.AlignCenter)
		card_layout.addWidget(link)

		sponsor_text = QLabel(t["sponsor.text"])
		sponsor_text.setWordWrap(True)
		sponsor_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
		card_layout.addWidget(sponsor_text)

		sponsor_link = QLabel(f'<a href="{t["sponsor.url"]}">{t["sponsor.link"]}</a>')
		sponsor_link.setOpenExternalLinks(False)
		sponsor_link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
		sponsor_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
		card_layout.addWidget(sponsor_link)

		layout.addWidget(card)

		grid = QGridLayout()
		info_rows = [
			(t["label.version"], "1.0.0"),
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
		label.setOpenExternalLinks(True)
		layout.addWidget(label)
		return w

	def _tr_map(self) -> dict[str, str]:
		s = get_strings(self._language)
		return {
			"title": s["about.title"],
			"tab.info": s["about.tab.info"],
			"tab.contributors": s["about.tab.contributors"],
			"tab.license": s["about.tab.license"],
			"tab.libraries": s["about.tab.libraries"],
			"tab.privacy": s["about.tab.privacy"],
			"label.version": s["about.label.version"],
			"label.python": s["about.label.python"],
			"label.qt": s["about.label.qt"],
			"label.license": s["about.label.license"],
			"contributors.text": s["about.contributors.text"],
			"license.text": s["about.license.text"],
			"libraries.text": s["about.libraries.text"],
			"privacy.text": s["about.privacy.text"],
			"sponsor.text": s["about.sponsor.text"],
			"sponsor.link": s["about.sponsor.link"],
			"sponsor.url": s["about.sponsor.url"],
		}
