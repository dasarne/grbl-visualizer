"""German UI string resources for GCode Lisa."""

STRINGS: dict[str, str] = {
    # -----------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------
    "app.title": "GCode Lisa",

    # -----------------------------------------------------------------------
    # Menu titles
    # -----------------------------------------------------------------------
    "menu.file": "&Datei",
    "menu.edit": "&Bearbeiten",
    "menu.info": "&Info",

    # -----------------------------------------------------------------------
    # File menu actions
    # -----------------------------------------------------------------------
    "file.new": "&Neu",
    "file.open": "&Öffnen...",
    "file.recent": "Letzte Dateien",
    "file.recent_empty": "(keine)",
    "file.save": "&Speichern",
    "file.save_as": "Speichern &unter...",
    "file.settings": "&Einstellungen",
    "file.about": "Über GCode Lisa",
    "file.quit": "&Beenden",
    "file.open_title": "G-Code-Datei öffnen",
    "file.open_missing": "Datei nicht gefunden: {path}",
    "file.open_failed": "Datei konnte nicht geöffnet werden: {path} ({error})",
    "file.save_title": "G-Code-Datei speichern",
    "file.save_nothing": "Keine geladene G-Code-Datei zum Speichern.",

    # -----------------------------------------------------------------------
    # Status bar
    # -----------------------------------------------------------------------
    "status.ready": "Bereit",
    "status.saved": "Gespeichert: {path}",
    "status.loaded": "Geladen: {path}",
    "status.errors": "{count} Fehler",
    "status.warnings": "{count} Warnungen",
    "status.no_issues": "Keine Probleme gefunden",
    "status.issues_button": "Meldungen/Fehler: {total} (E:{errors}, W:{warnings})",
    "status.issues_tooltip": "Meldungsdialog anzeigen",
    "status.parse_error": "Parserfehler: {msg}",
    "status.replaced": "{count} Treffer ersetzt",
    "status.replaced_one": "Ersetzt: {term}",
    "status.search_found": "Gefunden: {term}",
    "status.search_matches": "{count} Treffer",
    "status.search_not_found": "Nicht gefunden: {term}",
    "status.new_instance_failed": "Neue Instanz konnte nicht gestartet werden.",
    "status.dialect_detected": "Erkannter Dialekt: {dialect} ({confidence}%)",
    "status.profile_active": "Aktives Profil:",
    "status.profile_active_manual": "Aktives Profil (manuell): {profile}",
    "status.profile_active_auto": "Aktives Profil (automatisch): {profile}",
    "status.profile_auto_option": "Auto",
    "status.profile_auto_tooltip": "Auto aktiv: erkanntes Profil = {profile}",

    # -----------------------------------------------------------------------
    # Dialekt-Bezeichnungen
    # -----------------------------------------------------------------------
    "dialect.grbl": "GRBL",
    "dialect.linuxcnc": "LinuxCNC",
    "dialect.marlin": "Marlin",
    "dialect.unknown": "Unbekannt",

    # -----------------------------------------------------------------------
    # Edit menu
    # -----------------------------------------------------------------------
    "edit.undo": "&Rückgängig",
    "edit.redo": "&Wiederherstellen",
    "edit.copy": "&Kopieren",
    "edit.paste": "&Einfügen",
    "edit.find": "&Suchen",
    "edit.replace": "&Ersetzen",
    "edit.messages": "&Meldungen",
    "edit.find_prompt": "Suchbegriff:",
    "edit.find_not_found": "Kein Treffer gefunden.",
    "edit.replace_find": "Suche:",
    "edit.replace_with": "Ersetzen durch:",

    # -----------------------------------------------------------------------
    # Window / dialog titles
    # -----------------------------------------------------------------------
    "title.untitled": "Unbenannt",
    "confirm.unsaved_title": "Ungespeicherte Änderungen",
    "confirm.unsaved_message": "Die Datei wurde geändert. Vor dem Fortfahren speichern?",

    # -----------------------------------------------------------------------
    # Find and Replace dialog
    # -----------------------------------------------------------------------
    "find.title": "Suchen und Ersetzen",
    "find.find_label": "Suchen:",
    "find.find_prev": "Vorherige",
    "find.find_next": "Nächste",
    "find.regex": "Regulärer Ausdruck",
    "find.replace_label": "Ersetzen:",
    "find.replace_prev": "Vorherige ersetzen",
    "find.replace_next": "Nächste ersetzen",
    "find.replace_all": "Alles ersetzen",
    "find.in_selection": "In Auswahl",
    "find.case_sensitive": "Groß-/Kleinschreibung",
    "find.find_placeholder": "Suchbegriff oder Regex-Muster...",
    "find.replace_placeholder": "Ersetzungstext...",
    "find.status.empty_search": "Leerer Suchbegriff",
    "find.status.regex_error": "Regex-Fehler: {error}",

    # -----------------------------------------------------------------------
    # About dialog
    # -----------------------------------------------------------------------
    "about.title": "Info GCode Lisa",
    "about.tab.info": "Info",
    "about.tab.contributors": "Mitwirkende",
    "about.tab.license": "Lizenz",
    "about.tab.libraries": "Bibliotheken",
    "about.tab.privacy": "Datenschutz",
    "about.label.version": "Version",
    "about.label.python": "Python",
    "about.label.qt": "Qt",
    "about.label.license": "Lizenz",
    "about.contributors.text": (
        "GCode Lisa wird als fokussiertes G-Code-Werkzeug für CNC entwickelt.<br><br>"
        "Entwicklung: Arne von Irmer und ChatGPT.<br>"
        "Das Projekt lebt im öffentlichen Repository unter "
        '<a href="https://github.com/dasarne/grbl-visualizer">github.com/dasarne/GCode-Lisa</a>.<br>'
        "Beiträge sind willkommen."
    ),
    "about.license.text": (
        "GCode Lisa wird unter der GPL-3.0-Lizenz veröffentlicht.\n\n"
        "Die vollständige Lizenz steht in der Datei LICENSE im Repository."
    ),
    "about.libraries.text": (
        "Verwendete Kernbibliotheken:\n"
        "- PyQt6\n"
        "- pytest\n"
        "- numpy (optional)\n"
        "- matplotlib (optional, legacy)"
    ),
    "about.privacy.text": (
        "GCode Lisa ist eine lokale Desktop-Anwendung und überträgt keine "
        "G-Code-Dateien an Cloud-Dienste.\n\n"
        "Dateiverlauf und Einstellungen werden lokal gespeichert."
    ),
    "about.sponsor.text": (
        "Unabhängige Software für Maker und kleine Werkstätten lebt von "
        "privatem Engagement und kontinuierlicher Pflege."
    ),
    "about.sponsor.link": "Entwicklung über GitHub Sponsors unterstützen",
    "about.sponsor.url": "https://github.com/sponsors/dasarne",

    # -----------------------------------------------------------------------
    # Settings dialog
    # -----------------------------------------------------------------------
    "settings.title": "Einstellungen",
    "settings.profile": "Dialekt-Profil:",
    "settings.version": "Dialekt-Profil:",
    "settings.auto_detect": "Erkanntes Profil beim Laden verwenden:",
    "settings.language": "Sprache:",
    "settings.mouse_navigation": "Maus-Navigation:",
    "settings.mouse_navigation.cad": "CAD (FreeCAD)",
    "settings.mouse_navigation.blender": "Blender",
    "settings.mouse_navigation.gesture": "Gesture",
    "settings.mouse_navigation.maya_gesture": "MayaGesture",
    "settings.mouse_navigation.open_cascade": "OpenCascade",
    "settings.mouse_navigation.open_inventor": "OpenInventor",
    "settings.mouse_navigation.open_scad": "OpenSCAD",
    "settings.mouse_navigation.revit": "Revit",
    "settings.mouse_navigation.siemens_nx": "Siemens NX",
    "settings.mouse_navigation.solidworks": "SolidWorks",
    "settings.mouse_navigation.tinkercad": "TinkerCAD",
    "settings.mouse_navigation.touchpad": "Touchpad",
    "settings.mouse_navigation.legacy": "Legacy (Alt)",
    "settings.command": "Befehl",
    "settings.supported": "Unterstützt",
    "settings.ok": "OK",
    "settings.cancel": "Abbrechen",
}
