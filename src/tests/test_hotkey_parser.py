"""
Unit tests for QPaste Hotkey Parser, Formatter, and Combo Matcher.
Tests parsing, case normalization, fallback handling, formatting, and event matching.
"""

import os
import sys
import unittest
from typing import Optional

# Ensure src directory is on sys.path for direct unittest invocation
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.hotkey_parser import HotkeyCombo, format_hotkey, match_hotkey, parse_hotkey


class MockKey:
    """Mock representing pynput.keyboard.Key."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Key.{self.name}"


class MockKeyCode:
    """Mock representing pynput.keyboard.KeyCode."""

    def __init__(self, char: Optional[str] = None, vk: Optional[int] = None) -> None:
        self.char = char
        self.vk = vk

    def __repr__(self) -> str:
        return f"KeyCode(char={self.char!r}, vk={self.vk})"


class TestHotkeyParser(unittest.TestCase):
    """Tests parse_hotkey and format_hotkey functionality."""

    def test_parse_single_keys(self) -> None:
        self.assertEqual(parse_hotkey("F4"), HotkeyCombo(frozenset(), "f4"))
        self.assertEqual(parse_hotkey("a"), HotkeyCombo(frozenset(), "a"))
        self.assertEqual(parse_hotkey("1"), HotkeyCombo(frozenset(), "1"))
        self.assertEqual(parse_hotkey("Escape"), HotkeyCombo(frozenset(), "escape"))
        self.assertEqual(parse_hotkey("esc"), HotkeyCombo(frozenset(), "escape"))
        self.assertEqual(parse_hotkey("Enter"), HotkeyCombo(frozenset(), "enter"))
        self.assertEqual(parse_hotkey("return"), HotkeyCombo(frozenset(), "enter"))
        self.assertEqual(parse_hotkey("Space"), HotkeyCombo(frozenset(), "space"))
        self.assertEqual(parse_hotkey("Tab"), HotkeyCombo(frozenset(), "tab"))
        self.assertEqual(parse_hotkey("Delete"), HotkeyCombo(frozenset(), "delete"))

    def test_parse_modifier_combos(self) -> None:
        self.assertEqual(parse_hotkey("Ctrl+V"), HotkeyCombo(frozenset({"ctrl"}), "v"))
        self.assertEqual(parse_hotkey("Shift+F4"), HotkeyCombo(frozenset({"shift"}), "f4"))
        self.assertEqual(parse_hotkey("Ctrl+Shift+N"), HotkeyCombo(frozenset({"ctrl", "shift"}), "n"))
        self.assertEqual(parse_hotkey("Ctrl+Alt+Delete"), HotkeyCombo(frozenset({"ctrl", "alt"}), "delete"))
        self.assertEqual(
            parse_hotkey("Ctrl+Shift+Alt+N"), HotkeyCombo(frozenset({"ctrl", "shift", "alt"}), "n")
        )
        self.assertEqual(parse_hotkey("Win+E"), HotkeyCombo(frozenset({"win"}), "e"))
        self.assertEqual(parse_hotkey("Ctrl++"), HotkeyCombo(frozenset({"ctrl"}), "+"))

    def test_case_insensitivity_and_whitespace(self) -> None:
        self.assertEqual(parse_hotkey("ctrl+v"), HotkeyCombo(frozenset({"ctrl"}), "v"))
        self.assertEqual(parse_hotkey("CTRL+V"), HotkeyCombo(frozenset({"ctrl"}), "v"))
        self.assertEqual(parse_hotkey("cTrL + sHiFt + n"), HotkeyCombo(frozenset({"ctrl", "shift"}), "n"))
        self.assertEqual(parse_hotkey("  shift+f4  "), HotkeyCombo(frozenset({"shift"}), "f4"))

    def test_modifier_and_key_aliases(self) -> None:
        self.assertEqual(parse_hotkey("control+v"), HotkeyCombo(frozenset({"ctrl"}), "v"))
        self.assertEqual(parse_hotkey("menu+f4"), HotkeyCombo(frozenset({"alt"}), "f4"))
        self.assertEqual(parse_hotkey("option+f4"), HotkeyCombo(frozenset({"alt"}), "f4"))
        self.assertEqual(parse_hotkey("cmd+space"), HotkeyCombo(frozenset({"win"}), "space"))
        self.assertEqual(parse_hotkey("super+d"), HotkeyCombo(frozenset({"win"}), "d"))
        self.assertEqual(parse_hotkey("windows+r"), HotkeyCombo(frozenset({"win"}), "r"))
        self.assertEqual(parse_hotkey("ctrl+del"), HotkeyCombo(frozenset({"ctrl"}), "delete"))
        self.assertEqual(parse_hotkey("ctrl+spacebar"), HotkeyCombo(frozenset({"ctrl"}), "space"))
        self.assertEqual(parse_hotkey("ctrl+pgup"), HotkeyCombo(frozenset({"ctrl"}), "pageup"))

    def test_malformed_string_fallback(self) -> None:
        self.assertIsNone(parse_hotkey(""))
        self.assertIsNone(parse_hotkey("   "))
        self.assertIsNone(parse_hotkey(None))  # type: ignore[arg-type]
        self.assertIsNone(parse_hotkey(123))  # type: ignore[arg-type]
        self.assertIsNone(parse_hotkey("Ctrl"))
        self.assertIsNone(parse_hotkey("Ctrl+Shift"))
        self.assertIsNone(parse_hotkey("Ctrl+A+B"))
        self.assertIsNone(parse_hotkey("Ctrl+UnknownKeyXYZ"))
        self.assertIsNone(parse_hotkey("InvalidKeyOnly"))

    def test_format_hotkey(self) -> None:
        self.assertEqual(format_hotkey(HotkeyCombo(frozenset({"ctrl", "shift"}), "n")), "Ctrl+Shift+N")
        self.assertEqual(format_hotkey(HotkeyCombo(frozenset(), "f4")), "F4")
        self.assertEqual(format_hotkey(HotkeyCombo(frozenset({"shift"}), "f4")), "Shift+F4")
        self.assertEqual(format_hotkey(HotkeyCombo(frozenset({"ctrl", "alt"}), "delete")), "Ctrl+Alt+Delete")
        self.assertEqual(
            format_hotkey(HotkeyCombo(frozenset({"ctrl", "shift", "alt"}), "n")), "Ctrl+Shift+Alt+N"
        )
        self.assertEqual(format_hotkey(HotkeyCombo(frozenset({"ctrl"}), "v")), "Ctrl+V")
        self.assertEqual(format_hotkey(HotkeyCombo(frozenset(), "escape")), "Escape")
        with self.assertRaises(TypeError):
            format_hotkey("NotAHotkeyCombo")  # type: ignore[arg-type]


class TestHotkeyMatcher(unittest.TestCase):
    """Tests match_hotkey with strings, mock pynput Keys, and KeyCodes."""

    def setUp(self) -> None:
        self.combo_f4 = HotkeyCombo(frozenset(), "f4")
        self.combo_shift_f4 = HotkeyCombo(frozenset({"shift"}), "f4")
        self.combo_ctrl_v = HotkeyCombo(frozenset({"ctrl"}), "v")
        self.combo_ctrl_shift_n = HotkeyCombo(frozenset({"ctrl", "shift"}), "n")

    def test_single_key_matching(self) -> None:
        # F4 with no modifiers pressed
        self.assertTrue(match_hotkey(self.combo_f4, set(), MockKey("f4")))
        self.assertTrue(match_hotkey(self.combo_f4, set(), "f4"))
        self.assertTrue(match_hotkey(self.combo_f4, set(), "F4"))
        # F4 with Shift held should NOT match plain F4
        self.assertFalse(match_hotkey(self.combo_f4, {MockKey("shift_l")}, MockKey("f4")))
        self.assertFalse(match_hotkey(self.combo_f4, {"shift"}, "f4"))

    def test_combo_with_mock_pynput_keys(self) -> None:
        key_ctrl = MockKey("ctrl_l")
        key_shift = MockKey("shift_r")
        key_v = MockKeyCode(char="v", vk=86)
        key_n = MockKeyCode(char="n", vk=78)

        # Shift+F4
        self.assertTrue(match_hotkey(self.combo_shift_f4, {key_shift}, MockKey("f4")))
        # Ctrl+V
        self.assertTrue(match_hotkey(self.combo_ctrl_v, {key_ctrl}, key_v))
        # Ctrl+Shift+N
        self.assertTrue(match_hotkey(self.combo_ctrl_shift_n, {key_ctrl, key_shift}, key_n))

    def test_ctrl_character_translation(self) -> None:
        # When Ctrl is held, pynput often emits ascii control code \x16 for 'v'
        key_ctrl = MockKey("ctrl_l")
        key_ctrl_v = MockKeyCode(char="\x16", vk=86)
        self.assertTrue(match_hotkey(self.combo_ctrl_v, {key_ctrl}, key_ctrl_v))

    def test_mismatch_on_extra_modifiers_or_wrong_key(self) -> None:
        key_ctrl = MockKey("ctrl_l")
        key_alt = MockKey("alt_l")
        key_v = MockKeyCode(char="v", vk=86)

        # Ctrl+Alt+V should NOT match Ctrl+V
        self.assertFalse(match_hotkey(self.combo_ctrl_v, {key_ctrl, key_alt}, key_v))
        # Missing Ctrl
        self.assertFalse(match_hotkey(self.combo_ctrl_v, set(), key_v))
        # Wrong key
        key_c = MockKeyCode(char="c", vk=67)
        self.assertFalse(match_hotkey(self.combo_ctrl_v, {key_ctrl}, key_c))

    def test_string_and_vk_representations(self) -> None:
        # Using string representation
        self.assertTrue(match_hotkey(self.combo_ctrl_v, {"ctrl"}, "v"))
        self.assertTrue(match_hotkey(self.combo_ctrl_shift_n, {"ctrl", "shift"}, "n"))
        # Using VK integers
        self.assertTrue(match_hotkey(self.combo_ctrl_v, {0x11}, 0x56))

    def test_match_fallback_when_current_key_is_none(self) -> None:
        self.assertTrue(match_hotkey(self.combo_ctrl_v, {MockKey("ctrl_l"), "v"}, None))
        self.assertFalse(match_hotkey(self.combo_ctrl_v, {MockKey("ctrl_l")}, None))

    def test_match_invalid_combo(self) -> None:
        self.assertFalse(match_hotkey("NotACombo", set(), "v"))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
