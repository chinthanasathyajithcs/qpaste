"""
Unit tests for HotkeyRecorderField, the press-to-record key-cap widget.
Drives the widget with synthetic Tk key events (keycode = Windows virtual-key code)
against a mocked tkinter module.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import List, Optional
from unittest.mock import MagicMock

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.hotkey_parser import HotkeyCombo, parse_hotkey
import ui.hotkey_recorder as recorder_mod
from ui.hotkey_recorder import HotkeyRecorderField, widget_is_within
from tk_mocks import MockWidget, key_event, make_mock_tk

VK_SHIFT, VK_CTRL, VK_ALT, VK_WIN = 0x10, 0x11, 0x12, 0x5B
VK_ESC, VK_F4, VK_Q, VK_CAPSLOCK = 0x1B, 0x73, 0x51, 0x14


class TestHotkeyRecorderField(unittest.TestCase):
    def setUp(self) -> None:
        self.orig_tk = recorder_mod.tk
        recorder_mod.tk = make_mock_tk()
        self.parent = MockWidget()
        self.events: List[str] = []
        self.submitted: List[Optional[HotkeyCombo]] = []
        self.accept = True
        self.field = self._make_field(parse_hotkey("F4"))

    def tearDown(self) -> None:
        recorder_mod.tk = self.orig_tk

    def _make_field(self, combo: Optional[HotkeyCombo]) -> HotkeyRecorderField:
        return HotkeyRecorderField(
            self.parent,
            combo=combo,
            on_start=lambda: self.events.append("start"),
            on_submit=self._on_submit,
            on_stop=lambda committed: self.events.append(f"stop:{committed}"),
        )

    def _on_submit(self, combo: Optional[HotkeyCombo]) -> bool:
        self.submitted.append(combo)
        return self.accept

    def _press(self, *keycodes: int) -> None:
        for code in keycodes:
            self.field.on_key_press(key_event(code))

    def _release(self, *keycodes: int) -> None:
        for code in keycodes:
            self.field.on_key_release(key_event(code))

    # --- display -------------------------------------------------------------

    def test_shows_combo_as_one_cap_per_key(self) -> None:
        field = self._make_field(parse_hotkey("Ctrl+Alt+V"))
        self.assertEqual(field.displayed_tokens, ["Ctrl", "Alt", "V"])
        self.assertEqual(field.combo, parse_hotkey("Ctrl+Alt+V"))

    def test_win_combo_from_config_displays_as_caps(self) -> None:
        field = self._make_field(parse_hotkey("Win+V"))
        self.assertEqual(field.displayed_tokens, ["Win", "V"])

    def test_caps_use_dark_cap_style(self) -> None:
        cap = self.field._cap_widgets[0]
        self.assertEqual(cap._config["bg"], recorder_mod.BUTTON_BG)
        self.assertEqual(cap._config["fg"], recorder_mod.TEXT_PRIMARY)
        self.assertEqual(cap._config["highlightbackground"], recorder_mod.BUTTON_BORDER)
        self.assertEqual(cap._config["font"][0], "Segoe UI")
        self.assertIn(cap._config["font"][1], (8, 9))
        self.assertEqual(cap._config["font"][2], "bold")

    def test_missing_combo_shows_fallback_text_cap(self) -> None:
        field = HotkeyRecorderField(self.parent, combo=None, fallback_text="None")
        self.assertEqual(field.displayed_tokens, ["None"])

    def test_set_combo_updates_display(self) -> None:
        self.field.set_combo(parse_hotkey("Shift+F9"))
        self.assertEqual(self.field.displayed_tokens, ["Shift", "F9"])

    def test_idle_border_is_neutral(self) -> None:
        self.assertEqual(self.field.frame._config["highlightbackground"], recorder_mod.BUTTON_BORDER)

    # --- starting ------------------------------------------------------------

    def test_start_recording_notifies_focuses_and_shows_prompt(self) -> None:
        self.field.start_recording()

        self.assertTrue(self.field.recording)
        self.assertEqual(self.events, ["start"])
        self.assertTrue(self.field.frame.focused)
        self.assertEqual(self.field.frame._config["highlightbackground"], recorder_mod.ACCENT_PRIMARY)
        self.assertEqual(self.field.displayed_tokens, [])
        prompt = self.field._cap_widgets[0]
        self.assertEqual(prompt._config["text"], "Press keys…")
        self.assertEqual(prompt._config["fg"], recorder_mod.TEXT_SECONDARY)

    def test_starting_twice_notifies_once(self) -> None:
        self.field.start_recording()
        self.field.start_recording()
        self.assertEqual(self.events, ["start"])

    def test_clicking_the_field_starts_recording(self) -> None:
        self.field.frame._binds["<Button-1>"](key_event(0))
        self.assertTrue(self.field.recording)

    def test_clicking_a_cap_starts_recording(self) -> None:
        self.field._cap_widgets[0]._binds["<Button-1>"](key_event(0))
        self.assertTrue(self.field.recording)

    def test_key_events_are_bound_on_the_field(self) -> None:
        for sequence in ("<KeyPress>", "<KeyRelease>", "<FocusOut>", "<Button-1>"):
            self.assertIn(sequence, self.field.frame._binds)

    # --- live modifiers ------------------------------------------------------

    def test_held_modifiers_appear_live_and_disappear_on_release(self) -> None:
        self.field.start_recording()

        self._press(VK_CTRL)
        self.assertEqual(self.field.displayed_tokens, ["Ctrl"])
        self._press(VK_ALT)
        self.assertEqual(self.field.displayed_tokens, ["Ctrl", "Alt"])
        self._release(VK_CTRL)
        self.assertEqual(self.field.displayed_tokens, ["Alt"])
        self._release(VK_ALT)
        self.assertEqual(self.field.displayed_tokens, [])
        self.assertEqual(self.field._cap_widgets[0]._config["text"], "Press keys…")

    def test_live_modifier_caps_have_accent_tint(self) -> None:
        self.field.start_recording()
        self._press(VK_SHIFT)
        cap = self.field._cap_widgets[0]
        self.assertEqual(cap._config["bg"], recorder_mod.ACCENT_TINT_BG)
        self.assertEqual(cap._config["highlightbackground"], recorder_mod.ACCENT_PRIMARY)

    def test_left_and_right_modifier_codes_are_recognised(self) -> None:
        self.field.start_recording()
        self._press(0xA2, 0xA5)  # Ctrl_L, Alt_R
        self.assertEqual(self.field.displayed_tokens, ["Ctrl", "Alt"])
        self._release(0xA2)
        self.assertEqual(self.field.displayed_tokens, ["Alt"])

    def test_modifier_alone_never_submits(self) -> None:
        self.field.start_recording()
        self._press(VK_CTRL, VK_SHIFT)
        self.assertEqual(self.submitted, [])
        self.assertTrue(self.field.recording)

    def test_repeated_modifier_keydown_does_not_rebuild_caps(self) -> None:
        self.field.start_recording()
        self._press(VK_CTRL)
        caps = list(self.field._cap_widgets)
        self._press(VK_CTRL)
        self.assertEqual(self.field._cap_widgets, caps)

    def test_modifier_events_ignored_when_not_recording(self) -> None:
        self._press(VK_CTRL)
        self.assertEqual(self.field.displayed_tokens, ["F4"])

    # --- completing ----------------------------------------------------------

    def test_first_non_modifier_keydown_submits_combo_and_finishes(self) -> None:
        self.field.start_recording()
        self._press(VK_CTRL, VK_ALT, VK_Q)

        self.assertEqual(self.submitted, [HotkeyCombo(frozenset({"ctrl", "alt"}), "q")])
        self.assertFalse(self.field.recording)
        self.assertEqual(self.field.combo, HotkeyCombo(frozenset({"ctrl", "alt"}), "q"))
        self.assertEqual(self.field.displayed_tokens, ["Ctrl", "Alt", "Q"])
        self.assertEqual(self.events, ["start", "stop:True"])
        self.assertEqual(self.field.frame._config["highlightbackground"], recorder_mod.BUTTON_BORDER)

    def test_function_key_alone_completes(self) -> None:
        self.field.start_recording()
        self._press(0x77)  # F8
        self.assertEqual(self.field.combo, HotkeyCombo(frozenset(), "f8"))

    def test_rejected_combo_keeps_recording_and_previous_combo(self) -> None:
        self.accept = False
        self.field.start_recording()
        self._press(VK_Q)

        self.assertEqual(self.submitted, [HotkeyCombo(frozenset(), "q")])
        self.assertTrue(self.field.recording)
        self.assertEqual(self.field.combo, parse_hotkey("F4"))
        self.assertEqual(self.events, ["start"])

    def test_user_can_try_again_after_a_rejected_combo(self) -> None:
        self.accept = False
        self.field.start_recording()
        self._press(VK_Q)
        self.accept = True
        self._press(VK_CTRL, VK_Q)

        self.assertFalse(self.field.recording)
        self.assertEqual(self.field.combo, HotkeyCombo(frozenset({"ctrl"}), "q"))

    def test_unsupported_key_is_submitted_as_none(self) -> None:
        self.accept = False
        self.field.start_recording()
        self._press(VK_CAPSLOCK)
        self.assertEqual(self.submitted, [None])
        self.assertTrue(self.field.recording)

    def test_exception_in_submit_ends_recording_and_propagates(self) -> None:
        def boom(_combo: Optional[HotkeyCombo]) -> bool:
            raise RuntimeError("save failed")

        field = HotkeyRecorderField(
            self.parent, combo=parse_hotkey("F4"), on_submit=boom,
            on_stop=lambda committed: self.events.append(f"stop:{committed}"),
        )
        field.start_recording()
        with self.assertRaises(RuntimeError):
            field.on_key_press(key_event(VK_F4))
        self.assertFalse(field.recording)
        self.assertEqual(self.events, ["stop:False"])

    # --- cancelling ----------------------------------------------------------

    def test_escape_cancels_and_restores_previous_combo(self) -> None:
        self.field.start_recording()
        self._press(VK_ESC)

        self.assertFalse(self.field.recording)
        self.assertEqual(self.submitted, [])
        self.assertEqual(self.field.combo, parse_hotkey("F4"))
        self.assertEqual(self.field.displayed_tokens, ["F4"])
        self.assertEqual(self.events, ["start", "stop:False"])
        self.assertEqual(self.field.frame._config["highlightbackground"], recorder_mod.BUTTON_BORDER)

    def test_escape_with_modifier_is_submitted_not_cancelled(self) -> None:
        self.accept = False
        self.field.start_recording()
        self._press(VK_CTRL, VK_ESC)
        self.assertEqual(self.submitted, [HotkeyCombo(frozenset({"ctrl"}), "escape")])
        self.assertTrue(self.field.recording)

    def test_focus_out_cancels(self) -> None:
        self.field.start_recording()
        self._press(VK_CTRL)
        self.field.on_focus_out(key_event(0))

        self.assertFalse(self.field.recording)
        self.assertEqual(self.field.displayed_tokens, ["F4"])
        self.assertEqual(self.events, ["start", "stop:False"])

    def test_destroying_the_field_while_recording_cancels(self) -> None:
        self.field.start_recording()
        self.field.frame._binds["<Destroy>"](key_event(0, widget=self.field.frame))
        self.assertFalse(self.field.recording)
        self.assertEqual(self.events, ["start", "stop:False"])

    def test_cancel_when_idle_is_a_noop(self) -> None:
        self.field.cancel()
        self.assertEqual(self.events, [])

    def test_restarting_after_cancel_works(self) -> None:
        self.field.start_recording()
        self.field.cancel()
        self.field.start_recording()
        self.assertTrue(self.field.recording)
        self.assertEqual(self.events, ["start", "stop:False", "start"])

    def test_held_modifiers_reset_between_recordings(self) -> None:
        self.field.start_recording()
        self._press(VK_CTRL)
        self.field.cancel()
        self.field.start_recording()
        self.assertEqual(self.field.displayed_tokens, [])

    # --- event return values -------------------------------------------------

    def test_handlers_return_break_while_recording(self) -> None:
        self.field.start_recording()
        self.assertEqual(self.field.on_key_press(key_event(VK_CTRL)), "break")
        self.assertEqual(self.field.on_key_press(key_event(0x79)), "break")  # F10 completes
        self.field.start_recording()
        self.assertEqual(self.field.on_key_release(key_event(VK_CTRL)), "break")
        self.assertEqual(self.field.on_key_press(key_event(VK_ALT)), "break")

    def test_bound_handlers_return_break_for_alt_and_f10(self) -> None:
        self.accept = False
        self.field.start_recording()
        press = self.field.frame._binds["<KeyPress>"]
        self.assertEqual(press(key_event(VK_ALT)), "break")
        self.assertEqual(press(key_event(0x79)), "break")

    def test_handlers_do_not_swallow_events_when_idle(self) -> None:
        self.assertIsNone(self.field.on_key_press(key_event(VK_Q)))
        self.assertIsNone(self.field.on_key_release(key_event(VK_Q)))

    def test_rendering_survives_a_destroyed_widget(self) -> None:
        def broken_destroy() -> None:
            raise RuntimeError("widget gone")

        self.field._cap_widgets[0].destroy = broken_destroy  # type: ignore[method-assign]
        self.field.set_combo(parse_hotkey("F5"))  # must not raise
        self.assertEqual(self.field.combo, parse_hotkey("F5"))


class TestWidgetContainment(unittest.TestCase):
    def test_widget_inside_container_by_path(self) -> None:
        container = MockWidget()
        child = MockWidget(container)
        grandchild = MockWidget(child)
        self.assertTrue(widget_is_within(container, container))
        self.assertTrue(widget_is_within(grandchild, container))

    def test_sibling_with_similar_path_prefix_is_outside(self) -> None:
        container = MagicMock()
        container.__str__ = lambda self: ".a.b"
        other = MagicMock()
        other.__str__ = lambda self: ".a.bc"
        self.assertFalse(widget_is_within(other, container))

    def test_none_is_never_within(self) -> None:
        self.assertFalse(widget_is_within(None, MockWidget()))


if __name__ == "__main__":
    unittest.main()
