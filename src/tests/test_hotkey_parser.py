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

from core.hotkey_parser import (
    HotkeyCombo,
    format_hotkey,
    hotkey_parts,
    is_altgr_risky,
    key_name_from_vk,
    match_hotkey,
    modifier_from_vk,
    parse_hotkey,
)


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

class TestLayoutIndependentMatching(unittest.TestCase):
    """Letters and top-row digits resolve by virtual key, not by layout-dependent char."""

    def test_russian_layout_letter_matches_by_vk(self) -> None:
        combo = parse_hotkey("Ctrl+Alt+V")
        held = {MockKey("ctrl_l"), MockKey("alt_l")}
        key_v = MockKeyCode(char="\u043c", vk=0x56)
        self.assertTrue(match_hotkey(combo, held, key_v))

    def test_azerty_top_row_digit_matches_by_vk(self) -> None:
        combo = parse_hotkey("Ctrl+1")
        key_one = MockKeyCode(char="&", vk=0x31)
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, key_one))

    def test_layout_char_does_not_cause_false_match(self) -> None:
        # Physical V key must not match a hotkey bound to the char it happens to report
        combo = HotkeyCombo(frozenset({"ctrl"}), "\u043c")
        key_v = MockKeyCode(char="\u043c", vk=0x56)
        self.assertFalse(match_hotkey(combo, {MockKey("ctrl_l")}, key_v))

    def test_ctrl_control_character_still_matches(self) -> None:
        combo = parse_hotkey("Ctrl+V")
        key_v = MockKeyCode(char="\x16", vk=0x56)
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, key_v))

    def test_ctrl_control_character_without_vk_still_matches(self) -> None:
        combo = parse_hotkey("Ctrl+V")
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, MockKeyCode(char="\x16")))

    def test_numpad_digits_unchanged(self) -> None:
        # With a char reported, numpad resolves by char exactly as before
        combo = parse_hotkey("Ctrl+5")
        numpad_five = MockKeyCode(char="5", vk=0x65)
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, numpad_five))
        # With no char, numpad vk has no mapping and is not treated as a top-row digit
        self.assertFalse(match_hotkey(combo, {MockKey("ctrl_l")}, MockKeyCode(vk=0x65)))

    def test_char_only_key_falls_back_to_char(self) -> None:
        combo = parse_hotkey("Ctrl+V")
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, MockKeyCode(char="v")))
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, MockKeyCode(char="V")))

    def test_function_key_unchanged(self) -> None:
        combo = parse_hotkey("Ctrl+F5")
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, MockKey("f5")))
        self.assertTrue(match_hotkey(combo, {MockKey("ctrl_l")}, MockKeyCode(vk=0x74)))


class TestAltGrRisk(unittest.TestCase):
    """is_altgr_risky flags Ctrl+Alt combos on keys a layout may map behind AltGr."""

    def test_ctrl_alt_with_letter_or_digit_is_risky(self) -> None:
        self.assertTrue(is_altgr_risky(parse_hotkey("Ctrl+Alt+A")))
        self.assertTrue(is_altgr_risky(parse_hotkey("Ctrl+Alt+1")))

    def test_ctrl_alt_with_printable_punctuation_is_risky(self) -> None:
        self.assertTrue(is_altgr_risky(HotkeyCombo(frozenset({"ctrl", "alt"}), ";")))

    def test_extra_modifiers_still_risky(self) -> None:
        self.assertTrue(is_altgr_risky(parse_hotkey("Ctrl+Shift+Alt+Q")))

    def test_ctrl_alt_with_function_or_navigation_key_is_safe(self) -> None:
        self.assertFalse(is_altgr_risky(parse_hotkey("Ctrl+Alt+F5")))
        self.assertFalse(is_altgr_risky(parse_hotkey("Ctrl+Alt+Delete")))
        self.assertFalse(is_altgr_risky(parse_hotkey("Ctrl+Alt+Up")))
        self.assertFalse(is_altgr_risky(parse_hotkey("Ctrl+Alt+Space")))

    def test_missing_ctrl_or_alt_is_safe(self) -> None:
        self.assertFalse(is_altgr_risky(parse_hotkey("Ctrl+A")))
        self.assertFalse(is_altgr_risky(parse_hotkey("Alt+A")))
        self.assertFalse(is_altgr_risky(parse_hotkey("A")))
        self.assertFalse(is_altgr_risky(parse_hotkey("Ctrl+Shift+A")))


