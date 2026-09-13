"""
Global Keyboard Listener & Native Clipboard Monitor for QPaste.
Uses pynput for hotkey detection (F4, Shift+F4, Ctrl+V suppression)
and a native Win32 WM_CLIPBOARDUPDATE listener for copy detection.
"""
import threading
import ctypes
from ctypes import wintypes
import time
import sys
from typing import Any, Callable, Optional, Set
try:
    from pynput import keyboard
    from pynput.keyboard import Key
except (ImportError, Exception):
    keyboard = None  # type: ignore
    Key = None  # type: ignore

try:
    import pyperclip
except ImportError:
    pyperclip = None  # type: ignore

from core.clipboard_queue import ClipboardQueue
from core.state import AppState

# Windows Virtual Key Codes
VK_V = 0x56


def safe_copy(text: str, retries: int = 5, delay: float = 0.03) -> bool:
    """Safely copies text to OS clipboard with retry attempts for Win32 clipboard locks."""
    if pyperclip is None:
        return False
    for _ in range(retries):
        try:
            pyperclip.copy(text)
            return True
        except Exception:
            time.sleep(delay)
    return False


def safe_paste(retries: int = 5, delay: float = 0.03) -> str:
    """Safely reads text from OS clipboard with retry attempts for Win32 clipboard locks."""
    if pyperclip is None:
        return ""
    for _ in range(retries):
        try:
            return pyperclip.paste()
        except Exception:
            time.sleep(delay)
    return ""


class ShortcutHandler:
    """Processes hotkey events and coordinates state, queue, and clipboard operations."""

    def __init__(
        self,
        state: AppState,
        queue: ClipboardQueue,
        on_update_callback: Optional[Callable[[], None]] = None,
        on_notify_callback: Optional[Callable[[str, str], None]] = None,
        config: Optional[Any] = None,
        debounce_ms: float = 200.0,
        ignore_consecutive_duplicates: bool = True,
        duplicate_window_sec: float = 1.0,
    ) -> None:
        self.state = state
        self.queue = queue
        self.on_update_callback = on_update_callback
        self.on_notify_callback = on_notify_callback
        self.config = config
        self._copy_lock = threading.Lock()
        self._ignore_programmatic_copy = False
        self._debounce_ms = float(debounce_ms)
        self._ignore_consecutive_duplicates = bool(ignore_consecutive_duplicates)
        self._duplicate_window_sec = float(duplicate_window_sec)
        self._last_copied_text: Optional[str] = None
        self._last_copied_time: float = 0.0

    @property
    def debounce_ms(self) -> float:
        val = self.config.get("debounce_ms") if self.config and hasattr(self.config, "get") else None
        return float(val) if val is not None else self._debounce_ms

    @debounce_ms.setter
    def debounce_ms(self, val: float) -> None:
        self._debounce_ms = float(val)

    @property
    def ignore_consecutive_duplicates(self) -> bool:
        val = self.config.get("ignore_consecutive_duplicates") if self.config and hasattr(self.config, "get") else None
        return bool(val) if val is not None else self._ignore_consecutive_duplicates

    @ignore_consecutive_duplicates.setter
    def ignore_consecutive_duplicates(self, val: bool) -> None:
        self._ignore_consecutive_duplicates = bool(val)

    @property
    def duplicate_window_sec(self) -> float:
        val = self.config.get("duplicate_window_sec") if self.config and hasattr(self.config, "get") else None
        return float(val) if val is not None else self._duplicate_window_sec

    @duplicate_window_sec.setter
    def duplicate_window_sec(self, val: float) -> None:
        self._duplicate_window_sec = float(val)

    def handle_f4(self) -> None:
        """Toggles Master Queue Mode ON/OFF."""
        new_state = self.state.toggle()
        if self.on_update_callback:
            self.on_update_callback()
        if self.on_notify_callback:
            msg, tag = ("QPaste : ON", "on") if new_state else ("QPaste : OFF", "off")
            self.on_notify_callback(msg, tag)

    def handle_shift_f4(self) -> None:
        """Clears all items in the FIFO queue."""
        self.queue.clear()
        if self.on_update_callback:
            self.on_update_callback()
        if self.on_notify_callback:
            self.on_notify_callback("QPaste : Cleared", "cleared")

    def on_clipboard_changed(self, text: Optional[str]) -> None:
        """Handles external clipboard changes with debounce and deduplication."""
        if not text:
            return

        with self._copy_lock:
            if self._ignore_programmatic_copy:
                self._ignore_programmatic_copy = False
                return

            if not self.state.is_active():
                return

            now = time.time()
            elapsed = now - self._last_copied_time

            # 1. Debounce rapid format bursts (e.g. Word/Office multi-format updates)
            # 2. Consecutive duplicate suppression within window
            if text == self._last_copied_text:
                if elapsed < (self.debounce_ms / 1000.0):
                    return
                if self.ignore_consecutive_duplicates and elapsed < self.duplicate_window_sec:
                    return

            self.queue.push(text)
            self._last_copied_text = text
            self._last_copied_time = now
            q_len = len(self.queue)

        if self.on_update_callback:
            self.on_update_callback()
        if self.on_notify_callback:
            self.on_notify_callback(str(q_len), "copy_count")

    def handle_paste(self) -> bool:
        """
        Pops the oldest FIFO item and writes it to the OS clipboard
        BEFORE the native Ctrl+V keystroke reaches the active application.
        """
        if not self.state.is_active():
            return False

        with self._copy_lock:
            if self.queue.is_empty():
                return False

            text = self.queue.pop()
            if text:
                self._ignore_programmatic_copy = True
                self._last_copied_text = text
                self._last_copied_time = time.time()
                safe_copy(text)

                if self.on_update_callback:
                    self.on_update_callback()
                return True
        return False


