"""
Visual Queue Inspector GUI HUD Window using Tkinter with a modern dark theme.
Allows users to view, reorder, delete, and clear queued text snippets in real-time.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from core.clipboard_queue import ClipboardQueue

DARK_BG = "#1E1E1E"
CARD_BG = "#252526"
TEXT_COLOR = "#CCCCCC"
HEADER_COLOR = "#FFFFFF"
ACCENT_COLOR = "#007ACC"
BUTTON_BG = "#333333"
BUTTON_FG = "#FFFFFF"
SELECT_BG = "#094771"


class QueueInspectorWindow:
    """Tkinter-based Visual Queue Inspector Window."""

    def __init__(self, queue: ClipboardQueue) -> None:
        self.queue = queue
        self.root: Optional[tk.Tk] = None
        self.listbox: Optional[tk.Listbox] = None
        self._is_visible = False
        self._thread: Optional[threading.Thread] = None

    def show(self) -> None:
        """Shows or focuses the Queue Inspector window (thread-safe)."""
        if self.root is None:
            self._thread = threading.Thread(target=self._run_gui, daemon=True)
            self._thread.start()
        else:
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.refresh()
            except Exception:
                pass

    def _run_gui(self) -> None:
        self.root = tk.Tk()
        self.root.title("QPaste - Queue Inspector")
        self.root.geometry("520x420")
        self.root.minsize(400, 300)
        self.root.configure(bg=DARK_BG)

        # Intercept window close (hide instead of exit process)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # --- Top Header ---
        header_frame = tk.Frame(self.root, bg=DARK_BG, pady=10, padx=15)
        header_frame.pack(fill=tk.X)

        title_label = tk.Label(
            header_frame,
            text="📋 QPaste Queue Inspector",
            font=("Segoe UI", 12, "bold"),
            bg=DARK_BG,
            fg=HEADER_COLOR,
        )
        title_label.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            header_frame,
            text="Items: 0",
            font=("Segoe UI", 10),
            bg=DARK_BG,
            fg=ACCENT_COLOR,
        )
        self.count_label.pack(side=tk.RIGHT)

        # --- Main Content Frame ---
        content_frame = tk.Frame(self.root, bg=DARK_BG, padx=15, pady=5)
        content_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(content_frame, bg=DARK_BG)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            content_frame,
            bg=CARD_BG,
            fg=TEXT_COLOR,
            selectbackground=SELECT_BG,
            selectforeground="#FFFFFF",
            font=("Consolas", 10),
            bd=0,
            highlightthickness=1,
            highlightbackground="#3C3C3C",
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # --- Action Buttons Frame ---
        btn_frame = tk.Frame(self.root, bg=DARK_BG, pady=12, padx=15)
        btn_frame.pack(fill=tk.X)

        btn_style = {
            "bg": BUTTON_BG,
            "fg": BUTTON_FG,
            "activebackground": ACCENT_COLOR,
            "activeforeground": "#FFFFFF",
            "bd": 0,
            "padx": 8,
            "pady": 4,
            "font": ("Segoe UI", 9),
            "cursor": "hand2",
        }

        up_btn = tk.Button(btn_frame, text="▲ Move Up", command=self.move_up, **btn_style)
        up_btn.pack(side=tk.LEFT, padx=3)

        down_btn = tk.Button(btn_frame, text="▼ Move Down", command=self.move_down, **btn_style)
        down_btn.pack(side=tk.LEFT, padx=3)

        del_btn = tk.Button(btn_frame, text="🗑 Delete", command=self.delete_selected, **btn_style)
        del_btn.pack(side=tk.LEFT, padx=3)

        clear_btn = tk.Button(btn_frame, text="🧹 Clear All", command=self.clear_all, **btn_style)
        clear_btn.pack(side=tk.LEFT, padx=3)

        close_btn = tk.Button(btn_frame, text="Close", command=self.hide, **btn_style)
        close_btn.pack(side=tk.RIGHT, padx=3)

        self.refresh()
        self._auto_refresh_loop()
        self.root.mainloop()

    def refresh(self) -> None:
        """Refreshes listbox items from ClipboardQueue."""
        if not self.root or not self.listbox:
            return

        try:
            selected_idx = self.listbox.curselection()
            self.listbox.delete(0, tk.END)

            items = self.queue.get_items()
            self.count_label.config(text=f"Items: {len(items)}")

            for i, text in enumerate(items, 1):
                preview = text.replace("\n", " ↵ ").replace("\r", "")
                if len(preview) > 65:
                    preview = preview[:62] + "..."
                display_str = f" [{i}]  {preview}"
                self.listbox.insert(tk.END, display_str)

            if selected_idx and selected_idx[0] < len(items):
                self.listbox.selection_set(selected_idx[0])
        except Exception:
            pass

    def _auto_refresh_loop(self) -> None:
        """Periodic auto-refresh loop running every 500ms."""
        self.refresh()
        if self.root:
            self.root.after(500, self._auto_refresh_loop)

    def move_up(self) -> None:
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if sel and sel[0] > 0:
            idx = sel[0]
            if self.queue.move_item(idx, idx - 1):
                self.refresh()
                self.listbox.selection_set(idx - 1)

    def move_down(self) -> None:
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        items_count = len(self.queue)
        if sel and sel[0] < items_count - 1:
            idx = sel[0]
            if self.queue.move_item(idx, idx + 1):
                self.refresh()
                self.listbox.selection_set(idx + 1)

    def delete_selected(self) -> None:
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            self.queue.remove_at(idx)
            self.refresh()

    def clear_all(self) -> None:
        self.queue.clear()
        self.refresh()

    def hide(self) -> None:
        """Hides the window without destroying process."""
        if self.root:
            try:
                self.root.withdraw()
            except Exception:
                pass
