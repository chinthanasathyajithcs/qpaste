"""
Comprehensive User Story Acceptance Tests for QPaste.
Covers all user stories: Toggle Mode Isolation, FIFO Copy/Paste,
Empty Queue Fallback, Clear Queue, Smart Undo, Mode Transition Safety.

Each test function name maps to an acceptance criterion in user_stories.md.
"""
import time
import pytest
from unittest.mock import MagicMock
from core.clipboard_queue import ClipboardQueue
from core.state import AppState
from core.listener import ShortcutHandler


# ===========================================================================
# Helpers
# ===========================================================================

def _make_handler(active=True, notify=False, update=False):
    """Factory: creates a fresh (state, queue, handler, extras) tuple."""
    state = AppState(initial_active=active)
    queue = ClipboardQueue()
    notifications = [] if notify else None
    updates = [] if update else None

    handler = ShortcutHandler(
        state=state,
        queue=queue,
        on_notify_callback=(lambda msg, t: notifications.append((msg, t))) if notify else None,
        on_update_callback=(lambda: updates.append(True)) if update else None,
    )
    handler.CLIPBOARD_READ_DELAY = 0  # Remove delay for deterministic tests
    return state, queue, handler, notifications, updates


# ===========================================================================
# US-1: Toggle Mode Isolation (F4 Master Switch)
# ===========================================================================

class TestUS1_ToggleModeIsolation:

    def test_f4_toggles_on_off(self):
        """AC-1.1: F4 toggles queue mode between ON and OFF."""
        state, _, handler, _, _ = _make_handler(active=True)

        handler.handle_f4()
        assert state.is_active() is False

        handler.handle_f4()
        assert state.is_active() is True

        handler.handle_f4()
        assert state.is_active() is False

    def test_copy_ignored_when_off(self, monkeypatch):
        """AC-1.2: Ctrl+C does NOT enqueue when queue mode is OFF."""
        _, queue, handler, _, _ = _make_handler(active=False)
        monkeypatch.setattr("pyperclip.paste", lambda: "should_be_ignored")

        handler.handle_copy()
        time.sleep(0.3)
        assert queue.is_empty() is True

    def test_paste_ignored_when_off(self, monkeypatch):
        """AC-1.3: Ctrl+V does NOT dequeue when queue mode is OFF."""
        _, queue, handler, _, _ = _make_handler(active=False)
        queue.push("should_remain")
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        result = handler.handle_paste()
        assert result is False
        assert len(queue) == 1
        assert len(writes) == 0

    def test_undo_ignored_when_off(self, monkeypatch):
        """AC-1.4: Ctrl+Z does NOT re-enqueue when queue mode is OFF."""
        _, queue, handler, _, _ = _make_handler(active=False)
        handler._last_pasted_text = "recent_paste"
        handler._paste_timestamp = time.time()

        result = handler.handle_undo()
        assert result is False
        assert queue.is_empty() is True

    def test_toggle_off_preserves_queue(self):
        """AC-1.5: Toggling ON→OFF does NOT destroy existing queue items."""
        state, queue, handler, _, _ = _make_handler(active=True)
        queue.push("Item A")
        queue.push("Item B")

        handler.handle_f4()  # ON → OFF
        assert state.is_active() is False
        assert len(queue) == 2
        assert queue.get_items() == ["Item A", "Item B"]

    def test_toggle_on_resumes_fifo(self, monkeypatch):
        """AC-1.6: Toggling OFF→ON resumes FIFO from where it left off."""
        state, queue, handler, _, _ = _make_handler(active=True)
        queue.push("First")
        queue.push("Second")
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        # Paste one item while ON
        handler.handle_paste()
        assert writes[-1] == "First"

        # Toggle OFF then ON
        handler.handle_f4()  # OFF
        handler.handle_f4()  # ON

        # Next paste should continue FIFO
        handler.handle_paste()
        assert writes[-1] == "Second"

    def test_toggle_fires_toast(self):
        """AC-1.7: Toast notification fires on every toggle."""
        _, _, handler, notifs, _ = _make_handler(active=True, notify=True)

        handler.handle_f4()  # ON → OFF
        assert notifs[-1] == ("QPaste : OFF", "off")

        handler.handle_f4()  # OFF → ON
        assert notifs[-1] == ("QPaste : ON", "on")