class TestVirtualKeyNames(unittest.TestCase):
    """key_name_from_vk / modifier_from_vk translate Tk keycodes (Windows VK) to canonical names."""

    def test_letters_map_to_lowercase_names(self) -> None:
        self.assertEqual(key_name_from_vk(0x41), "a")
        self.assertEqual(key_name_from_vk(0x56), "v")
        self.assertEqual(key_name_from_vk(0x5A), "z")

    def test_digits_map_to_digit_names(self) -> None:
        self.assertEqual(key_name_from_vk(0x30), "0")
        self.assertEqual(key_name_from_vk(0x39), "9")

    def test_function_keys_f1_to_f24(self) -> None:
        self.assertEqual(key_name_from_vk(0x70), "f1")
        self.assertEqual(key_name_from_vk(0x73), "f4")
        self.assertEqual(key_name_from_vk(0x87), "f24")

    def test_navigation_and_named_keys(self) -> None:
        expected = {
            0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x1B: "escape", 0x20: "space",
            0x21: "pageup", 0x22: "pagedown", 0x23: "end", 0x24: "home",
            0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down", 0x2D: "insert", 0x2E: "delete",
        }
        for vk, name in expected.items():
            self.assertEqual(key_name_from_vk(vk), name)

    def test_unmapped_and_modifier_vks_return_none(self) -> None:
        self.assertIsNone(key_name_from_vk(0x10))  # Shift is a modifier, not a key
        self.assertIsNone(key_name_from_vk(0x14))  # CapsLock is not recordable
        self.assertIsNone(key_name_from_vk(0xE7))  # VK_PACKET
        self.assertIsNone(key_name_from_vk(0))

    def test_non_int_input_returns_none(self) -> None:
        self.assertIsNone(key_name_from_vk("v"))  # type: ignore[arg-type]
        self.assertIsNone(key_name_from_vk(None))  # type: ignore[arg-type]

    def test_modifier_vks_map_to_modifier_names(self) -> None:
        self.assertEqual(modifier_from_vk(0x10), "shift")
        self.assertEqual(modifier_from_vk(0xA1), "shift")
        self.assertEqual(modifier_from_vk(0x11), "ctrl")
        self.assertEqual(modifier_from_vk(0xA3), "ctrl")
        self.assertEqual(modifier_from_vk(0x12), "alt")
        self.assertEqual(modifier_from_vk(0xA5), "alt")
        self.assertEqual(modifier_from_vk(0x5B), "win")
        self.assertEqual(modifier_from_vk(0x5C), "win")

    def test_non_modifier_vk_returns_none_for_modifier(self) -> None:
        self.assertIsNone(modifier_from_vk(0x56))
        self.assertIsNone(modifier_from_vk(0x73))

    def test_recorded_combo_round_trips_through_parse(self) -> None:
        combo = HotkeyCombo(frozenset({"ctrl", "alt"}), key_name_from_vk(0x56))
        self.assertEqual(parse_hotkey(format_hotkey(combo)), combo)
        combo = HotkeyCombo(frozenset({"win", "shift"}), key_name_from_vk(0x74))
        self.assertEqual(parse_hotkey(format_hotkey(combo)), combo)


class TestHotkeyParts(unittest.TestCase):
    """hotkey_parts splits a combo into display tokens, one per key-cap."""

    def test_modifiers_in_canonical_order_then_key(self) -> None:
        combo = HotkeyCombo(frozenset({"alt", "ctrl"}), "v")
        self.assertEqual(hotkey_parts(combo), ["Ctrl", "Alt", "V"])

    def test_named_and_function_keys(self) -> None:
        self.assertEqual(hotkey_parts(parse_hotkey("Shift+F4")), ["Shift", "F4"])
        self.assertEqual(hotkey_parts(parse_hotkey("Ctrl+PageDown")), ["Ctrl", "PageDown"])

    def test_win_combo_is_displayable(self) -> None:
        self.assertEqual(hotkey_parts(parse_hotkey("Win+V")), ["Win", "V"])

    def test_joined_parts_match_format_hotkey(self) -> None:
        combo = parse_hotkey("Ctrl+Shift+Alt+Win+Delete")
        self.assertEqual("+".join(hotkey_parts(combo)), format_hotkey(combo))


if __name__ == "__main__":
    unittest.main()
