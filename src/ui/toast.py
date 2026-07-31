"""
Native Windows ToolWindow Toast Overlay for QPaste.
Uses Tkinter Toplevel + ctypes Win32 API (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
to guarantee zero taskbar presence and zero focus stealing.
"""
import tkinter as tk
import ctypes
from typing import Optional

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008


class NativeToastOverlay:
    """Manages a native, non-focus-stealing Windows toolwindow toast overlay."""

    def __init__(self, master: Optional[tk.Tk] = None) -> None:
        self.master = master
        self.window: Optional[tk.Toplevel] = None
        self.frame: Optional[tk.Frame] = None
        self.label: Optional[tk.Label] = None
        self._hide_timer_id: Optional[str] = None

    def start(self) -> None:
        """Initializes the Toast window under the main Tk root."""
        if self.master is None:
            self.master = tk.Tk()
            self.master.withdraw()

        self.window = tk.Toplevel(self.master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.94)
        self.window.configure(bg="#121824")
        self.window.withdraw()

        # Apply Win32 Extended Window Styles (ToolWindow + NoActivate + TopMost)
        self.window.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())  # type: ignore[attr-defined]
            if not hwnd:
                hwnd = self.window.winfo_id()
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)  # type: ignore[attr-defined]
            ex_style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Outer Frame with Subtle Dark Border
        self.frame = tk.Frame(self.window, bg="#181B24", highlightthickness=1, highlightbackground="#2D323E")
        self.frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Label Component
        self.label = tk.Label(
            self.frame,
            text="QPaste : ON",
            font=("Segoe UI", 11, "bold"),
            fg="#F8FAFC",
            bg="#181B24",
            padx=20,
            pady=10,
        )
        self.label.pack(expand=True)

    def show_toast(self, text: str, toast_type: str = "info") -> None:
        """Thread-safely displays the toast overlay at the bottom-right corner."""
        if not self.window and not self.master:
            return

        def _update_ui() -> None:
            if not self.window:
                self.start()

            if not self.window or not self.frame or not self.label:
                return

            # Cancel any active hide timer
            if self._hide_timer_id:
                self.window.after_cancel(self._hide_timer_id)
                self._hide_timer_id = None

            bg_color = "#181B24"        # Rich Dark Charcoal
            border_color = "#2D323E"    # Subtle Dark Border

            w, h = 220, 48
            font_style = ("Segoe UI", 11, "bold")
            timeout = 2000

            if toast_type == "on":
                fg_color = "#94A3B8"    # Clean Sky Cyan
            elif toast_type == "off":
                fg_color = "#94A3B8"    # Muted Slate
            elif toast_type == "copy_count":
                fg_color = "#94A3B8"
                w, h = 70, 50
                font_style = ("Segoe UI", 16, "bold")
                timeout = 800
            else:  # "cleared"
                fg_color = "#94A3B8"    # Pure Pearl White

            self.frame.configure(bg=bg_color, highlightbackground=border_color)
            self.label.configure(text=text, fg=fg_color, bg=bg_color, font=font_style)

            # Calculate bottom-right position dynamically
            try:
                user32 = ctypes.windll.user32  # type: ignore[attr-defined]
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
            except Exception:
                sw, sh = 1920, 1080

            x = max(0, sw - w - 30)
            y = max(0, sh - h - 70)

            self.window.geometry(f"{w}x{h}+{x}+{y}")
            self.window.deiconify()

            # Auto-hide after timeout
            self._hide_timer_id = self.window.after(timeout, self.window.withdraw)

        if self.master:
            self.master.after(0, _update_ui)
