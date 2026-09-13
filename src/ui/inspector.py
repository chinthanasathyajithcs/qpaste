"""
Visual Queue Inspector GUI HUD Window using Tkinter with a modern dark theme.
Features live queue management and embedded SettingsTab.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Optional

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig
from ui.settings_tab import SettingsTab

DARK_BG, CARD_BG, LIST_BG = "#12161F", "#1A1F2C", "#1E2433"
TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_PRIMARY = "#F8FAFC", "#94A3B8", "#0EA5E9"
BUTTON_BG, BUTTON_BORDER, SELECT_BG, EMPTY_TEXT_COLOR = "#2A3142", "#3D465C", "#0369A1", "#64748B"


class QueueInspectorWindow:
    """Tkinter-based Visual Queue Inspector Window with Settings tab."""

    def __init__(
        self,
        queue: ClipboardQueue,
        config: Optional[AppConfig] = None,
        master: Optional[Any] = None,
        on_hotkeys_changed: Optional[Callable[[], None]] = None,
    ) -> None:
        self.queue = queue
        self.config: AppConfig = config or AppConfig()
        self.master: Optional[Any] = master
        self.on_hotkeys_changed: Optional[Callable[[], None]] = on_hotkeys_changed

        self.root: Optional[Any] = None
        self.listbox: Optional[Any] = None
        self.count_label: Optional[Any] = None
        self.empty_label: Optional[Any] = None
        self.content_container: Optional[Any] = None
        self.queue_frame: Optional[Any] = None
        self.settings_tab: Optional[SettingsTab] = None
        self.queue_tab_btn: Optional[Any] = None
        self.settings_tab_btn: Optional[Any] = None

    def show(self) -> None:
        """Shows or focuses the Queue Inspector window (thread-safe)."""
        if self.master and hasattr(self.master, "after"):
            self.master.after(0, self._show_on_main_thread)
        else:
            self._show_on_main_thread()

    def _show_on_main_thread(self) -> None:
        if self.root is None:
            self._build_gui()
        elif hasattr(self.root, "deiconify"):
            try:
                self.root.deiconify()
                self.root.lift()
                self.root.focus_force()
                self.refresh()
            except Exception:
                pass

    def _build_gui(self) -> None:
        if tk is None:
            return
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

        def _get_asset_path(filename: str) -> str:
            if hasattr(sys, "_MEIPASS"):
                return os.path.join(sys._MEIPASS, "assets", filename)
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            return os.path.join(base_dir, "..", "assets", filename)

        try:
            from main import apply_window_icons
            apply_window_icons(self.root, _get_asset_path("icon.png"), _get_asset_path("icon.ico"))
        except Exception:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Header bar with tab buttons
        header = tk.Frame(self.root, bg=DARK_BG, pady=6, padx=12)
        header.pack(fill=tk.X)
        tabs_frame = tk.Frame(header, bg=DARK_BG)
        tabs_frame.pack(side=tk.LEFT)

        tab_kw = {
            "bg": DARK_BG, "fg": TEXT_SECONDARY, "activebackground": CARD_BG,
            "activeforeground": TEXT_PRIMARY, "bd": 0, "padx": 10, "pady": 5,
            "font": ("Segoe UI", 9, "bold"), "cursor": "hand2", "relief": tk.FLAT,
        }
        self.queue_tab_btn = tk.Button(tabs_frame, text="☰  Queue", command=self._switch_to_queue_tab, **tab_kw)
        self.queue_tab_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.settings_tab_btn = tk.Button(tabs_frame, text="⚙  Settings", command=self._switch_to_settings_tab, **tab_kw)
        self.settings_tab_btn.pack(side=tk.LEFT)

        self.count_label = tk.Label(header, text="0 / 25", font=("Segoe UI", 9, "bold"), bg=DARK_BG, fg=ACCENT_PRIMARY)
        self.count_label.pack(side=tk.RIGHT)

        # Content container
        self.content_container = tk.Frame(self.root, bg=DARK_BG)
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # 1. Queue Tab
        self.queue_frame = tk.Frame(self.content_container, bg=DARK_BG)
        list_box_frame = tk.Frame(self.queue_frame, bg=CARD_BG, bd=1, relief=tk.SOLID, highlightbackground=BUTTON_BORDER, highlightthickness=1)
        list_box_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_box_frame, bg=CARD_BG)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_box_frame, bg=LIST_BG, fg=TEXT_PRIMARY, selectbackground=SELECT_BG,
            selectforeground="#FFFFFF", font=("Consolas", 10), bd=0, highlightthickness=0,
            selectmode=tk.SINGLE, yscrollcommand=scrollbar.set, activestyle="none",
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.empty_label = tk.Label(list_box_frame, text="No items in queue", font=("Segoe UI", 10), bg=LIST_BG, fg=EMPTY_TEXT_COLOR, justify=tk.CENTER)

        action_bar = tk.Frame(self.queue_frame, bg=DARK_BG, pady=8)
        action_bar.pack(fill=tk.X)
        btn_kw = {
            "bg": BUTTON_BG, "fg": TEXT_PRIMARY, "activebackground": ACCENT_PRIMARY,
            "activeforeground": "#FFFFFF", "bd": 0, "padx": 8, "pady": 4,
            "font": ("Segoe UI", 9, "bold"), "cursor": "hand2", "relief": tk.FLAT,
        }
        tk.Button(action_bar, text="Delete", command=self.delete_selected, **btn_kw).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(action_bar, text="Clear All", command=self.clear_all, **btn_kw).pack(side=tk.LEFT, padx=4)
        tk.Button(action_bar, text="Close", command=self.hide, **btn_kw).pack(side=tk.RIGHT)

        self.listbox.bind("<Double-Button-1>", lambda _e: self.delete_selected())
        self.listbox.bind("<Delete>", lambda _e: self.delete_selected())

        # 2. Settings Tab
        self.settings_tab = SettingsTab(
            self.content_container,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )

        self._switch_to_queue_tab()
        self.refresh()

    def _switch_to_queue_tab(self) -> None:
        if self.settings_tab and hasattr(self.settings_tab, "pack_forget"):
            self.settings_tab.pack_forget()
        if self.queue_frame and hasattr(self.queue_frame, "pack"):
            self.queue_frame.pack(fill=tk.BOTH, expand=True)
        if self.queue_tab_btn and hasattr(self.queue_tab_btn, "config"):
            self.queue_tab_btn.config(fg=ACCENT_PRIMARY)
        if self.settings_tab_btn and hasattr(self.settings_tab_btn, "config"):
            self.settings_tab_btn.config(fg=TEXT_SECONDARY)
        self.refresh()

    def _switch_to_settings_tab(self) -> None:
        if self.queue_frame and hasattr(self.queue_frame, "pack_forget"):
            self.queue_frame.pack_forget()
        if self.settings_tab and hasattr(self.settings_tab, "pack"):
            self.settings_tab.pack(fill=tk.BOTH, expand=True)
        if self.queue_tab_btn and hasattr(self.queue_tab_btn, "config"):
            self.queue_tab_btn.config(fg=TEXT_SECONDARY)
        if self.settings_tab_btn and hasattr(self.settings_tab_btn, "config"):
            self.settings_tab_btn.config(fg=ACCENT_PRIMARY)

    def _on_hotkeys_changed(self) -> None:
        if self.on_hotkeys_changed:
            self.on_hotkeys_changed()

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

            if self.empty_label:
                self.empty_label.place_forget()

            for i, text in enumerate(items, 1):
                preview = text.replace("\n", " ↵ ").replace("\r", "")
                if len(preview) > 50:
                    preview = preview[:47] + "..."
                self.listbox.insert(tk.END, f" [{i:02d}]  {preview}")

            if selected_idx and selected_idx[0] < len(items):
                self.listbox.selection_set(selected_idx[0])
        except Exception:
            pass

    def delete_selected(self) -> None:
        """Deletes the selected item from queue."""
        if not self.listbox:
            return
        try:
            sel = self.listbox.curselection()
            if sel:
                self.queue.remove_at(sel[0])
                self.refresh()
        except Exception:
            pass

    def clear_all(self) -> None:
        """Clears all items from the queue."""
        self.queue.clear()
        self.refresh()

    def hide(self) -> None:
        """Hides the window without destroying process."""
        if self.root and hasattr(self.root, "withdraw"):
            try:
                self.root.withdraw()
            except Exception:
                pass