# ===========================================================================
# US-2: Sequential FIFO Copy & Paste
# ===========================================================================

class TestUS2_SequentialFIFO:

    def test_sequential_copy_enqueues_in_order(self, monkeypatch):
        """AC-2.1: Copying 3 items enqueues them in chronological order."""
        _, queue, handler, _, _ = _make_handler(active=True)

        for text in ["Alpha", "Beta", "Gamma"]:
            monkeypatch.setattr("pyperclip.paste", lambda t=text: t)
            handler._read_and_enqueue()

        items = queue.get_items()
        assert items == ["Alpha", "Beta", "Gamma"]

    def test_sequential_paste_fifo_order(self, monkeypatch):
        """AC-2.2: Pasting 3 times returns items in FIFO order (oldest first)."""
        _, queue, handler, _, _ = _make_handler(active=True)
        queue.push("First")
        queue.push("Second")
        queue.push("Third")
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        handler.handle_paste()
        handler.handle_paste()
        handler.handle_paste()

        assert writes == ["First", "Second", "Third"]

    def test_full_copy_paste_roundtrip(self, monkeypatch):
        """AC-2.3: Full round-trip copy A→B→C, paste returns A→B→C."""
        _, queue, handler, _, _ = _make_handler(active=True)
        clipboard = [""]
        writes = []

        monkeypatch.setattr("pyperclip.paste", lambda: clipboard[0])
        monkeypatch.setattr("pyperclip.copy", lambda t: (writes.append(t), clipboard.__setitem__(0, t)))

        # Copy phase
        for text in ["Alpha", "Beta", "Gamma"]:
            clipboard[0] = text
            handler._read_and_enqueue()

        # Paste phase
        handler.handle_paste()
        assert writes[-1] == "Alpha"
        handler.handle_paste()
        assert writes[-1] == "Beta"
        handler.handle_paste()
        assert writes[-1] == "Gamma"
        assert queue.is_empty()

    def test_multiline_code_block_preserved(self, monkeypatch):
        """AC-2.4: Multi-line text (code blocks) is preserved exactly."""
        _, queue, handler, _, _ = _make_handler(active=True)

        code_block = "def greet(name):\n    print(f'Hello {name}')\n    return True\n"
        monkeypatch.setattr("pyperclip.paste", lambda: code_block)

        handler._read_and_enqueue()
        assert queue.get_items()[0] == code_block

        written = []
        monkeypatch.setattr("pyperclip.copy", lambda t: written.append(t))
        handler.handle_paste()
        assert written[0] == code_block

    def test_single_line_text(self, monkeypatch):
        """AC-2.5: Single-line short text works correctly."""
        _, queue, handler, _, _ = _make_handler(active=True)

        monkeypatch.setattr("pyperclip.paste", lambda: "npm install express")
        handler._read_and_enqueue()

        written = []
        monkeypatch.setattr("pyperclip.copy", lambda t: written.append(t))
        handler.handle_paste()
        assert written[0] == "npm install express"

    def test_special_characters_preserved(self, monkeypatch):
        """AC-2.6: Unicode, tabs, mixed newlines are preserved."""
        _, queue, handler, _, _ = _make_handler(active=True)

        special = "Hello 🌍\tWorld\r\nLine2\nLine3\t\t🚀"
        monkeypatch.setattr("pyperclip.paste", lambda: special)
        handler._read_and_enqueue()

        written = []
        monkeypatch.setattr("pyperclip.copy", lambda t: written.append(t))
        handler.handle_paste()
        assert written[0] == special

    def test_empty_clipboard_ignored(self, monkeypatch):
        """AC-2.7: Empty clipboard content is silently ignored."""
        _, queue, handler, _, _ = _make_handler(active=True)

        monkeypatch.setattr("pyperclip.paste", lambda: "")
        handler._read_and_enqueue()
        assert queue.is_empty()


# ===========================================================================
# US-3: Empty Queue Fallback to OS Paste
# ===========================================================================

