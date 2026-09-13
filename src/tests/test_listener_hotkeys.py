"""
Unit tests for QPaste GlobalKeyboardListener configurable hotkey dispatching.
Tests default hotkeys, dynamic reload, fallback behavior on invalid hotkeys,
and ShortcutHandler notepad toggle handling.
"""

import os
import sys
import tempfile
import unittest
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock

# Ensure src directory is on sys.path for direct unittest invocation
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig
from core.hotkey_parser import HotkeyCombo
from core.listener import GlobalKeyboardListener, ShortcutHandler
from core.state import AppState


class MockKey:
    """Mock representing pynput.keyboard.Key."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Key.{self.name}"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, MockKey):
            return self.name == other.name
        return False

    def __hash__(self) -> int:
        return hash(("MockKey", self.name))


class MockKeyCode:
    """Mock representing pynput.keyboard.KeyCode."""

    def __init__(self, char: Optional[str] = None, vk: Optional[int] = None) -> None:
        self.char = char
        self.vk = vk

    def __repr__(self) -> str:
        return f"KeyCode(char={self.char!r}, vk={self.vk})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, MockKeyCode):
            return self.char == other.char and self.vk == other.vk
        return False

    def __hash__(self) -> int:
        return hash(("MockKeyCode", self.char, self.vk))


class TestListenerHotkeys(unittest.TestCase):
    """Tests GlobalKeyboardListener hotkey dispatching, dynamic reload, and fallbacks."""

    def setUp(self) -> None:
        self.temp_dir: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.config_path: str = os.path.join(self.temp_dir.name, "config.json")
        self.state = AppState(initial_active=True)
        self.queue = ClipboardQueue()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_shortcut_handler_handle_toggle_notepad_callback(self) -> None:
        """Given a ShortcutHandler with notepad callback, When handle_toggle_notepad is called, callback is invoked."""
        notepad_invoked = [False]

        def on_toggle_notepad() -> None:
            notepad_invoked[0] = True

        handler = ShortcutHandler(
            state=self.state,
            queue=self.queue,
            on_notepad_toggle_callback=on_toggle_notepad,
        )

        handler.handle_toggle_notepad()
        self.assertTrue(notepad_invoked[0])

    def test_shortcut_handler_handle_toggle_notepad_notification(self) -> None:
        """Given a ShortcutHandler without notepad callback, When handle_toggle_notepad is called, notification is sent."""
        notifications: List[Tuple[str, str]] = []

        def on_notify(msg: str, tag: str) -> None:
            notifications.append((msg, tag))

        handler = ShortcutHandler(
            state=self.state,
            queue=self.queue,
            on_notify_callback=on_notify,
        )

        handler.handle_toggle_notepad()
        self.assertEqual(notifications, [("QPaste : Notepad", "notepad")])

    def test_default_hotkeys_dispatching(self) -> None:
        """Given default configuration, When F4, Shift+F4, or F3 are pressed, appropriate handlers are called."""
        handler = ShortcutHandler(state=self.state, queue=self.queue)
        handler.handle_f4 = MagicMock()
        handler.handle_shift_f4 = MagicMock()
        handler.handle_toggle_notepad = MagicMock()

        listener = GlobalKeyboardListener(handler=handler)

        self.assertEqual(listener._toggle_queue_combo, HotkeyCombo(frozenset(), "f4"))
        self.assertEqual(listener._clear_queue_combo, HotkeyCombo(frozenset({"shift"}), "f4"))
        self.assertEqual(listener._toggle_notepad_combo, HotkeyCombo(frozenset(), "f3"))

        # Test F4 (toggle queue)
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        handler.handle_f4.assert_called_once()
        handler.handle_shift_f4.assert_not_called()
        handler.handle_toggle_notepad.assert_not_called()

        handler.handle_f4.reset_mock()

        # Test Shift+F4 (clear queue)
        listener._on_press(MockKey("shift_l"))
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        listener._on_release(MockKey("shift_l"))
        handler.handle_shift_f4.assert_called_once()
        handler.handle_f4.assert_not_called()
        handler.handle_toggle_notepad.assert_not_called()

        handler.handle_shift_f4.reset_mock()

        # Test F3 (toggle notepad)
        listener._on_press(MockKey("f3"))
        listener._on_release(MockKey("f3"))
        handler.handle_toggle_notepad.assert_called_once()
        handler.handle_f4.assert_not_called()
        handler.handle_shift_f4.assert_not_called()

    def test_dynamic_reload_hotkeys(self) -> None:
        """Given a listener with AppConfig, When hotkeys are changed and reload_hotkeys is called, new combos dispatch."""
        config = AppConfig(config_path=self.config_path)
        handler = ShortcutHandler(state=self.state, queue=self.queue, config=config)
        handler.handle_f4 = MagicMock()
        handler.handle_shift_f4 = MagicMock()
        handler.handle_toggle_notepad = MagicMock()

        listener = GlobalKeyboardListener(handler=handler, config=config)

        # Reconfigure hotkeys
        config.set_hotkey("toggle_queue", "F8")
        config.set_hotkey("clear_queue", "Ctrl+Shift+C")
        config.set_hotkey("toggle_notepad", "Ctrl+Alt+N")

        # Reload hotkeys
        listener.reload_hotkeys()

        self.assertEqual(listener._toggle_queue_combo, HotkeyCombo(frozenset(), "f8"))
        self.assertEqual(listener._clear_queue_combo, HotkeyCombo(frozenset({"ctrl", "shift"}), "c"))
        self.assertEqual(listener._toggle_notepad_combo, HotkeyCombo(frozenset({"ctrl", "alt"}), "n"))

        # Old hotkeys (F4, Shift+F4, F3) should no longer trigger
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        handler.handle_f4.assert_not_called()

        listener._on_press(MockKey("shift_l"))
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        listener._on_release(MockKey("shift_l"))
        handler.handle_shift_f4.assert_not_called()

        listener._on_press(MockKey("f3"))
        listener._on_release(MockKey("f3"))
        handler.handle_toggle_notepad.assert_not_called()

        # New hotkey: F8 -> handle_f4
        listener._on_press(MockKey("f8"))
        listener._on_release(MockKey("f8"))
        handler.handle_f4.assert_called_once()
        handler.handle_f4.reset_mock()

        # New hotkey: Ctrl+Shift+C -> handle_shift_f4
        listener._on_press(MockKey("ctrl_l"))
        listener._on_press(MockKey("shift_r"))
        listener._on_press(MockKeyCode(char="c", vk=67))
        listener._on_release(MockKeyCode(char="c", vk=67))
        listener._on_release(MockKey("shift_r"))
        listener._on_release(MockKey("ctrl_l"))
        handler.handle_shift_f4.assert_called_once()
        handler.handle_shift_f4.reset_mock()

        # New hotkey: Ctrl+Alt+N -> handle_toggle_notepad
        listener._on_press(MockKey("ctrl_l"))
        listener._on_press(MockKey("alt_l"))
        listener._on_press(MockKeyCode(char="n", vk=78))
        listener._on_release(MockKeyCode(char="n", vk=78))
        listener._on_release(MockKey("alt_l"))
        listener._on_release(MockKey("ctrl_l"))
        handler.handle_toggle_notepad.assert_called_once()

    def test_invalid_malformed_hotkeys_fallback(self) -> None:
        """Given invalid or malformed hotkey strings, When reload_hotkeys is called, combos gracefully fall back to defaults."""
        config = AppConfig(config_path=self.config_path)
        handler = ShortcutHandler(state=self.state, queue=self.queue, config=config)
        handler.handle_f4 = MagicMock()
        handler.handle_shift_f4 = MagicMock()
        handler.handle_toggle_notepad = MagicMock()

        listener = GlobalKeyboardListener(handler=handler, config=config)

        # Set invalid hotkeys
        config.set_hotkey("toggle_queue", "InvalidKeyCombo123")
        config.set_hotkey("clear_queue", "Ctrl+Alt+InvalidKeyXYZ")
        config.set_hotkey("toggle_notepad", "")

        # Reload should not raise any exception
        listener.reload_hotkeys()

        # Should fall back to default combos
        self.assertEqual(listener._toggle_queue_combo, HotkeyCombo(frozenset(), "f4"))
        self.assertEqual(listener._clear_queue_combo, HotkeyCombo(frozenset({"shift"}), "f4"))
        self.assertEqual(listener._toggle_notepad_combo, HotkeyCombo(frozenset(), "f3"))

        # Default hotkeys should work
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        handler.handle_f4.assert_called_once()

        listener._on_press(MockKey("shift_l"))
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        listener._on_release(MockKey("shift_l"))
        handler.handle_shift_f4.assert_called_once()

        listener._on_press(MockKey("f3"))
        listener._on_release(MockKey("f3"))
        handler.handle_toggle_notepad.assert_called_once()

    def test_key_releases_and_partial_modifiers(self) -> None:
        """Given active modifier keys, When releasing modifier keys, hotkey matching reflects updated state."""
        handler = ShortcutHandler(state=self.state, queue=self.queue)
        handler.handle_f4 = MagicMock()
        handler.handle_shift_f4 = MagicMock()

        listener = GlobalKeyboardListener(handler=handler)

        # Hold Shift
        listener._on_press(MockKey("shift_l"))
        # Press F4 -> Shift+F4 triggers handle_shift_f4
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        handler.handle_shift_f4.assert_called_once()
        handler.handle_f4.assert_not_called()

        handler.handle_shift_f4.reset_mock()

        # Release Shift
        listener._on_release(MockKey("shift_l"))

        # Press F4 -> F4 triggers handle_f4
        listener._on_press(MockKey("f4"))
        listener._on_release(MockKey("f4"))
        handler.handle_f4.assert_called_once()
        handler.handle_shift_f4.assert_not_called()


if __name__ == "__main__":
    unittest.main()
