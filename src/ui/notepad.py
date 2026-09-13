"""
Floating Quick Notepad HUD overlay for QPaste.
Frameless, draggable, dark-themed persistent scratchpad with auto-save.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]

from core.config import AppConfig

# Modern Dark Theme Color Palette
DARK_BG = "#12161F"          # Midnight background
CARD_BG = "#1A1F2C"          # Card container
EDITOR_BG = "#1E2433"        # Editor container
ACCENT_PRIMARY = "#0EA5E9"   # Sky cyan accent
TEXT_PRIMARY = "#F8FAFC"     # Primary text
TEXT_SECONDARY = "#94A3B8"   # Slate secondary text
BORDER_COLOR = "#2D323E"     # Border color
BTN_HOVER = "#EF4444"        # Close button hover red


class QuickNotepadHUD:
    """Floating draggable Quick Notepad HUD overlay with auto-persistence."""

    def __init__(self, config: Optional[AppConfig] = None, master: Optional[Any] = None) -> None:
        self.config: AppConfig = config or AppConfig()
        self.master: Optional[Any] = master
        self.window: Optional[Any] = None
        self.text_widget: Optional[Any] = None
        self.title_bar: Optional[Any] = None
        self._drag_offset_x: int = 0
        self._drag_offset_y: int = 0
        self._save_timer_id: Optional[str] = None
        self._is_visible: bool = False

    def show(self) -> None:
        """Thread-safely displays and focuses the Quick Notepad HUD."""
        if self.master and hasattr(self.master, "after"):
            self.master.after(0, self._show_main_thread)
        else:
            self._show_main_thread()

    def hide(self) -> None:
        """Thread-safely hides the Quick Notepad HUD and persists state."""
        if self.master and hasattr(self.master, "after"):
            self.master.after(0, self._hide_main_thread)
        else:
            self._hide_main_thread()

    def toggle(self) -> None:
        """Thread-safely toggles HUD visibility."""
        self.hide() if self.is_visible() else self.show()

    def is_visible(self) -> bool:
        """Checks if the notepad window is currently visible."""
        if self.window is None:
            return False
        try:
            val = self.window.winfo_viewable()
            if isinstance(val, (int, bool)):
                return bool(val)
            return self._is_visible
        except Exception:
            return self._is_visible

    def _show_main_thread(self) -> None:
        if self.window is None:
            self._build_gui()
        if self.window is not None:
            try:
                self.window.deiconify()
                self.window.lift()
                self.window.attributes("-topmost", True)
                if self.text_widget is not None:
                    self.text_widget.focus_set()
            except Exception:
                pass
            self._is_visible = True

    def _hide_main_thread(self) -> None:
        self.save_content()
        self.save_geometry()
        if self.window is not None:
            try:
                self.window.withdraw()
            except Exception:
                pass
        self._is_visible = False

    def _build_gui(self) -> None:
        if tk is None:
            return
        if self.master is None:
            self.master = tk.Tk()
            self.master.withdraw()

        self.window = tk.Toplevel(self.master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=DARK_BG)
        self.window.geometry(self.config.get("notepad_geometry", "380x280+200+200"))

        main_frame = tk.Frame(self.window, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER_COLOR)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.title_bar = tk.Frame(main_frame, bg=CARD_BG, height=30)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)

        accent = tk.Frame(self.title_bar, bg=ACCENT_PRIMARY, width=4, height=14)
        accent.pack(side=tk.LEFT, padx=(10, 6), pady=6)

        title_lbl = tk.Label(self.title_bar, text="Quick Notepad", font=("Segoe UI", 9, "bold"), fg=TEXT_PRIMARY, bg=CARD_BG)
        title_lbl.pack(side=tk.LEFT, pady=6)

        close_btn = tk.Button(
            self.title_bar, text="✕", command=self.hide, bg=CARD_BG, fg=TEXT_SECONDARY,
            activebackground=BTN_HOVER, activeforeground=TEXT_PRIMARY, bd=0, padx=8, pady=2,
            font=("Segoe UI", 9), cursor="hand2", relief=tk.FLAT,
        )
        close_btn.pack(side=tk.RIGHT, padx=4, pady=2)

        for widget in (self.title_bar, accent, title_lbl):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", lambda _e: self.save_geometry())

        editor_frame = tk.Frame(main_frame, bg=EDITOR_BG)
        editor_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        scrollbar = tk.Scrollbar(editor_frame, bg=CARD_BG, bd=0, highlightthickness=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widget = tk.Text(
            editor_frame, bg=EDITOR_BG, fg=TEXT_PRIMARY, insertbackground=ACCENT_PRIMARY,
            selectbackground="#0369A1", selectforeground=TEXT_PRIMARY, font=("Consolas", 10),
            wrap=tk.WORD, bd=0, highlightthickness=0, yscrollcommand=scrollbar.set, undo=True,
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        scrollbar.config(command=self.text_widget.yview)

        initial_text = self.config.get("notepad_text", "")
        if initial_text:
            self.text_widget.insert("1.0", initial_text)

        self.window.bind("<Escape>", lambda _e: self.hide())
        self.text_widget.bind("<Escape>", lambda _e: self.hide())
        self.text_widget.bind("<KeyRelease>", lambda _e: self._schedule_auto_save())
        self.text_widget.bind("<<Modified>>", self._on_text_modified)

    def _start_drag(self, event: Any) -> None:
        if self.window is not None:
            try:
                self._drag_offset_x = event.x_root - self.window.winfo_x()
                self._drag_offset_y = event.y_root - self.window.winfo_y()
            except Exception:
                self._drag_offset_x = getattr(event, "x", 0)
                self._drag_offset_y = getattr(event, "y", 0)

    def _on_drag(self, event: Any) -> None:
        if self.window is not None:
            try:
                new_x = event.x_root - self._drag_offset_x
                new_y = event.y_root - self._drag_offset_y
                self.window.geometry(f"+{new_x}+{new_y}")
            except Exception:
                pass

    def _on_text_modified(self, _event: Any) -> None:
        if self.text_widget is not None:
            try:
                if self.text_widget.edit_modified():
                    self.text_widget.edit_modified(False)
                    self._schedule_auto_save()
            except Exception:
                self._schedule_auto_save()

    def _schedule_auto_save(self) -> None:
        if self.window is not None and hasattr(self.window, "after"):
            if self._save_timer_id and hasattr(self.window, "after_cancel"):
                try:
                    self.window.after_cancel(self._save_timer_id)
                except Exception:
                    pass
            try:
                self._save_timer_id = self.window.after(300, self.save_content)
                return
            except Exception:
                pass
        self.save_content()

    def save_content(self) -> None:
        """Saves current editor content to configuration."""
        if self.text_widget is not None:
            try:
                content = self.text_widget.get("1.0", "end-1c")
                self.config.set("notepad_text", content)
            except Exception:
                pass

    def save_geometry(self) -> None:
        """Saves current window geometry to configuration."""
        if self.window is not None:
            try:
                geom = self.window.geometry()
                if geom:
                    self.config.set("notepad_geometry", geom)
            except Exception:
                pass
