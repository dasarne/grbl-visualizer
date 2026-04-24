"""English UI string resources for GCode Lisa."""

STRINGS: dict[str, str] = {
    # -----------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------
    "app.title": "GCode Lisa",

    # -----------------------------------------------------------------------
    # Menu titles
    # -----------------------------------------------------------------------
    "menu.file": "&File",
    "menu.edit": "&Edit",
    "menu.info": "&Info",

    # -----------------------------------------------------------------------
    # File menu actions
    # -----------------------------------------------------------------------
    "file.new": "&New",
    "file.open": "&Open...",
    "file.recent": "Recent Files",
    "file.recent_empty": "(none)",
    "file.save": "&Save",
    "file.save_as": "Save &As...",
    "file.settings": "&Settings",
    "file.about": "About GCode Lisa",
    "file.quit": "&Quit",
    "file.open_title": "Open G-Code File",
    "file.open_missing": "File not found: {path}",
    "file.open_failed": "Could not open file: {path} ({error})",
    "file.save_title": "Save G-Code File",
    "file.save_nothing": "No G-Code loaded to save.",

    # -----------------------------------------------------------------------
    # Status bar
    # -----------------------------------------------------------------------
    "status.ready": "Ready",
    "status.saved": "Saved: {path}",
    "status.loaded": "Loaded: {path}",
    "status.errors": "{count} error(s)",
    "status.warnings": "{count} warning(s)",
    "status.no_issues": "No issues found",
    "status.issues_button": "Messages/Errors: {total} (E:{errors}, W:{warnings})",
    "status.issues_tooltip": "Show messages dialog",
    "status.parse_error": "Parse error: {msg}",
    "status.replaced": "Replaced {count} occurrence(s)",
    "status.replaced_one": "Replaced: {term}",
    "status.search_found": "Found: {term}",
    "status.search_matches": "{count} match(es)",
    "status.search_not_found": "Not found: {term}",
    "status.new_instance_failed": "Could not launch a new instance.",
    "status.dialect_detected": "Detected dialect: {dialect} ({confidence}%)",
    "status.profile_active": "Active profile:",
    "status.profile_active_manual": "Active profile (manual): {profile}",
    "status.profile_active_auto": "Active profile (auto): {profile}",
    "status.profile_auto_option": "Auto",
    "status.profile_auto_tooltip": "Auto enabled: detected profile = {profile}",

    # -----------------------------------------------------------------------
    # Dialect labels
    # -----------------------------------------------------------------------
    "dialect.grbl": "GRBL",
    "dialect.linuxcnc": "LinuxCNC",
    "dialect.marlin": "Marlin",
    "dialect.unknown": "Unknown",

    # -----------------------------------------------------------------------
    # Edit menu
    # -----------------------------------------------------------------------
    "edit.undo": "&Undo",
    "edit.redo": "&Redo",
    "edit.copy": "&Copy",
    "edit.paste": "&Paste",
    "edit.find": "&Find",
    "edit.replace": "&Replace",
    "edit.messages": "&Messages",
    "edit.find_prompt": "Find:",
    "edit.find_not_found": "No match found.",
    "edit.replace_find": "Find:",
    "edit.replace_with": "Replace with:",

    # -----------------------------------------------------------------------
    # Window / dialog titles
    # -----------------------------------------------------------------------
    "title.untitled": "Untitled",
    "confirm.unsaved_title": "Unsaved changes",
    "confirm.unsaved_message": "The file has unsaved changes. Save before continuing?",

    # -----------------------------------------------------------------------
    # Find and Replace dialog
    # -----------------------------------------------------------------------
    "find.title": "Find and Replace",
    "find.find_label": "Find:",
    "find.find_prev": "Previous",
    "find.find_next": "Next",
    "find.regex": "Regular Expression",
    "find.replace_label": "Replace:",
    "find.replace_prev": "Replace Previous",
    "find.replace_next": "Replace Next",
    "find.replace_all": "Replace All",
    "find.in_selection": "In Selection",
    "find.case_sensitive": "Match Case",
    "find.find_placeholder": "Search term or regex pattern...",
    "find.replace_placeholder": "Replacement text...",
    "find.status.empty_search": "Empty search term",
    "find.status.regex_error": "Regex error: {error}",

    # -----------------------------------------------------------------------
    # About dialog
    # -----------------------------------------------------------------------
    "about.title": "About GCode Lisa",
    "about.tab.info": "Info",
    "about.tab.contributors": "Contributors",
    "about.tab.license": "License",
    "about.tab.libraries": "Libraries",
    "about.tab.privacy": "Privacy",
    "about.label.version": "Version",
    "about.label.python": "Python",
    "about.label.qt": "Qt",
    "about.label.license": "License",
    "about.contributors.text": (
        "GCode Lisa is developed as a focused G-Code tool for CNC workflows.<br><br>"
        "Development: Arne von Irmer and ChatGPT.<br>"
        "The project lives in the public repository "
        '<a href="https://github.com/dasarne/grbl-visualizer">github.com/dasarne/GCode-Lisa</a>.<br>'
        "Contributions are welcome."
    ),
    "about.license.text": (
        "GCode Lisa is released under GPL-3.0.\n\n"
        "See the LICENSE file in the repository root for details."
    ),
    "about.libraries.text": (
        "Core libraries in use:\n"
        "- PyQt6\n"
        "- pytest\n"
        "- numpy (optional)\n"
        "- matplotlib (optional, legacy)"
    ),
    "about.privacy.text": (
        "GCode Lisa is a local desktop application and does not upload "
        "G-Code files to cloud services.\n\n"
        "Recent files and settings are stored locally."
    ),
    "about.sponsor.text": (
        "Independent software for makers and small workshops depends on private "
        "engagement and sustained maintenance work."
    ),
    "about.sponsor.link": "Support development via GitHub Sponsors",
    "about.sponsor.url": "https://github.com/sponsors/dasarne",

    # -----------------------------------------------------------------------
    # Settings dialog
    # -----------------------------------------------------------------------
    "settings.title": "Settings",
    "settings.profile": "Dialect profile:",
    "settings.version": "Dialect profile:",
    "settings.auto_detect": "Use detected profile on file load:",
    "settings.language": "Language:",
    "settings.mouse_navigation": "Mouse navigation:",
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
    "settings.mouse_navigation.legacy": "Legacy",
    "settings.command": "Command",
    "settings.supported": "Supported",
    "settings.ok": "OK",
    "settings.cancel": "Cancel",
}
