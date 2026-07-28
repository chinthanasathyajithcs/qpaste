"""
Unit tests for UI integration and state synchronization in QPaste.
"""
from unittest.mock import MagicMock
import pytest

from core.clipboard_queue import ClipboardQueue
from core.listener import ShortcutHandler
from core.state import AppState
from ui.hud import QPasteHUD


def test_hud_initialization():
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    hud = QPasteHUD(state, queue)

    assert hud.state == state
    assert hud.queue == queue
    assert hud.page is None


def test_hud_callbacks_trigger():
    toggle_mock = MagicMock()
    clear_mock = MagicMock()

    hud = QPasteHUD(
        state=AppState(),
        queue=ClipboardQueue(),
        on_toggle_callback=toggle_mock,
        on_clear_callback=clear_mock,
    )

    hud._handle_toggle_click(None)
    toggle_mock.assert_called_once()

    hud._handle_clear_click(None)
    clear_mock.assert_called_once()


def test_shortcut_handler_triggers_ui_update_callback():
    update_mock = MagicMock()
    state = AppState(initial_active=True)
    queue = ClipboardQueue()

    handler = ShortcutHandler(state, queue, on_update_callback=update_mock)

    # Test F4 toggle triggers callback
    handler.handle_f4()
    assert update_mock.call_count == 1
    assert not state.is_active()

    # Test Clear triggers callback
    handler.handle_shift_f4()
    assert update_mock.call_count == 2
