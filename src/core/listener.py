"""
Global Keyboard Listener & Event Interceptor for QPaste.
Uses pynput keyboard.Listener for reliable low-level keystroke detection
with proper clipboard timing, FIFO paste injection, and smart
context-aware Ctrl+Z undo support.
"""
import time
import threading
import ctypes
from typing import Callable, Optional, Set
from pynput import keyboard
from pynput.keyboard import Key, KeyCode
import pyperclip

from core.clipboard_queue import ClipboardQueue
from core.state import AppState

# Windows Virtual Key Codes
VK_C = 0x43  # 67
VK_V = 0x56  # 86
VK_Z = 0x5A  # 90


def _get_vk(key) -> Optional[int]:
    """Extract the Windows virtual key code from a pynput key event.
    Returns None for non-KeyCode keys (modifiers, function keys, etc.)."""
    if isinstance(key, KeyCode):
        return getattr(key, 'vk', None)
    return None


class ShortcutHandler:
    """Processes hotkey events and coordinates state, queue, and clipboard operations."""

    UNDO_WINDOW_SECONDS = 5.0       # Max time after paste to allow Ctrl+Z re-enqueue
    CLIPBOARD_READ_DELAY = 0.15     # Seconds to wait for OS clipboard to finish writing

    def __init__(
        self,
        state: AppState,
        queue: ClipboardQueue,
        on_update_callback: Optional[Callable[[], None]] = None,
        on_notify_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.state = state
        self.queue = queue
        self.on_update_callback = on_update_callback
        self.on_notify_callback = on_notify_callback
        self._last_pasted_text: Optional[str] = None
        self._paste_timestamp: float = 0.0
        self._copy_lock = threading.Lock()

    def handle_f4(self) -> None:
        """Toggles Master Queue Mode ON/OFF."""
        new_state = self.state.toggle()
        if self.on_update_callback:
            self.on_update_callback()
        if self.on_notify_callback:
            if new_state:
                self.on_notify_callback("QPaste : ON", "on")
            else:
                self.on_notify_callback("QPaste : OFF", "off")

    def handle_shift_f4(self) -> None:
        """Clears all items in the FIFO queue."""
        self.queue.clear()
        self._last_pasted_text = None
        if self.on_update_callback:
            self.on_update_callback()
        if self.on_notify_callback:
            self.on_notify_callback("QPaste : Cleared", "cleared")

    def handle_copy(self) -> None:
        """
        Intercepts copy event when ACTIVE.
        Spawns a background thread that waits for the OS to finish writing
        to the clipboard, then reads it and enqueues the text into the FIFO queue.
        The native Ctrl+C is NOT suppressed — the OS copy completes normally.
        """
        if not self.state.is_active():
            return

        threading.Thread(target=self._read_and_enqueue, daemon=True).start()

    def _read_and_enqueue(self) -> None:
        """Background worker: waits for clipboard, then enqueues text."""
        time.sleep(self.CLIPBOARD_READ_DELAY)
        with self._copy_lock:
            try:
                text = pyperclip.paste()
                if text:
                    self.queue.push(text)
                    if self.on_update_callback:
                        self.on_update_callback()
            except Exception:
                pass

    def handle_paste(self) -> bool:
        """
        Pops the oldest FIFO item and writes it to the OS clipboard
        BEFORE the native Ctrl+V keystroke reaches the active application.

        Because pynput's low-level hook fires before the app's message loop,
        the clipboard content is already swapped by the time the application
        processes WM_KEYDOWN for 'V' and reads the clipboard.

        Returns True if clipboard was swapped with a queue item.
        Returns False if queue was empty (native paste proceeds unchanged).
        """
        if not self.state.is_active() or self.queue.is_empty():
            return False

        text = self.queue.pop()
        if text:
            pyperclip.copy(text)
            self._last_pasted_text = text
            self._paste_timestamp = time.time()
            if self.on_update_callback:
                self.on_update_callback()
            return True
        return False

    def handle_undo(self) -> bool:
        """
        Smart Ctrl+Z handler with window context awareness (PRD Section 3.6).

        When a FIFO paste was recently performed:
          - In text editors/input fields: re-enqueues the pasted text to the
            FRONT of the queue (appendleft). The native Ctrl+Z also fires,
            undoing the paste in the editor. Net effect: paste is reversed
            and the text is available for re-pasting.
          - In Windows File Explorer (explorer.exe): passes through entirely
            so native file undo works (e.g., restore deleted files).

        Returns True if QPaste re-enqueued text.
        Returns False if the event should pass through to native undo.
        """
        if not self.state.is_active():
            return False

        if not self._last_pasted_text:
            return False

        if (time.time() - self._paste_timestamp) > self.UNDO_WINDOW_SECONDS:
            self._last_pasted_text = None
            return False

        # Bypass re-enqueue if active window is File Explorer
        if self._is_explorer_active():
            return False

        # Re-enqueue to front of queue so it can be re-pasted
        self.queue.push_front(self._last_pasted_text)
        self._last_pasted_text = None
        if self.on_update_callback:
            self.on_update_callback()
        if self.on_notify_callback:
            self.on_notify_callback("QPaste : Undo", "info")
        return True

    @staticmethod
    def _is_explorer_active() -> bool:
        """Checks if the foreground window belongs to explorer.exe."""
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False

            pid = ctypes.c_ulong(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
            )
            if not handle:
                return False

            try:
                buf = ctypes.create_unicode_buffer(260)
                size = ctypes.c_ulong(260)
                kernel32.QueryFullProcessImageNameW(
                    handle, 0, buf, ctypes.byref(size)
                )
                return buf.value.lower().endswith("explorer.exe")
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False


class GlobalKeyboardListener:
    """
    Low-level global keyboard listener using pynput.keyboard.Listener.

    Uses a WH_KEYBOARD_LL hook (via pynput) which fires BEFORE the target
    application's message queue receives the keystroke. This guarantees that
    clipboard swaps in handle_paste() complete before the app reads the
    clipboard for its native Ctrl+V handling.
    """

    def __init__(self, handler: ShortcutHandler) -> None:
        self.handler = handler
        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys: Set = set()

    def _is_ctrl_held(self) -> bool:
        """Returns True if either Ctrl key is currently held."""
        return Key.ctrl_l in self._pressed_keys or Key.ctrl_r in self._pressed_keys

    def _is_shift_held(self) -> bool:
        """Returns True if any Shift key is currently held."""
        return (
            Key.shift_l in self._pressed_keys
            or Key.shift_r in self._pressed_keys
            or Key.shift in self._pressed_keys
        )

    def _on_press(self, key) -> None:
        """Low-level key press handler. Fires before the active application."""
        self._pressed_keys.add(key)

        # --- F4 / Shift+F4 (always active, regardless of queue mode) ---
        if key == Key.f4:
            if self._is_shift_held():
                self.handler.handle_shift_f4()
            elif not self._is_ctrl_held():
                self.handler.handle_f4()
            return

        # --- Ctrl+{C,V,Z} combos ---
        if not self._is_ctrl_held():
            return

        vk = _get_vk(key)
        if vk is None:
            return

        if vk == VK_C:
            # Ctrl+C: let the OS copy finish, then enqueue from clipboard
            self.handler.handle_copy()

        elif vk == VK_V:
            # Ctrl+V: swap clipboard content BEFORE native paste fires
            self.handler.handle_paste()

        elif vk == VK_Z:
            # Ctrl+Z: smart undo with explorer.exe bypass
            self.handler.handle_undo()

    def _on_release(self, key) -> None:
        """Tracks key releases to maintain pressed key state."""
        self._pressed_keys.discard(key)

    def start(self) -> None:
        """Starts the background keyboard listener thread."""
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        """Stops the keyboard listener thread."""
        if self._listener:
            self._listener.stop()
