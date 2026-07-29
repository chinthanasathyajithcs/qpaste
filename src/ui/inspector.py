"""
Visual Queue Inspector GUI HUD Window using Tkinter with a modern dark theme.
Allows users to view, inspect full text details, reorder, delete, copy, promote,
and clear queued text snippets in real-time.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

import pyperclip
from core.clipboard_queue import ClipboardQueue

# Modern Dark Theme Color Palette
DARK_BG = "#12161F"          # Deep midnight background
CARD_BG = "#1A1F2C"          # Rich card container
LIST_BG = "#1E2433"          # Soft list container
TEXT_PRIMARY = "#F8FAFC"      # Pure white text
TEXT_SECONDARY = "#94A3B8"    # Muted slate text
ACCENT_PRIMARY = "#0EA5E9"    # Sky Cyan accent
ACCENT_HOVER = "#0284C7"      # Darker cyan hover
BUTTON_BG = "#2A3142"        # Muted button fill
BUTTON_BORDER = "#3D465C"    # Subtle button border
SELECT_BG = "#0369A1"        # Vivid selection highlight
EMPTY_TEXT_COLOR = "#64748B"   # Muted placeholder text


class QueueInspectorWindow:
    """Tkinter-based Visual Queue Inspector Window."""

    def __init__(self, queue: ClipboardQueue, master: Optional[tk.Tk] = None) -> None:
        self.queue = queue
        self.master = master
        self.root: Optional[tk.Toplevel] = None
        self.listbox: Optional[tk.Listbox] = None
        self.preview_text: Optional[tk.Text] = None
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

        self.root.title("QPaste - Queue Inspector")
        self.root.geometry("580x520")
        self.root.minsize(460, 380)
        self.root.configure(bg=DARK_BG)

        # Intercept window close (hide instead of exit process)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # --- Top Header Bar ---
        header_frame = tk.Frame(self.root, bg=DARK_BG, pady=12, padx=16)
        header_frame.pack(fill=tk.X)

        title_label = tk.Label(
            header_frame,
            text="📋 QPaste Queue Inspector",
            font=("Segoe UI", 12, "bold"),
            bg=DARK_BG,
            fg=TEXT_PRIMARY,
        )
        title_label.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            header_frame,
            text="Items: 0 / 25",
            font=("Segoe UI", 10, "bold"),
            bg=DARK_BG,
            fg=ACCENT_PRIMARY,
        )
        self.count_label.pack(side=tk.RIGHT)

        # --- Main Content Split (List + Detail Pane) ---
        main_paned = tk.PanedWindow(
            self.root,
            orient=tk.VERTICAL,
            bg=DARK_BG,
            sashwidth=4,
            sashrelief=tk.FLAT,
            bd=0,
        )
        main_paned.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # 1. Top Pane: Queue List Container
        list_container = tk.Frame(main_paned, bg=CARD_BG, bd=1, relief=tk.SOLID)
        list_container.config(highlightbackground=BUTTON_BORDER, highlightthickness=1)
        main_paned.add(list_container, minsize=160, height=220)

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

        # Empty State Placeholder Label inside list container
        self.empty_label = tk.Label(
            list_container,
            text="✨ Queue is empty.\nCopy text with Ctrl+C to start collecting snippets!",
            font=("Segoe UI", 10, "italic"),
            bg=LIST_BG,
            fg=EMPTY_TEXT_COLOR,
            justify=tk.CENTER,
        )

        # 2. Bottom Pane: Full Snippet Detail View
        detail_container = tk.Frame(main_paned, bg=CARD_BG, bd=1, relief=tk.SOLID)
        detail_container.config(highlightbackground=BUTTON_BORDER, highlightthickness=1)
        main_paned.add(detail_container, minsize=100, height=140)

        detail_header = tk.Frame(detail_container, bg=CARD_BG, padx=8, pady=4)
        detail_header.pack(fill=tk.X)

        detail_title = tk.Label(
            detail_header,
            text="Full Snippet Preview:",
            font=("Segoe UI", 9, "bold"),
            bg=CARD_BG,
            fg=TEXT_SECONDARY,
        )
        detail_title.pack(side=tk.LEFT)

        detail_scroll = tk.Scrollbar(detail_container, bg=CARD_BG)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_text = tk.Text(
            detail_container,
            bg=DARK_BG,
            fg=TEXT_PRIMARY,
            font=("Consolas", 9),
            bd=0,
            highlightthickness=0,
            wrap=tk.WORD,
            yscrollcommand=detail_scroll.set,
            state=tk.DISABLED,
            height=6,
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))
        detail_scroll.config(command=self.preview_text.yview)

        # --- Event Bindings ---
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", lambda e: self.promote_selected())
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())
        self.listbox.bind("<Control-c>", lambda e: self.copy_selected())

        # --- Action Control Bar ---
        btn_frame = tk.Frame(self.root, bg=DARK_BG, pady=12, padx=16)
        btn_frame.pack(fill=tk.X)

        btn_style = {
            "bg": BUTTON_BG,
            "fg": TEXT_PRIMARY,
            "activebackground": ACCENT_PRIMARY,
            "activeforeground": "#FFFFFF",
            "bd": 0,
            "padx": 10,
            "pady": 5,
            "font": ("Segoe UI", 9, "bold"),
            "cursor": "hand2",
            "relief": tk.FLAT,
        }

        promote_btn = tk.Button(
            btn_frame,
            text="⭐ Promote Next",
            command=self.promote_selected,
            **btn_style,
        )
        promote_btn.pack(side=tk.LEFT, padx=(0, 4))

        copy_btn = tk.Button(
            btn_frame,
            text="📋 Copy Selected",
            command=self.copy_selected,
            **btn_style,
        )
        copy_btn.pack(side=tk.LEFT, padx=4)

        up_btn = tk.Button(btn_frame, text="▲ Up", command=self.move_up, **btn_style)
        up_btn.pack(side=tk.LEFT, padx=4)

        down_btn = tk.Button(btn_frame, text="▼ Down", command=self.move_down, **btn_style)
        down_btn.pack(side=tk.LEFT, padx=4)

        del_btn = tk.Button(
            btn_frame,
            text="🗑 Delete",
            command=self.delete_selected,
            **btn_style,
        )
        del_btn.pack(side=tk.LEFT, padx=4)

        clear_btn = tk.Button(
            btn_frame,
            text="🧹 Clear All",
            command=self.clear_all,
            **btn_style,
        )
        clear_btn.pack(side=tk.LEFT, padx=4)

        close_btn = tk.Button(btn_frame, text="Close", command=self.hide, **btn_style)
        close_btn.pack(side=tk.RIGHT, padx=(4, 0))

        self.refresh()
        self._auto_refresh_loop()

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
                self.count_label.config(text=f"Items: {len(items)} / {max_capacity}")

            if not items:
                if self.empty_label:
                    self.empty_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
                self._update_preview("")
                return
            else:
                if self.empty_label:
                    self.empty_label.place_forget()

            for i, text in enumerate(items, 1):
                preview = text.replace("\n", " ↵ ").replace("\r", "")
                if len(preview) > 60:
                    preview = preview[:57] + "..."
                display_str = f" [{i:02d}]  {preview}"
                self.listbox.insert(tk.END, display_str)

            if selected_idx and selected_idx[0] < len(items):
                self.listbox.selection_set(selected_idx[0])
                self._update_preview(items[selected_idx[0]])
            elif items:
                self._update_preview(items[0])
        except Exception:
            pass

    def _auto_refresh_loop(self) -> None:
        """Periodic auto-refresh loop running every 500ms."""
        self.refresh()
        if self.root:
            self.root.after(500, self._auto_refresh_loop)

    def _on_select(self, event=None) -> None:
        """Fires when user selects an item in the listbox."""
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            item_text = self.queue.get_item(idx)
            if item_text is not None:
                self._update_preview(item_text)

    def _update_preview(self, text: str) -> None:
        """Updates the full snippet detail text widget."""
        if not self.preview_text:
            return
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert(tk.END, text)
        self.preview_text.config(state=tk.DISABLED)

    def promote_selected(self) -> None:
        """Promotes the selected item to position 0 so it pastes next."""
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            if self.queue.promote_to_front(idx):
                self.refresh()
                self.listbox.selection_set(0)
                self._on_select()

    def copy_selected(self) -> None:
        """Copies the selected snippet directly to the OS clipboard."""
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if sel:
            idx = sel[0]
            text = self.queue.get_item(idx)
            if text:
                pyperclip.copy(text)

    def move_up(self) -> None:
        if not self.listbox:
            return
        sel = self.listbox.curselection()
        if sel and sel[0] > 0:
            idx = sel[0]
            if self.queue.move_item(idx, idx - 1):
                self.refresh()
                self.listbox.selection_set(idx - 1)
                self._on_select()

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
                self._on_select()

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
