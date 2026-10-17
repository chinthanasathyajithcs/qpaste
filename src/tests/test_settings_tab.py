"""
Unit tests for SettingsTab GUI component.
Tests Auto-Clear controls, press-to-record hotkey rows, validation, reset, and callbacks.
Gracefully mocks Tkinter for headless environments.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from typing import Any, List
from unittest.mock import MagicMock

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.config import AppConfig
from core.hotkey_parser import parse_hotkey
import ui.hotkey_recorder as recorder_mod
import ui.settings_tab as settings_mod
from ui.settings_tab import SettingsTab, HOTKEY_ACTIONS
from tk_mocks import MockWidget, key_event, make_mock_tk

VK_SHIFT, VK_CTRL, VK_ALT = 0x10, 0x11, 0x12
VK_ESC, VK_C, VK_V, VK_Q, VK_F3, VK_F4, VK_F8 = 0x1B, 0x43, 0x56, 0x51, 0x72, 0x73, 0x77
VK_CAPSLOCK = 0x14


class TestSettingsTab(unittest.TestCase):
    """Test suite for SettingsTab component."""

    def setUp(self) -> None:
        self.temp_dir: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.config_path: str = os.path.join(self.temp_dir.name, "config.json")
        self.config = AppConfig(config_path=self.config_path)

        self.mock_tk = make_mock_tk()
        self.orig_tk = settings_mod.tk
        self.orig_recorder_tk = recorder_mod.tk
        settings_mod.tk = self.mock_tk
        recorder_mod.tk = self.mock_tk

        self.parent_mock = MockWidget()
        self.hotkeys_changed_calls = 0
        self.recording_states: List[bool] = []

    def tearDown(self) -> None:
        settings_mod.tk = self.orig_tk
        recorder_mod.tk = self.orig_recorder_tk
        self.temp_dir.cleanup()

    def _on_hotkeys_changed(self) -> None:
        self.hotkeys_changed_calls += 1

    def _make_tab(self) -> SettingsTab:
        return SettingsTab(
            self.parent_mock,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
            on_recording_changed=self.recording_states.append,
        )

    def _record(self, tab: SettingsTab, action: str, *keycodes: int) -> None:
        """Starts recording `action` (if needed) and presses the given key codes in order."""
        field = tab.hotkey_fields[action]
        field.start_recording()
        for code in keycodes:
            field.on_key_press(key_event(code))

    def _error_text(self, tab: SettingsTab) -> str:
        return tab.error_label._config.get("text", "")

    # --- initialization ---------------------------------------------------------

    def test_initialization_defaults_from_config(self) -> None:
        """Given a fresh AppConfig, SettingsTab loads default values for auto-clear and hotkeys."""
        tab = self._make_tab()

        self.assertFalse(tab.auto_clear_var.get())
        self.assertEqual(tab.duration_var.get(), "1 Minute")
        self.assertEqual(tab.hotkey_fields["toggle_queue"].displayed_tokens, ["F4"])
        self.assertEqual(tab.hotkey_fields["clear_queue"].displayed_tokens, ["Shift", "F4"])
        self.assertEqual(tab.hotkey_fields["toggle_notepad"].displayed_tokens, ["F3"])

    def test_each_action_has_a_row_with_record_and_reset_controls(self) -> None:
        tab = self._make_tab()
        for action, _label, _default in HOTKEY_ACTIONS:
            self.assertIn(action, tab.hotkey_fields)
            self.assertEqual(tab.record_buttons[action]._config["text"], "Record")
            self.assertEqual(tab.reset_buttons[action]._config["text"], "↺")

    def test_configured_win_combo_displays_as_caps(self) -> None:
        self.config.set_hotkey("toggle_notepad", "Win+V")
        tab = self._make_tab()
        self.assertEqual(tab.hotkey_fields["toggle_notepad"].displayed_tokens, ["Win", "V"])

    def test_unparsable_stored_hotkey_shows_the_default_the_listener_falls_back_to(self) -> None:
        self.config.set_hotkey("toggle_queue", "NotAKey")
        tab = self._make_tab()
        self.assertEqual(tab.hotkey_fields["toggle_queue"].displayed_tokens, ["F4"])

    def test_record_button_starts_recording_that_row(self) -> None:
        tab = self._make_tab()
        tab.record_buttons["clear_queue"].click()
        self.assertTrue(tab.hotkey_fields["clear_queue"].recording)
        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)

    # --- auto clear -------------------------------------------------------------

    def test_auto_clear_settings_change_persists_to_config(self) -> None:
        """When auto-clear checkbox or duration changes, AppConfig is updated."""
        tab = self._make_tab()

        tab.auto_clear_var.set(True)
        tab.duration_var.set("5 Minutes")
        tab._on_auto_clear_changed()

        self.assertTrue(self.config.get("auto_clear_enabled"))
        self.assertEqual(self.config.get("auto_clear_seconds"), 300)
        self.assertEqual(self.config.get("auto_clear_mode"), "idle")

        # Verify disk persistence
        reloaded = AppConfig(config_path=self.config_path)
        self.assertTrue(reloaded.get("auto_clear_enabled"))
        self.assertEqual(reloaded.get("auto_clear_seconds"), 300)
        self.assertEqual(reloaded.get("auto_clear_mode"), "idle")

    # --- recording lifecycle and pausing ----------------------------------------

    def test_start_recording_pauses_global_hotkeys(self) -> None:
        tab = self._make_tab()
        tab.hotkey_fields["toggle_queue"].start_recording()
        self.assertEqual(self.recording_states, [True])

    def test_valid_combo_saves_formatted_hotkey_and_resumes_hotkeys(self) -> None:
        """When a valid combo is recorded, format_hotkey output is stored and callbacks fire."""
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_CTRL, VK_Q)

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "Ctrl+Q")
        self.assertEqual(self.hotkeys_changed_calls, 1)
        self.assertEqual(self.recording_states, [True, False])
        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)
        self.assertEqual(tab.hotkey_fields["toggle_queue"].displayed_tokens, ["Ctrl", "Q"])
        self.assertEqual(self._error_text(tab), "")

    def test_saved_hotkey_round_trips_through_parse_hotkey(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_notepad", VK_CTRL, VK_SHIFT, VK_ALT, 0x28)  # Ctrl+Shift+Alt+Down
        stored = self.config.get_hotkey("toggle_notepad")
        self.assertEqual(stored, "Ctrl+Shift+Alt+Down")
        self.assertIsNotNone(parse_hotkey(stored))

    def test_partial_input_is_never_saved(self) -> None:
        """Holding only modifiers (the way to Ctrl+...) must not change or reload any hotkey."""
        tab = self._make_tab()
        field = tab.hotkey_fields["toggle_queue"]
        field.start_recording()
        field.on_key_press(key_event(VK_CTRL))
        field.on_key_release(key_event(VK_CTRL))

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(self.hotkeys_changed_calls, 0)

    def test_plain_letter_is_rejected_and_recording_continues(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_C)

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(self.hotkeys_changed_calls, 0)
        self.assertIn("Ctrl", self._error_text(tab))
        self.assertEqual(tab.error_label._config["fg"], settings_mod.ERROR_COLOR)
        self.assertTrue(tab.hotkey_fields["toggle_queue"].recording)
        self.assertEqual(self.recording_states, [True])

    def test_shift_letter_is_rejected(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_SHIFT, VK_Q)
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertTrue(tab.hotkey_fields["toggle_queue"].recording)

    def test_reserved_combos_are_rejected(self) -> None:
        tab = self._make_tab()
        field = tab.hotkey_fields["toggle_queue"]
        field.start_recording()
        for modifiers, key in (((VK_CTRL,), VK_C), ((VK_CTRL,), VK_V), ((VK_ALT,), VK_F4)):
            for code in modifiers:
                field.on_key_press(key_event(code))
            field.on_key_press(key_event(key))
            self.assertIn("reserved", self._error_text(tab))
            for code in modifiers:
                field.on_key_release(key_event(code))

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertTrue(field.recording)

    def test_duplicate_combo_names_the_other_action(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_F3)  # F3 belongs to Quick Notepad

        self.assertEqual(self._error_text(tab), "Already used by Quick Notepad")
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertTrue(tab.hotkey_fields["toggle_queue"].recording)

    def test_unsupported_key_shows_error_and_keeps_recording(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_CAPSLOCK)

        self.assertNotEqual(self._error_text(tab), "")
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertTrue(tab.hotkey_fields["toggle_queue"].recording)

    def test_valid_combo_after_an_error_saves_and_clears_the_error(self) -> None:
        tab = self._make_tab()
        field = tab.hotkey_fields["toggle_queue"]
        self._record(tab, "toggle_queue", VK_C)
        self.assertNotEqual(self._error_text(tab), "")

        field.on_key_press(key_event(VK_F8))

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F8")
        self.assertEqual(self._error_text(tab), "")
        self.assertEqual(self.recording_states, [True, False])

    def test_altgr_risky_combo_saves_with_amber_warning(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_CTRL, VK_ALT, VK_Q)

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "Ctrl+Alt+Q")
        self.assertEqual(self.hotkeys_changed_calls, 1)
        self.assertIn("AltGr", self._error_text(tab))
        self.assertEqual(tab.error_label._config["fg"], settings_mod.WARNING_COLOR)
        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)

    def test_warning_color_is_replaced_by_error_color_for_next_error(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_CTRL, VK_ALT, VK_Q)
        self._record(tab, "toggle_notepad", VK_C)
        self.assertEqual(tab.error_label._config["fg"], settings_mod.ERROR_COLOR)

    def test_escape_cancels_without_saving_and_resumes_hotkeys(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_C)  # leaves an error showing
        tab.hotkey_fields["toggle_queue"].on_key_press(key_event(VK_ESC))

        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)
        self.assertEqual(tab.hotkey_fields["toggle_queue"].displayed_tokens, ["F4"])
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(self.hotkeys_changed_calls, 0)
        self.assertEqual(self.recording_states, [True, False])
        self.assertEqual(self._error_text(tab), "")

    def test_focus_out_cancels_and_resumes_hotkeys(self) -> None:
        tab = self._make_tab()
        tab.hotkey_fields["toggle_queue"].start_recording()
        tab.hotkey_fields["toggle_queue"].on_focus_out(key_event(0))

        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)
        self.assertEqual(self.recording_states, [True, False])

    def test_cancel_recording_is_public_and_resumes_hotkeys(self) -> None:
        tab = self._make_tab()
        tab.hotkey_fields["clear_queue"].start_recording()
        tab.cancel_recording()
        self.assertFalse(tab.hotkey_fields["clear_queue"].recording)
        self.assertEqual(self.recording_states, [True, False])

    def test_cancel_recording_when_idle_does_nothing(self) -> None:
        tab = self._make_tab()
        tab.cancel_recording()
        self.assertEqual(self.recording_states, [])

    def test_only_one_row_records_at_a_time(self) -> None:
        tab = self._make_tab()
        tab.hotkey_fields["toggle_queue"].start_recording()
        tab.hotkey_fields["clear_queue"].start_recording()

        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)
        self.assertTrue(tab.hotkey_fields["clear_queue"].recording)
        self.assertEqual(self.recording_states, [True])  # stays paused throughout the switch

        tab.hotkey_fields["clear_queue"].on_focus_out(key_event(0))
        self.assertEqual(self.recording_states, [True, False])

    def test_exception_while_saving_still_resumes_hotkeys(self) -> None:
        tab = self._make_tab()
        self.config.set_hotkey = MagicMock(side_effect=OSError("disk full"))  # type: ignore[method-assign]
        with self.assertRaises(OSError):
            self._record(tab, "toggle_queue", VK_CTRL, VK_Q)
        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)
        self.assertEqual(self.recording_states, [True, False])

    def test_failing_recording_callback_does_not_break_recording(self) -> None:
        def boom(_paused: bool) -> None:
            raise RuntimeError("listener gone")

        tab = SettingsTab(self.parent_mock, config=self.config, on_recording_changed=boom)
        self._record(tab, "toggle_queue", VK_CTRL, VK_Q)
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "Ctrl+Q")

    def test_click_elsewhere_in_window_cancels_recording(self) -> None:
        tab = self._make_tab()
        tab.hotkey_fields["toggle_queue"].start_recording()
        tab._on_window_click(key_event(1, widget=MockWidget()))
        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)
        self.assertEqual(self.recording_states, [True, False])

    def test_click_on_own_field_or_buttons_keeps_recording(self) -> None:
        tab = self._make_tab()
        field = tab.hotkey_fields["toggle_queue"]
        field.start_recording()
        tab._on_window_click(key_event(1, widget=field.frame))
        tab._on_window_click(key_event(1, widget=field._cap_widgets[0]))
        tab._on_window_click(key_event(1, widget=tab.record_buttons["clear_queue"]))
        tab._on_window_click(key_event(1, widget=tab.reset_buttons["toggle_queue"]))
        self.assertTrue(field.recording)

    def test_window_click_while_idle_does_nothing(self) -> None:
        tab = self._make_tab()
        tab._on_window_click(key_event(1, widget=MockWidget()))
        self.assertEqual(self.recording_states, [])

    # --- per-row reset ----------------------------------------------------------

    def test_row_reset_restores_only_that_rows_default(self) -> None:
        self.config.set_hotkey("toggle_queue", "Ctrl+Alt+1")
        self.config.set_hotkey("clear_queue", "Ctrl+Alt+2")
        tab = self._make_tab()

        tab.reset_buttons["toggle_queue"].click()

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(self.config.get_hotkey("clear_queue"), "Ctrl+Alt+2")
        self.assertEqual(tab.hotkey_fields["toggle_queue"].displayed_tokens, ["F4"])
        self.assertEqual(tab.hotkey_fields["clear_queue"].displayed_tokens, ["Ctrl", "Alt", "2"])
        self.assertEqual(self.hotkeys_changed_calls, 1)

    def test_row_reset_goes_through_validation(self) -> None:
        self.config.set_hotkey("toggle_queue", "F9")
        self.config.set_hotkey("toggle_notepad", "F4")  # now holds toggle_queue's default
        tab = self._make_tab()

        tab.reset_buttons["toggle_queue"].click()

        self.assertEqual(self._error_text(tab), "Already used by Quick Notepad")
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F9")
        self.assertEqual(tab.hotkey_fields["toggle_queue"].displayed_tokens, ["F9"])
        self.assertEqual(self.hotkeys_changed_calls, 0)

    def test_row_reset_cancels_any_active_recording(self) -> None:
        tab = self._make_tab()
        tab.hotkey_fields["clear_queue"].start_recording()
        tab.reset_buttons["toggle_queue"].click()
        self.assertFalse(tab.hotkey_fields["clear_queue"].recording)
        self.assertEqual(self.recording_states, [True, False])

    # --- reset all --------------------------------------------------------------

    def test_reset_defaults_restores_all_hotkeys_and_triggers_callback(self) -> None:
        """When reset_defaults is clicked, hotkeys revert to F4, Shift+F4, F3 and callback is called."""
        self.config.set_hotkey("toggle_queue", "Ctrl+Alt+1")
        self.config.set_hotkey("clear_queue", "Ctrl+Alt+2")
        self.config.set_hotkey("toggle_notepad", "Ctrl+Alt+3")
        tab = self._make_tab()

        tab.reset_defaults()

        self.assertEqual(self.hotkeys_changed_calls, 1)
        self.assertEqual(tab.hotkey_fields["toggle_queue"].displayed_tokens, ["F4"])
        self.assertEqual(tab.hotkey_fields["clear_queue"].displayed_tokens, ["Shift", "F4"])
        self.assertEqual(tab.hotkey_fields["toggle_notepad"].displayed_tokens, ["F3"])
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(self.config.get_hotkey("clear_queue"), "Shift+F4")
        self.assertEqual(self.config.get_hotkey("toggle_notepad"), "F3")
        self.assertEqual(self._error_text(tab), "")

    def test_reset_defaults_also_resets_auto_clear(self) -> None:
        tab = self._make_tab()
        tab.auto_clear_var.set(True)
        tab.duration_var.set("1 Hour")
        tab._on_auto_clear_changed()

        tab.reset_defaults()

        self.assertFalse(tab.auto_clear_var.get())
        self.assertEqual(tab.duration_var.get(), "1 Minute")
        self.assertFalse(self.config.get("auto_clear_enabled"))
        self.assertEqual(self.config.get("auto_clear_seconds"), 60)

    def test_reset_defaults_cancels_recording_and_clears_error(self) -> None:
        tab = self._make_tab()
        self._record(tab, "toggle_queue", VK_C)  # error showing, still recording

        tab.reset_defaults()

        self.assertFalse(tab.hotkey_fields["toggle_queue"].recording)
        self.assertEqual(self.recording_states, [True, False])
        self.assertEqual(self._error_text(tab), "")

    def test_safe_fallbacks_when_tk_is_none(self) -> None:
        """When tk is None (headless without mock), SettingsTab initializes safely."""
        settings_mod.tk = None
        tab = self._make_tab()
        self.assertIsNotNone(tab.config)
        tab.cancel_recording()
        tab.reset_defaults()
        self.assertEqual(self.hotkeys_changed_calls, 1)


if __name__ == "__main__":
    unittest.main()
