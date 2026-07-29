"""
Unit tests for QPaste Keyboard Listener Controller.
Covers: toggle, clear, copy-enqueue, paste-dequeue, smart undo, and FIFO ordering.
"""
import time
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


def test_shift_f4_clears_last_pasted_text():
    """Verify Shift+F4 also resets undo tracking."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler._last_pasted_text = "something"

    handler.handle_shift_f4()
    assert handler._last_pasted_text is None


# ---------------------------------------------------------------------------
# Copy (handle_copy / _read_and_enqueue)
# ---------------------------------------------------------------------------

def test_copy_enqueues_clipboard_text(monkeypatch):
    """Verify _read_and_enqueue reads clipboard and pushes to queue."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler.CLIPBOARD_READ_DELAY = 0  # Skip delay for test speed

    monkeypatch.setattr("pyperclip.paste", lambda: "Copied Code Snippet")

    handler._read_and_enqueue()
    assert len(queue) == 1
    assert queue.get_items()[0] == "Copied Code Snippet"


def test_copy_skipped_when_paused(monkeypatch):
    """Verify handle_copy does nothing when Queue Mode is PAUSED."""
    state = AppState(initial_active=False)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)

    monkeypatch.setattr("pyperclip.paste", lambda: "Ignored Snippet")

    handler.handle_copy()
    time.sleep(0.3)
    assert queue.is_empty() is True


def test_copy_multiline_text(monkeypatch):
    """Verify multi-line text (code blocks) is enqueued correctly."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler.CLIPBOARD_READ_DELAY = 0

    multiline = "def hello():\n    print('world')\n    return 42"
    monkeypatch.setattr("pyperclip.paste", lambda: multiline)

    handler._read_and_enqueue()
    assert len(queue) == 1
    assert queue.get_items()[0] == multiline


def test_copy_empty_clipboard_ignored(monkeypatch):
    """Verify empty clipboard text is not enqueued."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler.CLIPBOARD_READ_DELAY = 0

    monkeypatch.setattr("pyperclip.paste", lambda: "")

    handler._read_and_enqueue()
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


def test_paste_records_last_pasted_text(monkeypatch):
    """Verify paste records last pasted text for undo tracking."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    queue.push("TrackMe")
    handler = ShortcutHandler(state=state, queue=queue)

    monkeypatch.setattr("pyperclip.copy", lambda t: None)

    handler.handle_paste()
    assert handler._last_pasted_text == "TrackMe"
    assert handler._paste_timestamp > 0


# ---------------------------------------------------------------------------
# Full FIFO Sequence Integration
# ---------------------------------------------------------------------------

def test_full_fifo_copy_paste_sequence(monkeypatch):
    """End-to-end: copy 3 items, then paste 3 items in FIFO order."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler.CLIPBOARD_READ_DELAY = 0

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
    handler._read_and_enqueue()

    clipboard_content[0] = "Beta"
    handler._read_and_enqueue()

    clipboard_content[0] = "Gamma"
    handler._read_and_enqueue()

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
# Smart Undo (handle_undo)
# ---------------------------------------------------------------------------

def test_undo_reenqueues_to_front(monkeypatch):
    """Verify Ctrl+Z re-enqueues last pasted text to the FRONT of queue."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    queue.push("Remaining")
    handler = ShortcutHandler(state=state, queue=queue)

    monkeypatch.setattr("pyperclip.copy", lambda t: None)

    # Simulate a recent paste
    handler._last_pasted_text = "JustPasted"
    handler._paste_timestamp = time.time()

    # Mock _is_explorer_active to return False (we're in a text editor)
    monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: False))

    result = handler.handle_undo()
    assert result is True
    assert handler._last_pasted_text is None

    # "JustPasted" should be at the FRONT, before "Remaining"
    items = queue.get_items()
    assert items[0] == "JustPasted"
    assert items[1] == "Remaining"


def test_undo_bypassed_when_no_recent_paste():
    """Verify Ctrl+Z passes through if no paste was recently performed."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler._last_pasted_text = None

    result = handler.handle_undo()
    assert result is False


def test_undo_bypassed_when_paused():
    """Verify Ctrl+Z passes through when Queue Mode is PAUSED."""
    state = AppState(initial_active=False)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler._last_pasted_text = "Something"
    handler._paste_timestamp = time.time()

    result = handler.handle_undo()
    assert result is False


def test_undo_expires_after_window(monkeypatch):
    """Verify Ctrl+Z passes through if paste happened too long ago."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler.UNDO_WINDOW_SECONDS = 1.0

    handler._last_pasted_text = "Expired"
    handler._paste_timestamp = time.time() - 2.0  # 2 seconds ago, beyond 1s window

    monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: False))

    result = handler.handle_undo()
    assert result is False


def test_undo_bypassed_in_explorer(monkeypatch):
    """Verify Ctrl+Z passes through when active window is explorer.exe."""
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    handler = ShortcutHandler(state=state, queue=queue)
    handler._last_pasted_text = "InExplorer"
    handler._paste_timestamp = time.time()

    # Mock explorer active
    monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: True))

    result = handler.handle_undo()
    assert result is False
    assert len(queue) == 0  # Should NOT have re-enqueued


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
