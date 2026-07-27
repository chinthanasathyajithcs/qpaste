"""
Thread-safe Application State Manager for QPaste.
Manages global Master Toggle (F4) Queue Mode state (ACTIVE vs PAUSED).
"""
import threading


class AppState:
    """Thread-safe state manager for QPaste."""

    def __init__(self, initial_active: bool = True) -> None:
        self._active: bool = initial_active
        self._lock: threading.Lock = threading.Lock()

    def is_active(self) -> bool:
        """Returns True if Queue Mode is ACTIVE (ON)."""
        with self._lock:
            return self._active

    def toggle(self) -> bool:
        """Toggles Queue Mode state between ACTIVE and PAUSED. Returns new state."""
        with self._lock:
            self._active = not self._active
            return self._active

    def set_active(self, active: bool) -> None:
        """Explicitly sets Queue Mode state."""
        with self._lock:
            self._active = active
