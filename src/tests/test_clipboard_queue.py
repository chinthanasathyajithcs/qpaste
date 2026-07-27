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
