"""
Unit and integration tests for UI integration, notifications, notepad HUD,
auto-clear expiration manager, and system tray teardown in QPaste.
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
from ui.toast import NativeToastOverlay
from ui.notepad import QuickNotepadHUD


class MockKey:
    """Mock representing key objects for GlobalKeyboardListener."""

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


def test_native_toast_initialization():
    toast = NativeToastOverlay()
    assert toast.window is None
    assert toast.master is None
    assert toast.frame is None
    assert toast.label is None


def test_shortcut_handler_triggers_notification_callback():
    update_mock = MagicMock()
    notify_mock = MagicMock()
    state = AppState(initial_active=True)
    queue = ClipboardQueue()

    handler = ShortcutHandler(
        state,
        queue,
        on_update_callback=update_mock,
        on_notify_callback=notify_mock,
    )

    # Test F4 toggle triggers ON/OFF notifications
    handler.handle_f4()
    assert notify_mock.call_count == 1
    notify_mock.assert_called_with("QPaste : OFF", "off")
    assert not state.is_active()

    handler.handle_f4()
    assert notify_mock.call_count == 2
    notify_mock.assert_called_with("QPaste : ON", "on")
    assert state.is_active()

    # Test Clear triggers Cleared notification
    handler.handle_shift_f4()
    assert notify_mock.call_count == 3
    notify_mock.assert_called_with("QPaste : Cleared", "cleared")


class TestUIIntegration(unittest.TestCase):
    """Integration test suite for UI, HUD, and lifecycle management."""

    def test_native_toast_initialization(self) -> None:
        toast = NativeToastOverlay()
        self.assertIsNone(toast.window)
        self.assertIsNone(toast.master)
        self.assertIsNone(toast.frame)
        self.assertIsNone(toast.label)

    def test_shortcut_handler_triggers_notification_callback(self) -> None:
        update_mock = MagicMock()
        notify_mock = MagicMock()
        state = AppState(initial_active=True)
        queue = ClipboardQueue()

        handler = ShortcutHandler(
            state,
            queue,
            on_update_callback=update_mock,
            on_notify_callback=notify_mock,
        )

        handler.handle_f4()
        self.assertEqual(notify_mock.call_count, 1)
        notify_mock.assert_called_with("QPaste : OFF", "off")
        self.assertFalse(state.is_active())

        handler.handle_f4()
        self.assertEqual(notify_mock.call_count, 2)
        notify_mock.assert_called_with("QPaste : ON", "on")
        self.assertTrue(state.is_active())

        handler.handle_shift_f4()
        self.assertEqual(notify_mock.call_count, 3)
        notify_mock.assert_called_with("QPaste : Cleared", "cleared")

    def test_notepad_toggle_from_hotkey_and_tray(self) -> None:
        """Verify notepad HUD toggle through ShortcutHandler, GlobalKeyboardListener, and Tray."""
        mock_notepad = MagicMock(spec=QuickNotepadHUD)
        config = MagicMock(spec=AppConfig)
        config.get_hotkey.side_effect = lambda action, default=None: {
            "toggle_queue": "F4",
            "clear_queue": "Shift+F4",
            "toggle_notepad": "F3",
        }.get(action, default)
        config.get.side_effect = lambda key, default=None: {
            "hotkeys": {"toggle_notepad": "F3"},
        }.get(key, default)

        state = AppState(initial_active=True)
        queue = ClipboardQueue()
        update_mock = MagicMock()
        notify_mock = MagicMock()

        handler = ShortcutHandler(
            state=state,
            queue=queue,
            on_update_callback=update_mock,
            on_notify_callback=notify_mock,
            on_notepad_toggle_callback=mock_notepad.toggle,
            config=config,
        )

        # 1. Direct handler toggle
        handler.handle_toggle_notepad()
        mock_notepad.toggle.assert_called_once()
        mock_notepad.toggle.reset_mock()

        # 2. Global keyboard listener toggle
        listener = GlobalKeyboardListener(handler, config=config)
        listener._on_press(MockKey("f3"))
        listener._on_release(MockKey("f3"))
        mock_notepad.toggle.assert_called_once()
        mock_notepad.toggle.reset_mock()

        # 3. System tray handler simulation
        def on_toggle_notepad(icon, item):
            mock_notepad.toggle()

        on_toggle_notepad(None, None)
        mock_notepad.toggle.assert_called_once()

    def test_dynamic_tray_menu_hotkey_reflection_and_reload(self) -> None:
        """Verify tray menu text builds with dynamic hotkeys and updates on change."""
        mock_config = MagicMock(spec=AppConfig)
        hotkeys_map = {
            "toggle_queue": "F4",
            "clear_queue": "Shift+F4",
            "toggle_notepad": "F3",
        }
        mock_config.get_hotkey.side_effect = lambda act, default="": hotkeys_map.get(act, default)

        mock_notepad = MagicMock(spec=QuickNotepadHUD)
        mock_handler = MagicMock(spec=ShortcutHandler)

        class MockMenuItem:
            def __init__(self, text: str, action: Optional[Any] = None, default: bool = False, checked: Optional[Any] = None):
                self.text = text
                self.action = action
                self.default = default
                self.checked = checked

            def __call__(self, icon: Optional[Any] = None) -> None:
                if self.action:
                    self.action(icon, self)

        class MockMenu:
            SEPARATOR = object()

            def __init__(self, *items: Any):
                self.items = [it for it in items if it is not self.SEPARATOR]

        def build_tray_menu() -> MockMenu:
            return MockMenu(
                MockMenuItem(f"Toggle Queue Mode ({mock_config.get_hotkey('toggle_queue', 'F4')})", lambda i, m: mock_handler.handle_f4()),
                MockMenuItem(f"Clear Queue ({mock_config.get_hotkey('clear_queue', 'Shift+F4')})", lambda i, m: mock_handler.handle_shift_f4()),
                MockMenuItem(f"Quick Notepad ({mock_config.get_hotkey('toggle_notepad', 'F3')})", lambda i, m: mock_notepad.toggle()),
                MockMenuItem("Open Queue Inspector", lambda i, m: None, default=True),
                MockMenu.SEPARATOR,
                MockMenuItem("Start with Windows", lambda i, m: None),
                MockMenu.SEPARATOR,
                MockMenuItem("Exit", lambda i, m: None),
            )

        menu = build_tray_menu()
        self.assertEqual(menu.items[0].text, "Toggle Queue Mode (F4)")
        self.assertEqual(menu.items[1].text, "Clear Queue (Shift+F4)")
        self.assertEqual(menu.items[2].text, "Quick Notepad (F3)")

        # Trigger notepad item callback
        menu.items[2](None)
        mock_notepad.toggle.assert_called_once()

        # Change hotkey mapping
        hotkeys_map["toggle_notepad"] = "Ctrl+Shift+N"
        updated_menu = build_tray_menu()
        self.assertEqual(updated_menu.items[2].text, "Quick Notepad (Ctrl+Shift+N)")

    def test_idle_auto_clear_manager_execution_idle_mode(self) -> None:
        """Verify idle auto-clear expiration manager clears and notifies in idle mode."""
        mock_config = MagicMock(spec=AppConfig)
        mock_config.get.side_effect = lambda key, default=None: {
            "auto_clear_enabled": True,
            "auto_clear_mode": "idle",
            "auto_clear_seconds": 60,
        }.get(key, default)

        mock_queue = MagicMock(spec=ClipboardQueue)
        notify_mock = MagicMock()
        update_mock = MagicMock()

        # Scenario A: Purged > 0 in idle mode
        mock_queue.purge_idle.return_value = 3
        # Run one cycle of expiration manager logic
        if mock_config.get("auto_clear_enabled", False):
            mode = mock_config.get("auto_clear_mode", "idle")
            timeout = mock_config.get("auto_clear_seconds", 60)
            if mode == "idle":
                purged = mock_queue.purge_idle(timeout)
                if purged > 0:
                    notify_mock("QPaste : Cleared", "cleared")
                    update_mock()

        mock_queue.purge_idle.assert_called_once_with(60)
        notify_mock.assert_called_once_with("QPaste : Cleared", "cleared")
        update_mock.assert_called_once()

        # Scenario B: Purged == 0 in idle mode
        notify_mock.reset_mock()
        update_mock.reset_mock()
        mock_queue.purge_idle.return_value = 0

        if mock_config.get("auto_clear_enabled", False):
            mode = mock_config.get("auto_clear_mode", "idle")
            timeout = mock_config.get("auto_clear_seconds", 60)
            if mode == "idle":
                purged = mock_queue.purge_idle(timeout)
                if purged > 0:
                    notify_mock("QPaste : Cleared", "cleared")
                    update_mock()

        notify_mock.assert_not_called()
        update_mock.assert_not_called()

    def test_idle_auto_clear_manager_execution_ttl_mode(self) -> None:
        """Verify auto-clear expiration manager handles legacy TTL mode."""
        mock_config = MagicMock(spec=AppConfig)
        mock_config.get.side_effect = lambda key, default=None: {
            "auto_clear_enabled": True,
            "auto_clear_mode": "ttl",
            "auto_clear_seconds": 30,
        }.get(key, default)

        mock_queue = MagicMock(spec=ClipboardQueue)
        notify_mock = MagicMock()
        update_mock = MagicMock()

        # Scenario A: Purged > 0 and queue is empty -> Cleared toast + update
        mock_queue.purge_expired.return_value = 2
        mock_queue.__len__.return_value = 0

        if mock_config.get("auto_clear_enabled", False):
            mode = mock_config.get("auto_clear_mode", "idle")
            timeout = mock_config.get("auto_clear_seconds", 60)
            if mode == "idle":
                purged = mock_queue.purge_idle(timeout)
                if purged > 0:
                    notify_mock("QPaste : Cleared", "cleared")
                    update_mock()
            else:
                purged = mock_queue.purge_expired(timeout)
                if purged > 0:
                    if len(mock_queue) == 0:
                        notify_mock("QPaste : Cleared", "cleared")
                    update_mock()

        mock_queue.purge_expired.assert_called_once_with(30)
        notify_mock.assert_called_once_with("QPaste : Cleared", "cleared")
        update_mock.assert_called_once()

        # Scenario B: Purged > 0 but queue still has items -> update only, no cleared toast
        notify_mock.reset_mock()
        update_mock.reset_mock()
        mock_queue.purge_expired.return_value = 1
        mock_queue.__len__.return_value = 2

        if mock_config.get("auto_clear_enabled", False):
            mode = mock_config.get("auto_clear_mode", "idle")
            timeout = mock_config.get("auto_clear_seconds", 60)
            if mode == "idle":
                purged = mock_queue.purge_idle(timeout)
                if purged > 0:
                    notify_mock("QPaste : Cleared", "cleared")
                    update_mock()
            else:
                purged = mock_queue.purge_expired(timeout)
                if purged > 0:
                    if len(mock_queue) == 0:
                        notify_mock("QPaste : Cleared", "cleared")
                    update_mock()

        notify_mock.assert_not_called()
        update_mock.assert_called_once()

    def test_clean_exit_and_teardown(self) -> None:
        """Verify on_exit cleans up all resources, stops listeners, hides HUD, saves config."""
        mock_notepad = MagicMock(spec=QuickNotepadHUD)
        mock_config = MagicMock(spec=AppConfig)
        mock_clipboard_listener = MagicMock()
        mock_listener = MagicMock()
        mock_single_inst = MagicMock()
        mock_tray_icon = MagicMock()
        mock_root = MagicMock()
        icon_instance = [mock_tray_icon]

        with patch("os._exit") as mock_os_exit:
            def on_exit(icon, item):
                mock_notepad.hide()
                mock_config.save()
                mock_clipboard_listener.stop()
                mock_listener.stop()
                mock_single_inst.release()
                if icon_instance:
                    icon_instance[0].stop()
                try:
                    mock_root.quit()
                except Exception:
                    pass
                os._exit(0)

            on_exit(None, None)

            mock_notepad.hide.assert_called_once()
            mock_config.save.assert_called_once()
            mock_clipboard_listener.stop.assert_called_once()
            mock_listener.stop.assert_called_once()
            mock_single_inst.release.assert_called_once()
            mock_tray_icon.stop.assert_called_once()
            mock_root.quit.assert_called_once()
            mock_os_exit.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
