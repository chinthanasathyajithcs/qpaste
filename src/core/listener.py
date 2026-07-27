"""
Global Keyboard Listener & Event Interceptor for QPaste.
Uses pynput for low-latency background keystroke detection.
"""
import time
from typing import Callable, Optional
from pynput import keyboard
import pyperclip

from core.clipboard_queue import ClipboardQueue
from core.state import AppState


class ShortcutHandler:
    """Processes hotkey events and coordinates state, queue, and clipboard operations."""

    def __init__(
        self,
        state: AppState,
        queue: ClipboardQueue,
        on_update_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.state = state
        self.queue = queue
        self.on_update_callback = on_update_callback

    def handle_f4(self) -> None:
        """Toggles Master Queue Mode ON/OFF."""
        new_state = self.state.toggle()
        if self.on_update_callback:
            self.on_update_callback()

    def handle_shift_f4(self) -> None:
        """Clears all items in the FIFO queue."""
        self.queue.clear()
        if self.on_update_callback:
            self.on_update_callback()

    def handle_copy(self) -> None:
        """Intercepts copy event when ACTIVE, reads system clipboard, and enqueues snippet."""
        if not self.state.is_active():
            return
        # Brief pause to allow OS clipboard buffer to fill
        time.sleep(0.05)
        text = pyperclip.paste()
        if text:
            self.queue.push(text)
            if self.on_update_callback:
                self.on_update_callback()

    def handle_paste(self) -> Optional[str]:
        """Pops oldest item from queue and updates OS clipboard for pasting when ACTIVE."""
        if not self.state.is_active() or self.queue.is_empty():
            return None

        text = self.queue.pop()
        if text:
            pyperclip.copy(text)
            if self.on_update_callback:
                self.on_update_callback()
        return text


class GlobalKeyboardListener:
    """Listens globally for hotkey combinations using pynput."""

    def __init__(self, handler: ShortcutHandler) -> None:
        self.handler = handler
        self._listener: Optional[keyboard.Listener] = None

    def start(self) -> None:
        """Starts the background keyboard listener thread."""
        self._listener = keyboard.GlobalHotKeys(
            {
                "<f4>": self.handler.handle_f4,
                "<shift>+<f4>": self.handler.handle_shift_f4,
                "<ctrl>+c": self.handler.handle_copy,
                "<ctrl>+v": self.handler.handle_paste,
            }
        )
        self._listener.start()

    def stop(self) -> None:
        """Stops the keyboard listener thread."""
        if self._listener:
            self._listener.stop()