class TestUS3_EmptyQueueFallback:

    def test_paste_empty_queue_no_clipboard_write(self, monkeypatch):
        """AC-3.1: Ctrl+V with empty queue does NOT modify the clipboard."""
        _, queue, handler, _, _ = _make_handler(active=True)
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        handler.handle_paste()
        assert len(writes) == 0

    def test_paste_empty_queue_returns_false(self, monkeypatch):
        """AC-3.2: handle_paste() returns False when queue is empty."""
        _, _, handler, _, _ = _make_handler(active=True)
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        result = handler.handle_paste()
        assert result is False

    def test_paste_fallthrough_after_drain(self, monkeypatch):
        """AC-3.3: After queue drains completely, next paste falls through."""
        _, queue, handler, _, _ = _make_handler(active=True)
        queue.push("Only Item")
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        result1 = handler.handle_paste()
        assert result1 is True
        assert writes[-1] == "Only Item"

        # Queue is now empty — next paste should fall through
        result2 = handler.handle_paste()
        assert result2 is False
        assert len(writes) == 1  # No additional clipboard write


# ===========================================================================
# US-4: Clear Queue (Shift+F4)
# ===========================================================================

class TestUS4_ClearQueue:

    def test_clear_empties_queue(self):
        """AC-4.1: Shift+F4 empties the entire queue."""
        _, queue, handler, _, _ = _make_handler(active=True)
        queue.push("A")
        queue.push("B")
        queue.push("C")

        handler.handle_shift_f4()
        assert queue.is_empty()
        assert len(queue) == 0

    def test_clear_resets_undo_tracking(self):
        """AC-4.2: Shift+F4 resets undo tracking (no phantom undo)."""
        _, _, handler, _, _ = _make_handler(active=True)
        handler._last_pasted_text = "was_just_pasted"
        handler._paste_timestamp = time.time()

        handler.handle_shift_f4()
        assert handler._last_pasted_text is None

    def test_clear_fires_toast(self):
        """AC-4.3: A 'QPaste : Cleared' toast fires."""
        _, _, handler, notifs, _ = _make_handler(active=True, notify=True)

        handler.handle_shift_f4()
        assert notifs[-1] == ("QPaste : Cleared", "cleared")


# ===========================================================================
# US-5: Smart Ctrl+Z Undo Paste
# ===========================================================================

class TestUS5_SmartUndo:

    def test_undo_reenqueues_to_front(self, monkeypatch):
        """AC-5.1: Undo within 5s re-enqueues text to the FRONT of the queue."""
        _, queue, handler, _, _ = _make_handler(active=True)
        queue.push("Remaining Item")
        monkeypatch.setattr("pyperclip.copy", lambda t: None)
        monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: False))

        handler._last_pasted_text = "Just Pasted"
        handler._paste_timestamp = time.time()

        result = handler.handle_undo()
        assert result is True

        items = queue.get_items()
        assert items[0] == "Just Pasted"  # Re-enqueued at FRONT
        assert items[1] == "Remaining Item"

    def test_undo_expired_passes_through(self, monkeypatch):
        """AC-5.2: Undo after 5s window expires passes through to native undo."""
        _, queue, handler, _, _ = _make_handler(active=True)
        handler.UNDO_WINDOW_SECONDS = 1.0
        monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: False))

        handler._last_pasted_text = "Old Paste"
        handler._paste_timestamp = time.time() - 2.0  # Beyond 1s window

        result = handler.handle_undo()
        assert result is False
        assert queue.is_empty()  # NOT re-enqueued

    def test_undo_only_once_per_paste(self, monkeypatch):
        """AC-5.3: Undo can only be done once per paste (no double re-enqueue)."""
        _, queue, handler, _, _ = _make_handler(active=True)
        monkeypatch.setattr("pyperclip.copy", lambda t: None)
        monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: False))

        handler._last_pasted_text = "Undo Me"
        handler._paste_timestamp = time.time()

        # First undo succeeds
        result1 = handler.handle_undo()
        assert result1 is True
        assert len(queue) == 1

        # Second undo should fail (last_pasted_text was cleared)
        result2 = handler.handle_undo()
        assert result2 is False
        assert len(queue) == 1  # No duplicate

    def test_undo_bypassed_in_explorer(self, monkeypatch):
        """AC-5.4: Undo in File Explorer bypasses QPaste (native undo works)."""
        _, queue, handler, _, _ = _make_handler(active=True)
        monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: True))

        handler._last_pasted_text = "Explorer Paste"
        handler._paste_timestamp = time.time()

        result = handler.handle_undo()
        assert result is False
        assert queue.is_empty()  # NOT re-enqueued

    def test_undo_fires_toast(self, monkeypatch):
        """AC-5.5: Undo fires a 'QPaste : Undo' toast."""
        _, _, handler, notifs, _ = _make_handler(active=True, notify=True)
        monkeypatch.setattr("pyperclip.copy", lambda t: None)
        monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: False))

        handler._last_pasted_text = "Toast Test"
        handler._paste_timestamp = time.time()

        handler.handle_undo()
        assert notifs[-1] == ("QPaste : Undo", "info")


