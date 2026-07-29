"""
Unit tests for UI integration and notification dispatch in QPaste.
"""
from unittest.mock import MagicMock
import pytest

from core.clipboard_queue import ClipboardQueue
from core.listener import ShortcutHandler
from core.state import AppState
from ui.toast import NativeToastOverlay


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
