"""
Unit tests for Quick Notepad HUD overlay.
Supports headless execution via Tkinter mocking.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.config import AppConfig
import ui.notepad as notepad_mod
from ui.notepad import (
    QuickNotepadHUD,
    DARK_BG,
    CARD_BG,
    EDITOR_BG,
    ACCENT_PRIMARY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class MockTkEvent:
    """Mock Tkinter event object."""

    def __init__(self, x: int = 0, y: int = 0, x_root: int = 0, y_root: int = 0) -> None:
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root


class TestQuickNotepadHUD(unittest.TestCase):
    """Test suite for QuickNotepadHUD."""

    def setUp(self) -> None:
        self.mock_config = MagicMock(spec=AppConfig)
        self.mock_config.get.side_effect = lambda key, default=None: {
            "notepad_text": "Saved notes test",
            "notepad_geometry": "400x300+100+100",
        }.get(key, default)

        # Setup mock Tkinter environment
        self.mock_tk = MagicMock()
        self.mock_master = MagicMock()
        self.mock_window = MagicMock()
        self.mock_text = MagicMock()

        self.mock_tk.Tk.return_value = self.mock_master
        self.mock_tk.Toplevel.return_value = self.mock_window
        self.mock_tk.Text.return_value = self.mock_text

        # Synchronous execution of after callbacks in base mock
        self.mock_master.after.side_effect = lambda _ms, fn, *args: fn(*args)
        self.mock_window.after.side_effect = lambda _ms, fn, *args: fn(*args)

        # Track viewable state for window
        self._window_viewable = 0
        self.mock_window.deiconify.side_effect = lambda: setattr(self, "_window_viewable", 1)
        self.mock_window.withdraw.side_effect = lambda: setattr(self, "_window_viewable", 0)
        self.mock_window.winfo_viewable.side_effect = lambda: self._window_viewable

        self.mock_tk.WORD = "word"
        self.mock_tk.BOTH = "both"
        self.mock_tk.X = "x"
        self.mock_tk.Y = "y"
        self.mock_tk.TOP = "top"
        self.mock_tk.LEFT = "left"
        self.mock_tk.RIGHT = "right"
        self.mock_tk.FLAT = "flat"

        self.orig_tk = notepad_mod.tk
        notepad_mod.tk = self.mock_tk

    def tearDown(self) -> None:
        notepad_mod.tk = self.orig_tk

    def test_initialization_defaults(self) -> None:
        """Verify HUD initialization with default config."""
        hud = QuickNotepadHUD()
        self.assertIsNotNone(hud.config)
        self.assertIsNone(hud.window)
        self.assertIsNone(hud.text_widget)
        self.assertFalse(hud.is_visible())

    def test_initialization_and_content_loading(self) -> None:
        """Verify HUD builds GUI and loads initial text and geometry from config."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.mock_tk.Toplevel.assert_called_once()
        self.mock_window.overrideredirect.assert_called_with(True)
        self.mock_window.attributes.assert_called_with("-topmost", True)
        self.mock_window.configure.assert_called_with(bg=DARK_BG)
        self.mock_window.geometry.assert_called_with("400x300+100+100")

        self.mock_text.insert.assert_called_with("1.0", "Saved notes test")

    def test_show_and_hide(self) -> None:
        """Verify show and hide lifecycle."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud.show()

        self.mock_window.deiconify.assert_called_once()
        self.mock_window.lift.assert_called_once()
        self.mock_text.focus_set.assert_called_once()
        self.assertTrue(hud.is_visible())

        # Test hide persists content and geometry
        self.mock_text.get.return_value = "Updated note content"
        self.mock_window.geometry.return_value = "450x350+120+120"

        hud.hide()
        self.mock_config.set.assert_any_call("notepad_text", "Updated note content")
        self.mock_config.set.assert_any_call("notepad_geometry", "450x350+120+120")
        self.mock_window.withdraw.assert_called_once()
        self.assertFalse(hud.is_visible())

    def test_toggle(self) -> None:
        """Verify toggle alternates visibility."""
        hud = QuickNotepadHUD(config=self.mock_config)
        self.assertFalse(hud.is_visible())

        hud.toggle()
        self.assertTrue(hud.is_visible())
        self.mock_window.deiconify.assert_called_once()

        hud.toggle()
        self.assertFalse(hud.is_visible())
        self.mock_window.withdraw.assert_called_once()

    def test_text_persistence_on_edit(self) -> None:
        """Verify text persistence and auto-save scheduling on edit."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.mock_text.get.return_value = "Auto-saved text"
        self.mock_text.edit_modified.return_value = True

        hud._on_text_modified(None)
        self.mock_text.edit_modified.assert_called_with(False)
        self.mock_window.after.assert_called_with(300, hud.save_content)

        # Directly invoke save_content
        hud.save_content()
        self.mock_config.set.assert_called_with("notepad_text", "Auto-saved text")

    def test_escape_key_binding_hides_window(self) -> None:
        """Verify Escape key handler triggers hide."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        # Find escape binding on window
        escape_calls = [
            call for call in self.mock_window.bind.call_args_list
            if call[0][0] == "<Escape>"
        ]
        self.assertTrue(len(escape_calls) > 0)
        escape_handler = escape_calls[0][0][1]

        with patch.object(hud, "hide") as mock_hide:
            escape_handler(MockTkEvent())
            mock_hide.assert_called_once()

    def test_drag_handling_and_geometry_save(self) -> None:
        """Verify mouse dragging updates geometry and release persists geometry."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.mock_window.winfo_x.return_value = 100
        self.mock_window.winfo_y.return_value = 100

        # Start drag at root (120, 115) -> offset is (20, 15)
        hud._start_drag(MockTkEvent(x_root=120, y_root=115))
        self.assertEqual(hud._drag_offset_x, 20)
        self.assertEqual(hud._drag_offset_y, 15)

        # Drag motion to root (220, 215) -> new position is (200, 200)
        hud._on_drag(MockTkEvent(x_root=220, y_root=215))
        self.mock_window.geometry.assert_called_with("+200+200")

        # End drag persists geometry
        self.mock_window.geometry.return_value = "400x300+200+200"
        hud.save_geometry()
        self.mock_config.set.assert_called_with("notepad_geometry", "400x300+200+200")

    def test_thread_safe_dispatch(self) -> None:
        """Verify master.after is used for thread safety when master exists."""
        master_mock = MagicMock()
        hud = QuickNotepadHUD(config=self.mock_config, master=master_mock)
        hud.show()
        master_mock.after.assert_called_with(0, hud._show_main_thread)

        hud.hide()
        master_mock.after.assert_called_with(0, hud._hide_main_thread)

    def test_key_release_triggers_auto_save(self) -> None:
        """Verify KeyRelease binding triggers auto-save."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        keyrelease_calls = [
            call for call in self.mock_text.bind.call_args_list
            if call[0][0] == "<KeyRelease>"
        ]
        self.assertTrue(len(keyrelease_calls) > 0)
        key_handler = keyrelease_calls[0][0][1]

        with patch.object(hud, "_schedule_auto_save") as mock_save:
            key_handler(MockTkEvent())
            mock_save.assert_called_once()

    def test_timer_cancel_on_reschedule(self) -> None:
        """Verify pending save timer is cancelled when rescheduled."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        hud._save_timer_id = "timer_123"

        hud._schedule_auto_save()
        self.mock_window.after_cancel.assert_called_with("timer_123")

    def test_safe_fallbacks_when_tk_none(self) -> None:
        """Verify methods execute safely when tk or widgets are None."""
        notepad_mod.tk = None
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        self.assertIsNone(hud.window)

        # Calling save methods when widgets are None should not crash
        hud.save_content()
        hud.save_geometry()
        self.assertFalse(hud.is_visible())


if __name__ == "__main__":
    unittest.main()
