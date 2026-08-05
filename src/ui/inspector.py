"""
Visual Queue Inspector GUI HUD Window using Tkinter with a modern dark theme.
Minimalist layout displaying live queued text items with basic delete and clear options.
"""
import os
import sys
import threading
import tkinter as tk
from typing import Optional

from core.clipboard_queue import ClipboardQueue

# Modern Dark Theme Color Palette
DARK_BG = "#12161F"          # Deep midnight background
CARD_BG = "#1A1F2C"          # Rich card container
LIST_BG = "#1E2433"          # Soft list container
TEXT_PRIMARY = "#F8FAFC"      # Pure white text
TEXT_SECONDARY = "#94A3B8"    # Muted slate text
ACCENT_PRIMARY = "#0EA5E9"    # Sky Cyan accent
BUTTON_BG = "#2A3142"        # Muted button fill
BUTTON_BORDER = "#3D465C"    # Subtle button border
SELECT_BG = "#0369A1"        # Vivid selection highlight
EMPTY_TEXT_COLOR = "#64748B"   # Muted placeholder text


class QueueInspectorWindow:
    """Minimal Tkinter-based Visual Queue Inspector Window."""

    def __init__(self, queue: ClipboardQueue, master: Optional[tk.Tk] = None) -> None:
        self.queue = queue
        self.master = master
        self.root: Optional[tk.Toplevel] = None
        self.listbox: Optional[tk.Listbox] = None
        self.count_label: Optional[tk.Label] = None
        self.empty_label: Optional[tk.Label] = None

    def show(self) -> None:
        """Shows or focuses the Queue Inspector window (thread-safe)."""
        if self.master:
            self.master.after(0, self._show_on_main_thread)
        else:
            self._show_on_main_thread()

    def _show_on_main_thread(self) -> None:
        if self.root is None:
            self._build_gui()
        else:
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.refresh()
            except Exception:
                pass

    def _build_gui(self) -> None:
        if self.master:
            self.root = tk.Toplevel(self.master)
        else:
            self.master = tk.Tk()
            self.root = tk.Toplevel(self.master)
            self.master.withdraw()

        self.root.title("QPaste Queue")
        self.root.geometry("400x300")
        self.root.minsize(340, 240)
        self.root.configure(bg=DARK_BG)

        # Intercept window close (hide instead of exit process)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # --- Compact Top Header Bar ---
        header_frame = tk.Frame(self.root, bg=DARK_BG, pady=8, padx=12)
        header_frame.pack(fill=tk.X)

        title_label = tk.Label(
            header_frame,
            text="📋 QPaste Queue",
            font=("Segoe UI", 11, "bold"),
            bg=DARK_BG,
            fg=TEXT_PRIMARY,
        )
        title_label.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            header_frame,
            text="0 / 25",
            font=("Segoe UI", 9, "bold"),
            bg=DARK_BG,
            fg=ACCENT_PRIMARY,
        )
        self.count_label.pack(side=tk.RIGHT)

        # --- Single List Container ---
        list_container = tk.Frame(self.root, bg=CARD_BG, bd=1, relief=tk.SOLID)
        list_container.config(highlightbackground=BUTTON_BORDER, highlightthickness=1)
        list_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        scrollbar = tk.Scrollbar(list_container, bg=CARD_BG)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_container,
            bg=LIST_BG,
            fg=TEXT_PRIMARY,
            selectbackground=SELECT_BG,
            selectforeground="#FFFFFF",
            font=("Consolas", 10),
            bd=0,
            highlightthickness=0,
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            activestyle="none",
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # Empty State Placeholder Label
        self.empty_label = tk.Label(
            list_container,
            text="Queue is empty",
            font=("Segoe UI", 10, "italic"),
            bg=LIST_BG,
            fg=EMPTY_TEXT_COLOR,
            justify=tk.CENTER,
        )

        # --- Event Bindings ---
        self.listbox.bind("<Double-Button-1>", lambda e: self.delete_selected())
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())

        # --- Minimal Action Control Bar (Delete, Clear All, Close) ---
        btn_frame = tk.Frame(self.root, bg=DARK_BG, pady=8, padx=12)
        btn_frame.pack(fill=tk.X)

        btn_style = {
            "bg": BUTTON_BG,
            "fg": TEXT_PRIMARY,
            "activebackground": ACCENT_PRIMARY,
            "activeforeground": "#FFFFFF",
            "bd": 0,
            "padx": 8,
            "pady": 4,
            "font": ("Segoe UI", 9, "bold"),
            "cursor": "hand2",
            "relief": tk.FLAT,
        }

        del_btn = tk.Button(
            btn_frame,
            text="Delete",
            command=self.delete_selected,
            **btn_style,
        )
        del_btn.pack(side=tk.LEFT, padx=(0, 4))

        clear_btn = tk.Button(
            btn_frame,
            text="Clear All",
            command=self.clear_all,
            **btn_style,
        )
        clear_btn.pack(side=tk.LEFT, padx=4)

        close_btn = tk.Button(btn_frame, text="Close", command=self.hide, **btn_style)
        close_btn.pack(side=tk.RIGHT)

        self.refresh()

    def refresh(self) -> None:
        """Refreshes listbox items and count label from ClipboardQueue."""
        if not self.root or not self.listbox:
            return

        try:
            selected_idx = self.listbox.curselection()
            self.listbox.delete(0, tk.END)

            items = self.queue.get_items()
            max_capacity = getattr(self.queue, "max_size", 25)

            if self.count_label:
                self.count_label.config(text=f"{len(items)} / {max_capacity}")

            if not items:
                if self.empty_label:
                    self.empty_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                return
            else:
                if self.empty_label:
                    self.empty_label.place_forget()

            for i, text in enumerate(items, 1):
                preview = text.replace("\n", " ↵ ").replace("\r", "")
                if len(preview) > 50:
                    preview = preview[:47] + "..."
                display_str = f" [{i:02d}]  {preview}"
                self.listbox.insert(tk.END, display_str)

            if selected_idx and selected_idx[0] < len(items):
                self.listbox.selection_set(selected_idx[0])
        except Exception:
            pass

    def delete_selected(self) -> None:
        """Deletes the selected item from queue."""
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            self.queue.remove_at(idx)
            self.refresh()

    def clear_all(self) -> None:
        """Clears all items from the queue."""
        self.queue.clear()
        self.refresh()

    def hide(self) -> None:
        """Hides the window without destroying process."""
        if self.root:
            try:
                self.root.withdraw()
            except Exception:
                pass
