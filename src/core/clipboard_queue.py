"""
Thread-safe First-In, First-Out (FIFO) Clipboard Queue engine for QPaste.
"""
from collections import deque
import threading
from typing import List, Optional


class ClipboardQueue:
    """Thread-safe FIFO Queue managing sequential copied text items."""

    def __init__(self) -> None:
        self._queue: deque[str] = deque()
        self._lock: threading.Lock = threading.Lock()

    def push(self, text: str) -> None:
        """Appends a copied text snippet to the back of the FIFO queue."""
        if not text:
            return
        with self._lock:
            self._queue.append(text)

    def pop(self) -> Optional[str]:
        """
        Removes and returns the oldest text snippet from the front of the queue.
        Returns None if the queue is empty.
        """
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

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
