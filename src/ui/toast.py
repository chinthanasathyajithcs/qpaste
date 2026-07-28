"""
Native Windows ToolWindow Toast Overlay for QPaste.
Uses Tkinter + ctypes Win32 API (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
to guarantee zero taskbar presence and zero focus stealing.
"""
import tkinter as tk
import ctypes
import threading
import time
from typing import Optional

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008


class NativeToastOverlay:
    """Manages a native, non-focus-stealing Windows toolwindow toast overlay."""

    def __init__(self) -> None:
        self.root: Optional[tk.Tk] = None
        self.frame: Optional[tk.Frame] = None
        self.label: Optional[tk.Label] = None
        self._hide_timer_id: Optional[str] = None
        self._initialized = threading.Event()

    def start(self) -> None:
        """Initializes and runs the Tkinter event loop in a dedicated thread."""
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.94)
        self.root.configure(bg="#121824")
        self.root.withdraw()

        # Apply Win32 Extended Window Styles (ToolWindow + NoActivate + TopMost)
        self.root.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) # type: ignore[attr-defined]
            if not hwnd:
                hwnd = self.root.winfo_id()
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE) # type: ignore[attr-defined]
            ex_style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style) # type: ignore[attr-defined]
        except Exception:
            pass

        # Outer Frame with Subtle Dark Border (no neon/glowing effects)
        self.frame = tk.Frame(self.root, bg="#181B24", highlightthickness=1, highlightbackground="#2D323E")
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

        self._initialized.set()
        self.root.mainloop()

    def show_toast(self, text: str, toast_type: str = "info") -> None:
        """Thread-safely displays the toast overlay at the bottom-right corner."""
        if not self._initialized.is_set() or not self.root:
            return

        def _update_ui() -> None:
            if not self.root or not self.frame or not self.label:
                return

            # Cancel any active hide timer
            if self._hide_timer_id:
                self.root.after_cancel(self._hide_timer_id)
                self._hide_timer_id = None

            # Clean, Minimal, Rich Aesthetic (No glowing effects)
            bg_color = "#181B24"        # Rich Dark Charcoal
            border_color = "#2D323E"    # Subtle Dark Border

            if toast_type == "on":
                fg_color = "#94A3B8"    # Clean Sky Cyan
                formatted_text = text
            elif toast_type == "off":
                fg_color = "#94A3B8"    # Muted Slate
                formatted_text = text
            else:  # "cleared"
                fg_color = "#94A3B8"    # Pure Pearl White
                formatted_text = text

            self.frame.configure(bg=bg_color, highlightbackground=border_color)
            self.label.configure(text=formatted_text, fg=fg_color, bg=bg_color)

            # Calculate bottom-right position dynamically
            try:
                user32 = ctypes.windll.user32 # type: ignore[attr-defined]
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
            except Exception:
                sw, sh = 1920, 1080

            w, h = 220, 48
            x = max(0, sw - w - 30)
            y = max(0, sh - h - 70)

            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.root.deiconify()

            # Auto-hide after 2 seconds
            self._hide_timer_id = self.root.after(2000, self.root.withdraw)

        self.root.after(0, _update_ui)
