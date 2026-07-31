"""
Unit tests for QPaste Keyboard Listener Controller.
Covers: toggle, clear, copy-enqueue, paste-dequeue, and FIFO ordering.
"""
import pytest
from unittest.mock import MagicMock
from core.clipboard_queue import ClipboardQueue
from core.state import AppState
from core.listener import ShortcutHandler


# ---------------------------------------------------------------------------
# Toggle & Clear
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Copy (handle_copy / _read_and_enqueue)
# ---------------------------------------------------------------------------

def test_copy_enqueues_clipboard_text(monkeypatch):
    """Verify _read_and_enqueue reads clipboard and pushes to queue."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)


    handler.on_clipboard_changed("Copied Code Snippet")
    assert len(queue) == 1
    assert queue.get_items()[0] == "Copied Code Snippet"


def test_copy_skipped_when_paused(monkeypatch):
    """Verify handle_copy does nothing when Queue Mode is PAUSED."""
    state = AppState(initial_active=False)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    handler.on_clipboard_changed("Ignored Snippet")
    assert queue.is_empty() is True


def test_copy_multiline_text(monkeypatch):
    """Verify multi-line text (code blocks) is enqueued correctly."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)


    multiline = "def hello():\n    print('world')\n    return 42"
    handler.on_clipboard_changed(multiline)
    assert len(queue) == 1
    assert queue.get_items()[0] == multiline


def test_copy_empty_clipboard_ignored(monkeypatch):
    """Verify empty clipboard text is not enqueued."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)


    handler.on_clipboard_changed("")
    assert queue.is_empty() is True


# ---------------------------------------------------------------------------
# Paste (handle_paste)
# ---------------------------------------------------------------------------

def test_paste_pops_oldest_fifo_item(monkeypatch):
    """Verify paste pops the OLDEST item and writes it to clipboard."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    queue.push("First")
    queue.push("Second")
    queue.push("Third")
    handler = ShortcutHandler(state=state, queue=queue)

    clipboard_writes = []
    monkeypatch.setattr("pyperclip.copy", lambda t: clipboard_writes.append(t))

    result = handler.handle_paste()
    assert result is True
    assert clipboard_writes[-1] == "First"
    assert len(queue) == 2

    result = handler.handle_paste()
    assert result is True
    assert clipboard_writes[-1] == "Second"
    assert len(queue) == 1

    result = handler.handle_paste()
    assert result is True
    assert clipboard_writes[-1] == "Third"
    assert len(queue) == 0


def test_paste_empty_queue_returns_false(monkeypatch):
    """Verify paste returns False and does nothing when queue is empty."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    clipboard_writes = []
    monkeypatch.setattr("pyperclip.copy", lambda t: clipboard_writes.append(t))

    result = handler.handle_paste()
    assert result is False
    assert len(clipboard_writes) == 0


def test_paste_skipped_when_paused(monkeypatch):
    """Verify paste does nothing when Queue Mode is PAUSED."""
    state = AppState(initial_active=False)
    queue = ClipboardQueue()
    queue.push("Should Not Paste")
    handler = ShortcutHandler(state=state, queue=queue)

    clipboard_writes = []
    monkeypatch.setattr("pyperclip.copy", lambda t: clipboard_writes.append(t))

    result = handler.handle_paste()
    assert result is False
    assert len(queue) == 1  # Item should remain in queue


# ---------------------------------------------------------------------------
# Full FIFO Sequence Integration
# ---------------------------------------------------------------------------

def test_full_fifo_copy_paste_sequence(monkeypatch):
    """End-to-end: copy 3 items, then paste 3 items in FIFO order."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    clipboard_content = [""]
    clipboard_writes = []

    def mock_paste():
        return clipboard_content[0]

    def mock_copy(text):
        clipboard_content[0] = text
        clipboard_writes.append(text)

    monkeypatch.setattr("pyperclip.paste", mock_paste)
    monkeypatch.setattr("pyperclip.copy", mock_copy)

    # Simulate 3 sequential copies
    clipboard_content[0] = "Alpha"
    handler.on_clipboard_changed("Alpha")

    clipboard_content[0] = "Beta"
    handler.on_clipboard_changed("Beta")

    clipboard_content[0] = "Gamma"
    handler.on_clipboard_changed("Gamma")

    assert len(queue) == 3

    # Simulate 3 sequential pastes — must come out in FIFO order
    handler.handle_paste()
    assert clipboard_writes[-1] == "Alpha"

    handler.handle_paste()
    assert clipboard_writes[-1] == "Beta"

    handler.handle_paste()
    assert clipboard_writes[-1] == "Gamma"

    assert queue.is_empty() is True



# ---------------------------------------------------------------------------
# Notification Callbacks
# ---------------------------------------------------------------------------

def test_toggle_fires_notification_callback():
    """Verify F4 toggle fires the notification callback with correct args."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    notifications = []
    handler = ShortcutHandler(
        state=state, queue=queue,
        on_notify_callback=lambda msg, t: notifications.append((msg, t))
    )

    handler.handle_f4()  # ON -> OFF
    assert notifications[-1] == ("QPaste : OFF", "off")

    handler.handle_f4()  # OFF -> ON
    assert notifications[-1] == ("QPaste : ON", "on")


def test_clear_fires_notification_callback():
    """Verify Shift+F4 fires the notification callback."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    notifications = []
    handler = ShortcutHandler(
        state=state, queue=queue,
        on_notify_callback=lambda msg, t: notifications.append((msg, t))
    )

    handler.handle_shift_f4()
    assert notifications[-1] == ("QPaste : Cleared", "cleared")


def test_copy_fires_notification_callback():
    """Verify copying an item fires the notification callback with the queue length."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    notifications = []
    handler = ShortcutHandler(
        state=state, queue=queue,
        on_notify_callback=lambda msg, t: notifications.append((msg, t))
    )

    handler.on_clipboard_changed("First Copy")
    assert notifications[-1] == ("1", "copy_count")

    handler.on_clipboard_changed("Second Copy")
    assert notifications[-1] == ("2", "copy_count")


# ---------------------------------------------------------------------------
# Extensive TDD Test Cases for LIFO/FIFO and Hook Races
# ---------------------------------------------------------------------------

def test_tdd_fifo_order_extensive(monkeypatch):
    """
    Test that when 4 items are copied sequentially, they are pasted
    in the exact same FIFO order (1, 2, 3, 4), and NOT LIFO (4, 3, 2, 1).
    """
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    # 1. Copy 4 items
    items_to_copy = ["Item 1", "Item 2", "Item 3", "Item 4"]
    for item in items_to_copy:
        handler.on_clipboard_changed(item)
    
    assert len(queue) == 4
    
    # 2. Paste 4 items
    clipboard_writes = []
    monkeypatch.setattr("pyperclip.copy", lambda t: clipboard_writes.append(t))
    
    for _ in range(4):
        handler.handle_paste()
        
    assert len(clipboard_writes) == 4
    assert clipboard_writes == ["Item 1", "Item 2", "Item 3", "Item 4"]
    assert queue.is_empty() is True