# ===========================================================================
# US-6: Mode Transition Safety
# ===========================================================================

class TestUS6_ModeTransitionSafety:

    def test_copy_while_off_not_queued(self, monkeypatch):
        """AC-6.1: Items copied while OFF are NOT added to the queue."""
        state, queue, handler, _, _ = _make_handler(active=True)
        monkeypatch.setattr("pyperclip.paste", lambda: "while_off")

        handler.handle_f4()  # Turn OFF
        assert state.is_active() is False

        handler.handle_copy()
        time.sleep(0.3)
        assert queue.is_empty()

    def test_on_after_os_copy_drains_queue(self, monkeypatch):
        """AC-6.2: Turning ON after OS-mode copy: paste drains queue, not OS clipboard."""
        state, queue, handler, _, _ = _make_handler(active=True)
        writes = []

        # Pre-load queue with items from a previous session
        queue.push("Queued Item A")
        queue.push("Queued Item B")

        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        # Toggle OFF, then ON (simulating "user copied in OS mode, now back")
        handler.handle_f4()  # OFF
        handler.handle_f4()  # ON

        # Paste should drain queue, NOT whatever the OS clipboard has
        handler.handle_paste()
        assert writes[-1] == "Queued Item A"
        handler.handle_paste()
        assert writes[-1] == "Queued Item B"

    def test_off_mid_queue_items_survive(self, monkeypatch):
        """AC-6.3: Turning OFF mid-queue: remaining items survive for next ON session."""
        state, queue, handler, _, _ = _make_handler(active=True)
        queue.push("Survive A")
        queue.push("Survive B")
        queue.push("Survive C")
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        # Paste one item
        handler.handle_paste()
        assert writes[-1] == "Survive A"

        # Toggle OFF mid-queue
        handler.handle_f4()
        assert len(queue) == 2

        # Toggle ON — remaining items are still there
        handler.handle_f4()
        handler.handle_paste()
        assert writes[-1] == "Survive B"
        handler.handle_paste()
        assert writes[-1] == "Survive C"
        assert queue.is_empty()

    def test_rapid_toggle_no_corruption(self, monkeypatch):
        """AC-6.4: Rapid toggle ON→OFF→ON does not corrupt queue state."""
        _, queue, handler, _, _ = _make_handler(active=True)
        queue.push("Stable A")
        queue.push("Stable B")

        # Rapid toggles
        for _ in range(10):
            handler.handle_f4()  # OFF
            handler.handle_f4()  # ON

        # Queue should be completely untouched
        assert queue.get_items() == ["Stable A", "Stable B"]

        # Paste should still work correctly
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))
        handler.handle_paste()
        assert writes[-1] == "Stable A"
        handler.handle_paste()
        assert writes[-1] == "Stable B"


# ===========================================================================
# US-7: Queue Operations (Inspector Backend)
# ===========================================================================