class GlobalKeyboardListener:
    """
    Low-level global keyboard listener using pynput.
    Handles F4/Shift+F4 hotkeys and conditionally suppresses Ctrl+V
    to inject QPaste's queued clipboard content.
    """

    def __init__(self, handler: ShortcutHandler) -> None:
        self.handler = handler
        self._listener: Optional[Any] = None
        self._pressed_keys: Set = set()
        
        self._controller = keyboard.Controller() if keyboard else None
        self._simulating_v = False

    def _is_ctrl_held(self) -> bool:
        """Returns True if either Ctrl key is currently held."""
        return bool(Key and (Key.ctrl_l in self._pressed_keys or Key.ctrl_r in self._pressed_keys))

    def _is_shift_held(self) -> bool:
        """Returns True if any Shift key is currently held."""
        return bool(Key and any(k in self._pressed_keys for k in (Key.shift_l, Key.shift_r, Key.shift)))

    def _on_press(self, key) -> None:
        """Tracks key press and handles non-blocking shortcuts (F4)."""
        if not Key:
            return
        self._pressed_keys.add(key)

        # --- F4 / Shift+F4 (always active, regardless of queue mode) ---
        if key == Key.f4:
            if self._is_shift_held():
                self.handler.handle_shift_f4()
            elif not self._is_ctrl_held():
                self.handler.handle_f4()
            return

    def _on_release(self, key) -> None:
        """Tracks key releases to maintain pressed key state."""
        self._pressed_keys.discard(key)

    def win32_event_filter(self, msg, data):
        """Low-level hook filter. Suppresses native Ctrl+V when the queue has items,
        swaps the clipboard in a background thread, and injects a virtual paste."""
        # 256 = WM_KEYDOWN, 260 = WM_SYSKEYDOWN
        if msg in (256, 260) and data.vkCode == VK_V:
            ctrl_down = (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) != 0
            if ctrl_down:
                if getattr(self, '_simulating_v', False):
                    return True
                if self.handler.state.is_active() and not self.handler.queue.is_empty():
                    threading.Thread(target=self._async_paste, daemon=True).start()
                    self._listener.suppress_event()
                    return False
        return True

    def _async_paste(self):
        """Swaps the clipboard and injects a virtual paste."""
        if self.handler.handle_paste():
            self._simulating_v = True
            try:
                if self._controller:
                    self._controller.press('v')
                    self._controller.release('v')
            finally:
                self._simulating_v = False

    def start(self) -> None:
        """Starts the keyboard listener thread."""
        if not keyboard:
            return
        kwargs = {"on_press": self._on_press, "on_release": self._on_release}
        if sys.platform == "win32":
            kwargs["win32_event_filter"] = self.win32_event_filter
        self._listener = keyboard.Listener(**kwargs)
        self._listener.start()

    def stop(self) -> None:
        """Stops the global listener thread."""
        if self._listener:
            self._listener.stop()


class NativeClipboardListener:
    """
    Listens to WM_CLIPBOARDUPDATE messages from Windows.
    Runs on its own dedicated background thread with its own hidden
    message-only window and message loop — completely isolated from
    Tkinter and pynput to avoid GIL conflicts.
    """

    WM_CLIPBOARDUPDATE = 0x031D
    WM_QUIT = 0x0012

    # ctypes types that work on both 32-bit and 64-bit Python
    LRESULT = ctypes.c_int64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
    _winfunc = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    WNDPROC = _winfunc(
        LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    )

    def __init__(self, handler: ShortcutHandler):
        self.handler = handler
        self._hwnd: Optional[int] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        # prevent garbage-collection of the C callback
        self._wndproc_ref = self.WNDPROC(self._wndproc)

    # ---- public API --------------------------------------------------------

    def start(self) -> None:
        """Spawn the background listener thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to exit and clean up."""
        if not self._running:
            return
        self._running = False
        # Post WM_QUIT to break out of GetMessageW
        if self._hwnd:
            ctypes.windll.user32.PostMessageW(self._hwnd, self.WM_QUIT, 0, 0)

    # ---- internal ----------------------------------------------------------

    def _run(self) -> None:
        """Thread entry-point: register window class, create hidden window, pump messages."""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # 1. Register a unique window class
        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT), ("lpfnWndProc", self.WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
            ]

        h_instance = kernel32.GetModuleHandleW(None)

        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = h_instance
        wc.lpszClassName = "QPasteClipboardListener"

        user32.RegisterClassW(ctypes.byref(wc))

        # 2. Create a message-only window (parent = HWND_MESSAGE = -3)
        HWND_MESSAGE = wintypes.HWND(-3)
        self._hwnd = user32.CreateWindowExW(
            0, wc.lpszClassName, "QPasteHidden", 0,
            0, 0, 0, 0, HWND_MESSAGE, None, h_instance, None
        )

        # 3. Register for clipboard-update notifications
        user32.AddClipboardFormatListener(self._hwnd)

        # 4. Standard Win32 message pump
        msg = wintypes.MSG()
        while self._running:
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        # 5. Cleanup
        try:
            user32.RemoveClipboardFormatListener(self._hwnd)
            user32.DestroyWindow(self._hwnd)
        except Exception:
            pass

    def _wndproc(self, hwnd, msg, wparam, lparam):
        """Called by Windows whenever the hidden window receives a message."""
        if msg == self.WM_CLIPBOARDUPDATE and self._running:
            try:
                self.handler.on_clipboard_changed(safe_paste())
            except Exception:
                pass
        user32 = ctypes.windll.user32
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = wintypes.LPARAM
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
