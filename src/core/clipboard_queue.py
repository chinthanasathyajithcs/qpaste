"""Thread-safe First-In, First-Out (FIFO) Clipboard Queue engine for QPaste."""
from collections import deque
import threading
import time
from typing import List, Optional, Tuple

DEFAULT_MAX_QUEUE_SIZE = 25


class ClipboardQueue:
    """Thread-safe FIFO Queue managing sequential copied text items with timestamps and max capacity."""

    def __init__(self, max_size: int = DEFAULT_MAX_QUEUE_SIZE) -> None:
        self.max_size: int = max_size
        self._queue: deque[Tuple[str, float]] = deque()
        self._lock: threading.RLock = threading.RLock()
        self._last_activity_time: float = time.time()

    def push(self, text: str) -> None:
        """Appends text snippet to back; evicts oldest if over max_size."""
        if not text:
            return
        with self._lock:
            self._last_activity_time = time.time()
            self._queue.append((text, time.time()))
            while len(self._queue) > self.max_size:
                self._queue.popleft()

    def push_front(self, text: str) -> None:
        """Pushes text snippet to front; evicts newest if over max_size."""
        if not text:
            return
        with self._lock:
            self._last_activity_time = time.time()
            self._queue.appendleft((text, time.time()))
            while len(self._queue) > self.max_size:
                self._queue.pop()

    def pop(self) -> Optional[str]:
        """Removes and returns oldest text snippet from front of queue."""
        with self._lock:
            self._last_activity_time = time.time()
            if not self._queue:
                return None
            item, _ = self._queue.popleft()
            return item

    def get_item(self, index: int) -> Optional[str]:
        """Returns item at index without removing it, or None if invalid."""
        with self._lock:
            if 0 <= index < len(self._queue):
                return self._queue[index][0]
            return None

    def promote_to_front(self, index: int) -> bool:
        """Moves item at index directly to position 0. Returns True if successful."""
        with self._lock:
            if 0 <= index < len(self._queue):
                self._last_activity_time = time.time()
                items = list(self._queue)
                item = items.pop(index)
                items.insert(0, item)
                self._queue = deque(items)
                return True
            return False

    def remove_at(self, index: int) -> Optional[str]:
        """Removes and returns item at index, or None if invalid."""
        with self._lock:
            if 0 <= index < len(self._queue):
                self._last_activity_time = time.time()
                items = list(self._queue)
                removed_item, _ = items.pop(index)
                self._queue = deque(items)
                return removed_item
            return None

    def move_item(self, old_index: int, new_index: int) -> bool:
        """Moves item from old_index to new_index. Returns True if successful."""
        with self._lock:
            if 0 <= old_index < len(self._queue) and 0 <= new_index < len(self._queue):
                self._last_activity_time = time.time()
                items = list(self._queue)
                item = items.pop(old_index)
                items.insert(new_index, item)
                self._queue = deque(items)
                return True
            return False

    def purge_expired(self, timeout_seconds: float) -> int:
        """Purges items older than timeout_seconds. Returns number of purged items."""
        if timeout_seconds <= 0:
            return 0
        now = time.time()
        with self._lock:
            initial_count = len(self._queue)
            valid_items = [item for item in self._queue if (now - item[1]) <= timeout_seconds]
            self._queue = deque(valid_items)
            return initial_count - len(self._queue)

    def get_last_activity_time(self) -> float:
        """Returns timestamp of last queue activity."""
        with self._lock:
            return self._last_activity_time

    def touch_activity(self) -> None:
        """Explicitly refreshes activity timestamp."""
        with self._lock:
            self._last_activity_time = time.time()

    def is_idle_expired(self, idle_timeout_seconds: float) -> bool:
        """Returns True if queue has items, timeout > 0, and idle duration >= timeout."""
        with self._lock:
            return (
                len(self._queue) > 0
                and idle_timeout_seconds > 0
                and (time.time() - self._last_activity_time) >= idle_timeout_seconds
            )

    def purge_idle(self, idle_timeout_seconds: float) -> int:
        """Empties queue if idle timeout expired, returning count of purged items."""
        with self._lock:
            if not self.is_idle_expired(idle_timeout_seconds):
                return 0
            count = len(self._queue)
            self._queue.clear()
            self._last_activity_time = time.time()
            return count

    def clear(self) -> None:
        """Empties all items from the FIFO queue."""
        with self._lock:
            self._last_activity_time = time.time()
            self._queue.clear()

    def is_empty(self) -> bool:
        """Returns True if the queue contains no items."""
        with self._lock:
            return len(self._queue) == 0

    def get_items(self) -> List[str]:
        """Returns a snapshot copy of all text strings currently in the queue."""
        with self._lock:
            return [item[0] for item in self._queue]

    def __len__(self) -> int:
        with self._lock:
            return len(self._queue)
