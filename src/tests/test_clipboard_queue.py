"""
Unit tests for QPaste thread-safe FIFO Clipboard Queue.
"""
import pytest
from core.clipboard_queue import ClipboardQueue


def test_queue_initial_state_empty():
    """Verify that a newly created queue is empty."""
    q = ClipboardQueue()
    assert q.is_empty() is True
    assert len(q) == 0


def test_enqueue_items():
    """Verify items are added to the queue."""
    q = ClipboardQueue()
    q.push("Snippet 1")
    q.push("Snippet 2")
    assert len(q) == 2
    assert q.is_empty() is False


def test_fifo_dequeue_order():
    """Verify items pop in First-In, First-Out (FIFO) order."""
    q = ClipboardQueue()
    q.push("First")
    q.push("Second")
    q.push("Third")

    assert q.pop() == "First"
    assert q.pop() == "Second"
    assert q.pop() == "Third"
    assert q.is_empty() is True


def test_pop_empty_queue_returns_none():
    """Verify popping an empty queue returns None without raising an exception."""
    q = ClipboardQueue()
    assert q.pop() is None


def test_clear_queue():
    """Verify clear() removes all items from the queue."""
    q = ClipboardQueue()
    q.push("Item A")
    q.push("Item B")
    q.clear()
    assert len(q) == 0
    assert q.is_empty() is True


# --- TDD Slice: Max Queue Size Limit (25) ---

def test_max_queue_size_default_is_25():
    """Verify max_size defaults to 25."""
    q = ClipboardQueue()
    assert q.max_size == 25


def test_max_queue_size_evicts_oldest_item_when_exceeded():
    """Verify pushing more than 25 items keeps queue size at 25 and evicts oldest items."""
    q = ClipboardQueue(max_size=25)
    for i in range(26):
        q.push(f"Item {i}")

    assert len(q) == 25
    # Item 0 should have been evicted; queue should start at Item 1 and end at Item 25
    items = q.get_items()
    assert items[0] == "Item 1"
    assert items[-1] == "Item 25"


def test_max_queue_size_custom_limit():
    """Verify custom max_size (e.g. 5) limits capacity and evicts oldest items."""
    q = ClipboardQueue(max_size=5)
    for i in range(7):
        q.push(f"Snippet {i}")

    assert len(q) == 5
    items = q.get_items()
    assert items[0] == "Snippet 2"
    assert items[-1] == "Snippet 6"
