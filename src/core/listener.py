"""
Global Keyboard Listener & Native Clipboard Monitor for QPaste.
Uses pynput for hotkey detection (F4, Shift+F4, Ctrl+V suppression)
and a native Win32 WM_CLIPBOARDUPDATE listener for copy detection.
"""
import threading
import ctypes
from ctypes import wintypes
import sys
from typing import Callable, Optional, Set
from pynput import keyboard
from pynput.keyboard import Key
import pyperclip

from core.clipboard_queue import ClipboardQueue
from core.state import AppState

# Windows Virtual Key Codes
VK_V = 0x56


class ShortcutHandler:
    """Processes hotkey events and coordinates state, queue, and clipboard operations."""

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
        self._copy_lock = threading.Lock()
        self._ignore_programmatic_copy = False

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
        if self.on_update_callback:
            self.on_update_callback()
        if self.on_notify_callback:
            self.on_notify_callback("QPaste : Cleared", "cleared")

    def on_clipboard_changed(self, text: str) -> None:
        with self._copy_lock:
            if self._ignore_programmatic_copy:
                self._ignore_programmatic_copy = False
                return

        if not self.state.is_active():
            return

        if text:
            with self._copy_lock:
                self.queue.push(text)
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
                pyperclip.copy(text)
                
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
        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys: Set = set()
        
        self._controller = keyboard.Controller()
        self._simulating_v = False

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
        """Tracks key press and handles non-blocking shortcuts (F4)."""
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
        if msg == 256 or msg == 260:
            vk = data.vkCode
            if vk == VK_V:
                ctrl_down = (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) != 0
                if ctrl_down:
                    # If this is our own injected V, let it pass to the OS
                    if getattr(self, '_simulating_v', False):
                        return True
                        
                    # Suppress the native V and do the heavy lifting in a new thread
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
                # The user is already physically holding Ctrl. Injecting a V will paste.
                self._controller.press('v')
                self._controller.release('v')
            finally:
                self._simulating_v = False

    def start(self) -> None:
        """Starts the keyboard listener thread."""
        
        kwargs = {
            "on_press": self._on_press,
            "on_release": self._on_release,
        }
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
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        LRESULT = ctypes.c_int64
    else:
        LRESULT = ctypes.c_long

    WNDPROC = ctypes.WINFUNCTYPE(
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
                ("style", wintypes.UINT),
                ("lpfnWndProc", self.WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
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
            0,                          # dwExStyle
            wc.lpszClassName,           # lpClassName
            "QPasteHidden",             # lpWindowName
            0,                          # dwStyle
            0, 0, 0, 0,                 # x, y, w, h
            HWND_MESSAGE,               # hWndParent
            None,                       # hMenu
            h_instance,                 # hInstance
            None,                       # lpParam
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
                text = pyperclip.paste()
                self.handler.on_clipboard_changed(text)
            except Exception:
                pass
        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
