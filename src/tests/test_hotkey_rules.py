"""
Unit tests for QPaste hotkey validation rules (validate_hotkey).
Covers the modifier requirement, reserved combos, duplicate detection and the AltGr warning.
"""

import os
import sys
import unittest

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.hotkey_parser import parse_hotkey
from core.hotkey_rules import RESERVED_COMBOS, ValidationResult, validate_hotkey

ASSIGNMENTS = {
    "toggle_queue": "F4",
    "clear_queue": "Shift+F4",
    "toggle_notepad": "F3",
}
LABELS = {
    "toggle_queue": "Toggle Queue Mode",
    "clear_queue": "Clear Queue",
    "toggle_notepad": "Quick Notepad",
}


def check(text: str, action: str = "toggle_queue") -> ValidationResult:
    return validate_hotkey(parse_hotkey(text), action, ASSIGNMENTS, LABELS)


class TestModifierRequirement(unittest.TestCase):
    """Typing keys need Ctrl, Alt or Win; function keys may stand alone."""

    def test_plain_letter_digit_and_space_are_rejected(self) -> None:
        for text in ("A", "5", "Space", "Enter", "Tab", "Backspace", "Delete", "Up", "Home", "End", "PageUp", "PageDown", "Insert"):
            with self.subTest(text=text):
                self.assertIsNotNone(check(text).error)

    def test_shift_alone_is_not_enough(self) -> None:
        self.assertIsNotNone(check("Shift+A").error)
        self.assertIsNotNone(check("Shift+Space").error)
        self.assertIsNotNone(check("Shift+Left").error)

    def test_ctrl_alt_or_win_unlock_typing_keys(self) -> None:
        for text in ("Ctrl+Q", "Alt+Q", "Win+Q", "Ctrl+Space", "Alt+Left", "Ctrl+Shift+Q"):
            with self.subTest(text=text):
                self.assertIsNone(check(text).error)

    def test_function_keys_alone_and_with_shift_are_fine(self) -> None:
        self.assertIsNone(check("F8").error)
        self.assertIsNone(check("Shift+F8").error)
        self.assertIsNone(check("F24").error)


class TestReservedCombos(unittest.TestCase):
    """Combos QPaste or Windows rely on are blocked."""

    def test_clipboard_shortcuts_are_blocked(self) -> None:
        for text in ("Ctrl+C", "Ctrl+V", "Ctrl+X"):
            with self.subTest(text=text):
                self.assertIn("reserved", check(text).error)

    def test_window_switching_and_system_combos_are_blocked(self) -> None:
        for text in ("Alt+F4", "Alt+Tab", "Ctrl+Esc", "Alt+Esc", "Ctrl+Shift+Esc", "Ctrl+Alt+Delete", "Win+L"):
            with self.subTest(text=text):
                self.assertIn("reserved", check(text).error)

    def test_escape_alone_is_blocked_because_it_cancels_recording(self) -> None:
        result = check("Esc")
        self.assertIn("Esc", result.error)
        self.assertIn("cancel", result.error)

    def test_reserved_set_is_a_named_frozen_constant(self) -> None:
        self.assertIsInstance(RESERVED_COMBOS, frozenset)
        self.assertIn(parse_hotkey("Ctrl+V"), RESERVED_COMBOS)

    def test_similar_but_unreserved_combos_pass(self) -> None:
        self.assertIsNone(check("Ctrl+Shift+C").error)
        self.assertIsNone(check("Alt+F5").error)
        self.assertIsNone(check("Alt+V").error)

    def test_any_ctrl_v_combo_is_blocked_because_queue_paste_intercepts_it(self) -> None:
        """The Ctrl+V hook fires whenever Ctrl is down, so extra modifiers would also pop the queue."""
        for text in ("Ctrl+Alt+V", "Ctrl+Shift+V", "Ctrl+Alt+Shift+V"):
            with self.subTest(text=text):
                self.assertIn("queue paste", check(text).error)


class TestDuplicates(unittest.TestCase):
    """A combo bound to another action is an error that names that action."""

    def test_duplicate_of_other_action_names_it(self) -> None:
        result = check("F3", action="toggle_queue")
        self.assertEqual(result.error, "Already used by Quick Notepad")

    def test_reassigning_own_current_combo_is_allowed(self) -> None:
        self.assertIsNone(check("F4", action="toggle_queue").error)

    def test_shift_f4_and_f4_are_distinct(self) -> None:
        self.assertEqual(check("Shift+F4", action="toggle_notepad").error, "Already used by Clear Queue")
        self.assertEqual(check("F4", action="clear_queue").error, "Already used by Toggle Queue Mode")

    def test_unparsable_stored_assignment_is_ignored(self) -> None:
        result = validate_hotkey(parse_hotkey("F9"), "toggle_queue", {"clear_queue": "garbage"}, LABELS)
        self.assertTrue(result.ok)

    def test_label_falls_back_to_title_cased_action(self) -> None:
        result = validate_hotkey(parse_hotkey("F3"), "toggle_queue", ASSIGNMENTS)
        self.assertEqual(result.error, "Already used by Toggle Notepad")


class TestAltGrWarning(unittest.TestCase):
    """Ctrl+Alt+<printable> is saved but flagged."""

    def test_ctrl_alt_letter_warns_but_has_no_error(self) -> None:
        result = check("Ctrl+Alt+Q")
        self.assertIsNone(result.error)
        self.assertTrue(result.ok)
        self.assertIn("AltGr", result.warning)

    def test_ctrl_alt_function_key_has_no_warning(self) -> None:
        result = check("Ctrl+Alt+F5")
        self.assertTrue(result.ok)
        self.assertIsNone(result.warning)

    def test_plain_valid_combo_has_neither(self) -> None:
        result = check("Ctrl+Q")
        self.assertTrue(result.ok)
        self.assertIsNone(result.warning)

    def test_error_result_is_not_ok(self) -> None:
        self.assertFalse(check("A").ok)


if __name__ == "__main__":
    unittest.main()
