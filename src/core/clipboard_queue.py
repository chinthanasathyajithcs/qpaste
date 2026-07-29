"""
Thread-safe First-In, First-Out (FIFO) Clipboard Queue engine for QPaste.
"""
from collections import deque
import threading
from typing import List, Optional

DEFAULT_MAX_QUEUE_SIZE = 25


class ClipboardQueue:
    """Thread-safe FIFO Queue managing sequential copied text items with max size capacity."""

    def __init__(self, max_size: int = DEFAULT_MAX_QUEUE_SIZE) -> None:
        self.max_size: int = max_size
        self._queue: deque[str] = deque()
        self._lock: threading.Lock = threading.Lock()

    def push(self, text: str) -> None:
        """
        Appends a copied text snippet to the back of the FIFO queue.
        Evicts the oldest item from the front if queue length exceeds max_size.
        """
        if not text:
            return
        with self._lock:
            self._queue.append(text)
            while len(self._queue) > self.max_size:
                self._queue.popleft()

    def push_front(self, text: str) -> None:
        """
        Pushes a text snippet to the front of the FIFO queue (for undo paste).
        Evicts the newest item from the back if queue length exceeds max_size.
        """
        if not text:
            return
        with self._lock:
            self._queue.appendleft(text)
            while len(self._queue) > self.max_size:
                self._queue.pop()

    def pop(self) -> Optional[str]:
        """
        Removes and returns the oldest text snippet from the front of the queue.
        Returns None if the queue is empty.
        """
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    def remove_at(self, index: int) -> Optional[str]:
        """Removes and returns the item at the specified index, or None if invalid."""
        with self._lock:
            if 0 <= index < len(self._queue):
                items = list(self._queue)
                removed = items.pop(index)
                self._queue = deque(items)
                return removed
            return None

    def move_item(self, old_index: int, new_index: int) -> bool:
        """Moves an item from old_index to new_index. Returns True if successful."""
        with self._lock:
            if 0 <= old_index < len(self._queue) and 0 <= new_index < len(self._queue):
                items = list(self._queue)
                item = items.pop(old_index)
                items.insert(new_index, item)
                self._queue = deque(items)
                return True
            return False

    def clear(self) -> None:
        """Empties all items from the FIFO queue."""
        with self._lock:
            self._queue.clear()

    def is_empty(self) -> bool:
        """Returns True if the queue contains no items."""
        with self._lock:
            return len(self._queue) == 0

    def get_items(self) -> List[str]:
        """Returns a snapshot copy of all items currently in the queue for HUD rendering."""
        with self._lock:
            return list(self._queue)

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)