class TestUS7_QueueOperations:

    def test_remove_at_index(self):
        """AC-8.1: Delete an item at a specific index."""
        q = ClipboardQueue()
        q.push("A")
        q.push("B")
        q.push("C")

        removed = q.remove_at(1)
        assert removed == "B"
        assert q.get_items() == ["A", "C"]

    def test_remove_at_invalid_index(self):
        """Edge: remove_at with out-of-bounds index returns None."""
        q = ClipboardQueue()
        q.push("A")

        assert q.remove_at(5) is None
        assert q.remove_at(-1) is None
        assert len(q) == 1

    def test_move_item_reorder(self):
        """AC-8.2: Move an item up/down."""
        q = ClipboardQueue()
        q.push("A")
        q.push("B")
        q.push("C")

        # Move "C" (index 2) up to index 0
        q.move_item(2, 0)
        assert q.get_items() == ["C", "A", "B"]

        # Move "C" (now index 0) down to index 2
        q.move_item(0, 2)
        assert q.get_items() == ["A", "B", "C"]

    def test_move_item_invalid_index(self):
        """Edge: move_item with invalid indices returns False."""
        q = ClipboardQueue()
        q.push("A")

        assert q.move_item(0, 5) is False
        assert q.move_item(5, 0) is False

    def test_push_front(self):
        """Verify push_front adds to front (used by undo)."""
        q = ClipboardQueue()
        q.push("B")
        q.push("C")
        q.push_front("A")

        assert q.get_items() == ["A", "B", "C"]

    def test_inspector_clear_all(self):
        """AC-8.3: Clear all via inspector clears the underlying queue."""
        q = ClipboardQueue()
        q.push("X")
        q.push("Y")
        q.push("Z")

        q.clear()
        assert q.is_empty()
        assert len(q) == 0


# ===========================================================================
# Integration: Full Workflow Scenarios
# ===========================================================================

class TestIntegration_FullWorkflows:

    def test_copy_paste_undo_repaste(self, monkeypatch):
        """Workflow: copy → paste → undo → paste again (same item re-appears)."""
        _, queue, handler, _, _ = _make_handler(active=True)
        writes = []
        monkeypatch.setattr("pyperclip.paste", lambda: "Snippet")
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))
        monkeypatch.setattr(ShortcutHandler, "_is_explorer_active", staticmethod(lambda: False))

        # Copy
        handler._read_and_enqueue()
        assert len(queue) == 1

        # Paste
        handler.handle_paste()
        assert writes[-1] == "Snippet"
        assert queue.is_empty()

        # Undo — re-enqueue
        handler.handle_undo()
        assert len(queue) == 1
        assert queue.get_items()[0] == "Snippet"

        # Paste again — same item
        handler.handle_paste()
        assert writes[-1] == "Snippet"
        assert queue.is_empty()

    def test_mixed_toggle_copy_paste_flow(self, monkeypatch):
        """Workflow: ON → copy 2 → OFF → ON → paste 2 in FIFO order."""
        state, queue, handler, _, _ = _make_handler(active=True)
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        # ON: copy 2 items
        monkeypatch.setattr("pyperclip.paste", lambda: "Item1")
        handler._read_and_enqueue()
        monkeypatch.setattr("pyperclip.paste", lambda: "Item2")
        handler._read_and_enqueue()
        assert len(queue) == 2

        # OFF
        handler.handle_f4()
        assert state.is_active() is False

        # ON again
        handler.handle_f4()
        assert state.is_active() is True

        # Paste — should drain in FIFO order
        handler.handle_paste()
        assert writes[-1] == "Item1"
        handler.handle_paste()
        assert writes[-1] == "Item2"
        assert queue.is_empty()

    def test_clear_then_copy_paste(self, monkeypatch):
        """Workflow: copy 3 → clear → copy 1 → paste returns only the new item."""
        _, queue, handler, _, _ = _make_handler(active=True)
        writes = []
        monkeypatch.setattr("pyperclip.copy", lambda t: writes.append(t))

        # Copy 3 items
        for text in ["Old1", "Old2", "Old3"]:
            monkeypatch.setattr("pyperclip.paste", lambda t=text: t)
            handler._read_and_enqueue()

        # Clear queue
        handler.handle_shift_f4()
        assert queue.is_empty()

        # Copy 1 new item
        monkeypatch.setattr("pyperclip.paste", lambda: "Fresh")
        handler._read_and_enqueue()

        # Paste should return only the new item
        handler.handle_paste()
        assert writes[-1] == "Fresh"
        assert queue.is_empty()
