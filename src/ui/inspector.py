"""
Visual Queue Inspector GUI HUD Window using Tkinter with a modern dark theme.
Features live queue management and auto-clear timer settings.
"""
import os
import sys
import threading
import tkinter as tk
from typing import Optional

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig

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

DURATION_OPTIONS = [
    ("30 Seconds", 30),
    ("1 Minute", 60),
    ("5 Minutes", 300),
    ("15 Minutes", 900),
    ("30 Minutes", 1800),
    ("1 Hour", 3600),
]


class QueueInspectorWindow:
    """Tkinter-based Visual Queue Inspector Window with Settings tab."""

    def __init__(
        self,
        queue: ClipboardQueue,
        config: Optional[AppConfig] = None,
        master: Optional[tk.Tk] = None,
    ) -> None:
        self.queue = queue
        self.config = config or AppConfig()
        self.master = master
        self.root: Optional[tk.Toplevel] = None
        self.listbox: Optional[tk.Listbox] = None
        self.count_label: Optional[tk.Label] = None
        self.empty_label: Optional[tk.Label] = None

        self.queue_frame: Optional[tk.Frame] = None
        self.settings_frame: Optional[tk.Frame] = None
        self.queue_tab_btn: Optional[tk.Button] = None
        self.settings_tab_btn: Optional[tk.Button] = None

        self.auto_clear_var: Optional[tk.BooleanVar] = None
        self.duration_var: Optional[tk.StringVar] = None

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

        self.root.title("QPaste Inspector & Settings")
        self.root.geometry("420x340")
        self.root.minsize(360, 280)
        self.root.configure(bg=DARK_BG)

        # Set title bar & taskbar window icon
        def _get_asset_path(filename: str) -> str:
            if hasattr(sys, "_MEIPASS"):
                return os.path.join(sys._MEIPASS, "assets", filename)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base_dir, "..", "assets", filename)

        icon_ico = _get_asset_path("icon.ico")
        icon_png = _get_asset_path("icon.png")
        if os.path.exists(icon_ico):
            try:
                self.root.iconbitmap(icon_ico)
            except Exception:
                pass
        elif os.path.exists(icon_png):
            try:
                img = tk.PhotoImage(file=icon_png)
                self.root.iconphoto(True, img)
            except Exception:
                pass

        # Intercept window close (hide instead of exit process)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # --- Top Navigation / Header Bar ---
        header_frame = tk.Frame(self.root, bg=DARK_BG, pady=6, padx=12)
        header_frame.pack(fill=tk.X)

        tabs_frame = tk.Frame(header_frame, bg=DARK_BG)
        tabs_frame.pack(side=tk.LEFT)

        tab_style = {
            "bg": DARK_BG,
            "fg": TEXT_SECONDARY,
            "activebackground": CARD_BG,
            "activeforeground": TEXT_PRIMARY,
            "bd": 0,
            "padx": 10,
            "pady": 5,
            "font": ("Segoe UI", 9, "bold"),
            "cursor": "hand2",
            "relief": tk.FLAT,
            "anchor": tk.CENTER,
        }

        self.queue_tab_btn = tk.Button(
            tabs_frame,
            text="☰  Queue",
            command=self._switch_to_queue_tab,
            **tab_style,
        )
        self.queue_tab_btn.pack(side=tk.LEFT, padx=(0, 4))

        self.settings_tab_btn = tk.Button(
            tabs_frame,
            text="⚙  Settings",
            command=self._switch_to_settings_tab,
            **tab_style,
        )
        self.settings_tab_btn.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            header_frame,
            text="0 / 25",
            font=("Segoe UI", 9, "bold"),
            bg=DARK_BG,
            fg=ACCENT_PRIMARY,
        )
        self.count_label.pack(side=tk.RIGHT)

        # --- Content Container ---
        content_container = tk.Frame(self.root, bg=DARK_BG)
        content_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # 1. QUEUE TAB FRAME
        self.queue_frame = tk.Frame(content_container, bg=DARK_BG)

        list_container = tk.Frame(self.queue_frame, bg=CARD_BG, bd=1, relief=tk.SOLID)
        list_container.config(highlightbackground=BUTTON_BORDER, highlightthickness=1)
        list_container.pack(fill=tk.BOTH, expand=True)

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
            text="No items in queue",
            font=("Segoe UI", 10),
            bg=LIST_BG,
            fg=EMPTY_TEXT_COLOR,
            justify=tk.CENTER,
        )

        # Queue Action Bar
        queue_btn_frame = tk.Frame(self.queue_frame, bg=DARK_BG, pady=8)
        queue_btn_frame.pack(fill=tk.X)

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

        del_btn = tk.Button(queue_btn_frame, text="Delete", command=self.delete_selected, **btn_style)
        del_btn.pack(side=tk.LEFT, padx=(0, 4))

        clear_btn = tk.Button(queue_btn_frame, text="Clear All", command=self.clear_all, **btn_style)
        clear_btn.pack(side=tk.LEFT, padx=4)

        close_btn1 = tk.Button(queue_btn_frame, text="Close", command=self.hide, **btn_style)
        close_btn1.pack(side=tk.RIGHT)

        self.listbox.bind("<Double-Button-1>", lambda e: self.delete_selected())
        self.listbox.bind("<Delete>", lambda e: self.delete_selected())

        # 2. SETTINGS TAB FRAME
        self.settings_frame = tk.Frame(content_container, bg=CARD_BG, bd=0)
        self.settings_frame.config(highlightbackground=BUTTON_BORDER, highlightthickness=1)

        # Inner padded container
        inner = tk.Frame(self.settings_frame, bg=CARD_BG, padx=20, pady=16)
        inner.pack(fill=tk.BOTH, expand=True)

        # --- Section: Title ---
        sett_title = tk.Label(
            inner,
            text="Auto-Clear Settings",
            font=("Segoe UI", 11, "bold"),
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            anchor=tk.W,
        )
        sett_title.pack(fill=tk.X, pady=(0, 4))

        # Thin divider
        divider = tk.Frame(inner, bg=BUTTON_BORDER, height=1)
        divider.pack(fill=tk.X, pady=(0, 14))

        # --- Section: Description ---
        sett_desc = tk.Label(
            inner,
            text="Automatically remove items from the clipboard queue after a set duration.",
            font=("Segoe UI", 9),
            bg=CARD_BG,
            fg=TEXT_SECONDARY,
            wraplength=350,
            justify=tk.LEFT,
            anchor=tk.W,
        )
        sett_desc.pack(fill=tk.X, pady=(0, 16))

        # --- Section: Toggle row ---
        self.auto_clear_var = tk.BooleanVar(value=bool(self.config.get("auto_clear_enabled", False)))

        toggle_row = tk.Frame(inner, bg=CARD_BG)
        toggle_row.pack(fill=tk.X, pady=(0, 14))

        check_btn = tk.Checkbutton(
            toggle_row,
            text="Enable Auto-Clear",
            variable=self.auto_clear_var,
            command=self._on_settings_changed,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            selectcolor=DARK_BG,
            activebackground=CARD_BG,
            activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W,
            cursor="hand2",
        )
        check_btn.pack(side=tk.LEFT)

        # --- Section: Duration row (label + dropdown side by side) ---
        dur_row = tk.Frame(inner, bg=CARD_BG)
        dur_row.pack(fill=tk.X, pady=(0, 14))

        dur_label = tk.Label(
            dur_row,
            text="Remove items older than",
            font=("Segoe UI", 9),
            bg=CARD_BG,
            fg=TEXT_SECONDARY,
            anchor=tk.W,
        )
        dur_label.pack(side=tk.LEFT, padx=(0, 10))

        curr_seconds = self.config.get("auto_clear_seconds", 60)
        curr_label = next((label for label, secs in DURATION_OPTIONS if secs == curr_seconds), "1 Minute")
        self.duration_var = tk.StringVar(value=curr_label)

        dur_menu = tk.OptionMenu(
            dur_row,
            self.duration_var,
            *[label for label, _ in DURATION_OPTIONS],
            command=lambda val: self._on_settings_changed(),
        )
        dur_menu.config(
            bg=BUTTON_BG,
            fg=TEXT_PRIMARY,
            activebackground=ACCENT_PRIMARY,
            activeforeground="#FFFFFF",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 9),
            cursor="hand2",
            relief=tk.FLAT,
            padx=8,
        )
        dur_menu["menu"].config(
            bg=BUTTON_BG,
            fg=TEXT_PRIMARY,
            activebackground=ACCENT_PRIMARY,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9),
        )
        dur_menu.pack(side=tk.LEFT)

        # --- Section: Info note ---
        note_label = tk.Label(
            inner,
            text="Expired items are removed automatically. If the queue is empty, Ctrl+V reverts to standard paste.",
            font=("Segoe UI", 8),
            bg=CARD_BG,
            fg=EMPTY_TEXT_COLOR,
            wraplength=350,
            justify=tk.LEFT,
            anchor=tk.W,
        )
        note_label.pack(fill=tk.X, pady=(0, 0))

        # --- Footer: Close button pinned to bottom ---
        footer = tk.Frame(self.settings_frame, bg=CARD_BG, padx=20, pady=10)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Frame(footer, bg=BUTTON_BORDER, height=1).pack(fill=tk.X, pady=(0, 10))
        close_btn2 = tk.Button(footer, text="Close", command=self.hide, **btn_style)
        close_btn2.pack(side=tk.RIGHT)

        # Default Tab: Queue
        self._switch_to_queue_tab()
        self.refresh()

    def _switch_to_queue_tab(self) -> None:
        if self.settings_frame:
            self.settings_frame.pack_forget()
        if self.queue_frame:
            self.queue_frame.pack(fill=tk.BOTH, expand=True)
        if self.queue_tab_btn:
            self.queue_tab_btn.config(fg=ACCENT_PRIMARY)
        if self.settings_tab_btn:
            self.settings_tab_btn.config(fg=TEXT_SECONDARY)
        self.refresh()

    def _switch_to_settings_tab(self) -> None:
        if self.queue_frame:
            self.queue_frame.pack_forget()
        if self.settings_frame:
            self.settings_frame.pack(fill=tk.BOTH, expand=True)
        if self.queue_tab_btn:
            self.queue_tab_btn.config(fg=TEXT_SECONDARY)
        if self.settings_tab_btn:
            self.settings_tab_btn.config(fg=ACCENT_PRIMARY)

    def _on_settings_changed(self) -> None:
        """Saves setting updates to AppConfig."""
        if not self.config or not self.auto_clear_var or not self.duration_var:
            return

        enabled = self.auto_clear_var.get()
        selected_label = self.duration_var.get()
        seconds = next((secs for label, secs in DURATION_OPTIONS if label == selected_label), 60)

        self.config.set("auto_clear_enabled", enabled)
        self.config.set("auto_clear_seconds", seconds)

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
