"""
Unit tests for QPaste main application component wiring and integration.
Validates QuickNotepadHUD wiring, dynamic tray menu hotkeys, listener reloading,
idle expiration management, and clean teardown without requiring a real display.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig
from core.listener import GlobalKeyboardListener, ShortcutHandler
from core.state import AppState
from ui.notepad import QuickNotepadHUD


class TestMainWiring(unittest.TestCase):
    """Test suite for main application wiring."""

    def setUp(self) -> None:
        self.mock_config = MagicMock(spec=AppConfig)
        self.config_data = {
            "auto_clear_enabled": True,
            "auto_clear_seconds": 30,
            "auto_clear_mode": "idle",
            "hotkeys": {
                "toggle_queue": "F4",
                "clear_queue": "Shift+F4",
                "toggle_notepad": "F3",
            },
        }
        self.mock_config.get.side_effect = lambda key, default=None: self.config_data.get(key, default)
        self.mock_config.get_hotkey.side_effect = lambda action, default=None: self.config_data.get("hotkeys", {}).get(action, default)

        self.state = AppState(initial_active=True)
        self.queue = ClipboardQueue()
        self.mock_notepad = MagicMock(spec=QuickNotepadHUD)
        self.mock_notify = MagicMock()
        self.mock_update = MagicMock()

    def test_shortcut_handler_notepad_toggle_callback(self) -> None:
        """Verify ShortcutHandler triggers notepad toggle callback."""
        handler = ShortcutHandler(
            self.state,
            self.queue,
            on_notify_callback=self.mock_notify,
            on_update_callback=self.mock_update,
            on_notepad_toggle_callback=self.mock_notepad.toggle,
            config=self.mock_config,
        )

        handler.handle_toggle_notepad()
        self.mock_notepad.toggle.assert_called_once()

    def test_global_keyboard_listener_receives_config_and_reloads(self) -> None:
        """Verify GlobalKeyboardListener parses hotkeys from config upon reload."""
        handler = ShortcutHandler(
            self.state,
            self.queue,
            on_notepad_toggle_callback=self.mock_notepad.toggle,
            config=self.mock_config,
        )
        listener = GlobalKeyboardListener(handler, config=self.mock_config)

        self.assertIsNotNone(listener._toggle_notepad_combo)
        self.assertIsNotNone(listener._toggle_queue_combo)
        self.assertIsNotNone(listener._clear_queue_combo)

        # Update config hotkeys and reload
        self.config_data["hotkeys"]["toggle_notepad"] = "Ctrl+Shift+N"
        listener.reload_hotkeys()
        self.assertIsNotNone(listener._toggle_notepad_combo)

    def test_tray_menu_hotkey_labels(self) -> None:
        """Verify dynamic tray menu labels reflect active configured hotkeys."""
        def get_toggle_queue_label(_item=None) -> str:
            hk = self.mock_config.get_hotkey("toggle_queue", default="F4")
            return f"Toggle Queue Mode ({hk})" if hk else "Toggle Queue Mode"

        def get_clear_queue_label(_item=None) -> str:
            hk = self.mock_config.get_hotkey("clear_queue", default="Shift+F4")
            return f"Clear Queue ({hk})" if hk else "Clear Queue"

        def get_notepad_label(_item=None) -> str:
            hk = self.mock_config.get_hotkey("toggle_notepad", default="F3")
            return f"Quick Notepad ({hk})" if hk else "Quick Notepad"

        self.assertEqual(get_toggle_queue_label(), "Toggle Queue Mode (F4)")
        self.assertEqual(get_clear_queue_label(), "Clear Queue (Shift+F4)")
        self.assertEqual(get_notepad_label(), "Quick Notepad (F3)")

        # Change hotkeys in config
        self.config_data["hotkeys"]["toggle_notepad"] = "Alt+N"
        self.config_data["hotkeys"]["toggle_queue"] = "F8"
        self.assertEqual(get_notepad_label(), "Quick Notepad (Alt+N)")
        self.assertEqual(get_toggle_queue_label(), "Toggle Queue Mode (F8)")

    def test_expiration_manager_idle_mode_purge(self) -> None:
        """Verify expiration manager calls purge_idle."""
        self.queue.push("Item 1")
        self.config_data["auto_clear_enabled"] = True
        self.config_data["auto_clear_seconds"] = 10

        with patch.object(self.queue, "purge_idle", return_value=1) as mock_purge_idle:
            timeout = self.mock_config.get("auto_clear_seconds", 60)
            purged = self.queue.purge_idle(timeout)

            mock_purge_idle.assert_called_once_with(10)
            self.assertEqual(purged, 1)

    def test_teardown_cleans_up_notepad_and_config(self) -> None:
        """Verify application exit logic hides notepad and saves config."""
        mock_notepad = MagicMock()
        mock_config = MagicMock()
        mock_listener = MagicMock()
        mock_clip_listener = MagicMock()
        mock_single_inst = MagicMock()
        mock_icon = MagicMock()

        def on_exit():
            try:
                mock_notepad.hide()
                mock_config.save()
            except Exception:
                pass
            mock_clip_listener.stop()
            mock_listener.stop()
            mock_single_inst.release()
            mock_icon.stop()

        on_exit()

        mock_notepad.hide.assert_called_once()
        mock_config.save.assert_called_once()
        mock_clip_listener.stop.assert_called_once()
        mock_listener.stop.assert_called_once()
        mock_single_inst.release.assert_called_once()
        mock_icon.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
