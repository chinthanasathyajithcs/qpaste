"""
Unit tests for QPaste Keyboard Listener Controller.
Ref: PRD Section 3 / POC TC-1 through TC-5
"""
import pytest
from core.clipboard_queue import ClipboardQueue
from core.state import AppState
from core.listener import ShortcutHandler


def test_f4_press_toggles_state():
    """Verify pressing F4 toggles AppState."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    handler.handle_f4()
    assert state.is_active() is False

    handler.handle_f4()
    assert state.is_active() is True


def test_shift_f4_press_clears_queue():
    """Verify pressing Shift+F4 clears the queue."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    queue.push("Item 1")
    queue.push("Item 2")
    handler = ShortcutHandler(state=state, queue=queue)

    handler.handle_shift_f4()
    assert queue.is_empty() is True


def test_copy_event_when_active_enqueues_text(monkeypatch):
    """Verify Ctrl+C enqueues clipboard text when Queue Mode is ACTIVE."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    # Mock pyperclip.paste() to return test snippet
    monkeypatch.setattr("pyperclip.paste", lambda: "Copied Code Snippet")

    handler.handle_copy()
    assert len(queue) == 1
    assert queue.get_items()[0] == "Copied Code Snippet"


def test_copy_event_when_paused_ignores_enqueue(monkeypatch):
    """Verify Ctrl+C is ignored when Queue Mode is PAUSED."""
    state = AppState(initial_active=False)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    monkeypatch.setattr("pyperclip.paste", lambda: "Ignored Snippet")

    handler.handle_copy()
    assert queue.is_empty() is True
