"""Tests for FindReplaceDialog behavior and UX affordances."""

from src.ui.find_replace_dialog import FindReplaceDialog


def test_enter_in_find_triggers_find_next(qtbot):
    """Pressing Enter in the find field should trigger next-search action."""
    dialog = FindReplaceDialog(language="en")
    qtbot.addWidget(dialog)

    calls: list[tuple[str, bool, bool, bool]] = []
    dialog.find_next_requested.connect(lambda term, use_regex, in_sel, case_sens: calls.append((term, use_regex, in_sel, case_sens)))

    dialog._find_input.setText("G1")
    dialog._find_input.returnPressed.emit()

    assert calls == [("G1", False, False, False)]


def test_invalid_regex_while_typing_sets_error_and_clears_preview(qtbot):
    """Typing an invalid regex should report the error and clear preview highlights."""
    dialog = FindReplaceDialog(language="en")
    qtbot.addWidget(dialog)

    previews: list[tuple[str, bool, bool, bool]] = []
    dialog.search_updated.connect(lambda term, use_regex, in_sel, case_sens: previews.append((term, use_regex, in_sel, case_sens)))

    dialog._regex_check.setChecked(True)
    dialog._find_input.setText("(")

    assert previews
    assert previews[-1][0] == ""
    assert "Regex error" in dialog._status_label.text()


def test_placeholders_are_localized(qtbot):
    """Placeholder text should switch with dialog language resources."""
    dialog = FindReplaceDialog(language="de")
    qtbot.addWidget(dialog)

    assert dialog._find_input.placeholderText() == "Suchbegriff oder Regex-Muster..."
    assert dialog._replace_input.placeholderText() == "Ersetzungstext..."


def test_case_sensitive_checkbox_present_and_localized(qtbot):
    """Case sensitivity checkbox should be present with correct localized label."""
    dialog_en = FindReplaceDialog(language="en")
    qtbot.addWidget(dialog_en)
    assert dialog_en._case_check.text() == "Match Case"

    dialog_de = FindReplaceDialog(language="de")
    qtbot.addWidget(dialog_de)
    assert dialog_de._case_check.text() == "Groß-/Kleinschreibung"


def test_case_sensitive_emitted_in_signal(qtbot):
    """Enabling case-sensitive checkbox should emit True as last signal argument."""
    dialog = FindReplaceDialog(language="en")
    qtbot.addWidget(dialog)

    calls: list[tuple[str, bool, bool, bool]] = []
    dialog.find_next_requested.connect(lambda term, use_regex, in_sel, case_sens: calls.append((term, use_regex, in_sel, case_sens)))

    dialog._case_check.setChecked(True)
    dialog._find_input.setText("G1")
    dialog._find_input.returnPressed.emit()

    assert calls == [("G1", False, False, True)]
