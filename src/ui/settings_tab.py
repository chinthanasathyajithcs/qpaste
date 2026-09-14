"""
Settings Tab component for QPaste Inspector.
Encapsulates Auto-Clear timer settings and Hotkey customization with validation.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]

from core.config import AppConfig
from core.hotkey_parser import parse_hotkey

DARK_BG, CARD_BG, LIST_BG = "#12161F", "#1A1F2C", "#1E2433"
TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_PRIMARY = "#F8FAFC", "#94A3B8", "#0EA5E9"
BUTTON_BG, BUTTON_BORDER, ERROR_COLOR = "#2A3142", "#3D465C", "#EF4444"

DURATION_OPTIONS: list[tuple[str, int]] = [
    ("30 Seconds", 30), ("1 Minute", 60), ("5 Minutes", 300),
    ("15 Minutes", 900), ("30 Minutes", 1800), ("1 Hour", 3600),
]
HOTKEY_ACTIONS: list[tuple[str, str, str]] = [
    ("toggle_queue", "Toggle Queue Mode", "F4"),
    ("clear_queue", "Clear Queue", "Shift+F4"),
    ("toggle_notepad", "Quick Notepad", "F3"),
]

_BaseFrame = tk.Frame if tk is not None else object


class SettingsTab(_BaseFrame):  # type: ignore[misc]
    """Settings frame with Auto-Clear controls and Hotkey customization."""

    def __init__(
        self,
        parent: Any,
        config: Optional[AppConfig] = None,
        on_hotkeys_changed: Optional[Callable[[], None]] = None,
        **kwargs: Any,
    ) -> None:
        if tk is not None and isinstance(getattr(tk, "Frame", None), type):
            try:
                super().__init__(parent, bg=CARD_BG, **kwargs)
            except Exception:
                pass
        self.config: AppConfig = config or AppConfig()
        self.on_hotkeys_changed: Optional[Callable[[], None]] = on_hotkeys_changed

        self.auto_clear_var: Optional[Any] = None
        self.duration_var: Optional[Any] = None
        self.hotkey_vars: Dict[str, Any] = {}
        self.hotkey_entries: Dict[str, Any] = {}
        self.error_label: Optional[Any] = None

        if tk is not None:
            self._build_ui()

    def pack(self, *args: Any, **kwargs: Any) -> None:
        if hasattr(self, "tk"):
            super().pack(*args, **kwargs)

    def pack_forget(self, *args: Any, **kwargs: Any) -> None:
        if hasattr(self, "tk"):
            super().pack_forget(*args, **kwargs)

    def _build_ui(self) -> None:
        if tk is None:
            return
        inner = tk.Frame(self, bg=CARD_BG, padx=14, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)

        tk.Label(inner, text="Auto-Clear Timer", font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, anchor=tk.W).pack(fill=tk.X)
        tk.Frame(inner, bg=BUTTON_BORDER, height=1).pack(fill=tk.X, pady=(2, 8))

        row_clear = tk.Frame(inner, bg=CARD_BG)
        row_clear.pack(fill=tk.X, pady=(0, 6))

        self.auto_clear_var = tk.BooleanVar(value=bool(self.config.get("auto_clear_enabled", False)))
        tk.Checkbutton(
            row_clear, text="Auto-clear queue after:", variable=self.auto_clear_var,
            command=self._on_auto_clear_changed, bg=CARD_BG, fg=TEXT_PRIMARY,
            selectcolor=DARK_BG, activebackground=CARD_BG, activeforeground=TEXT_PRIMARY,
            font=("Segoe UI", 9), cursor="hand2", bd=0,
        ).pack(side=tk.LEFT, padx=(0, 8))

        curr_secs = self.config.get("auto_clear_seconds", 60)
        dur_label = next((l for l, s in DURATION_OPTIONS if s == curr_secs), "1 Minute")
        self.duration_var = tk.StringVar(value=dur_label)
        self._create_menu(row_clear, self.duration_var, [l for l, _ in DURATION_OPTIONS]).pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(row_clear, text="of inactivity", font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_SECONDARY).pack(side=tk.LEFT)

        tk.Label(inner, text="Hotkey Configuration", font=("Segoe UI", 10, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY, anchor=tk.W).pack(fill=tk.X, pady=(10, 0))
        tk.Frame(inner, bg=BUTTON_BORDER, height=1).pack(fill=tk.X, pady=(2, 8))

        for action, label_text, default_val in HOTKEY_ACTIONS:
            row = tk.Frame(inner, bg=CARD_BG)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label_text, font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_SECONDARY, width=16, anchor=tk.W).pack(side=tk.LEFT)

            current_key = self.config.get_hotkey(action, default=default_val)
            str_var = tk.StringVar(value=current_key)
            self.hotkey_vars[action] = str_var

            entry = tk.Entry(
                row, textvariable=str_var, bg=LIST_BG, fg=TEXT_PRIMARY,
                insertbackground=ACCENT_PRIMARY, font=("Consolas", 9, "bold"),
                relief=tk.FLAT, bd=0, highlightthickness=1, highlightbackground=BUTTON_BORDER,
            )
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3, padx=(4, 0))
            entry.bind("<KeyRelease>", lambda _e, a=action: self._on_hotkey_edited(a))
            entry.bind("<FocusOut>", lambda _e, a=action: self._on_hotkey_edited(a))
            self.hotkey_entries[action] = entry

        bottom_row = tk.Frame(inner, bg=CARD_BG)
        bottom_row.pack(fill=tk.X, pady=(8, 0))
        self.error_label = tk.Label(bottom_row, text="", font=("Segoe UI", 8), bg=CARD_BG, fg=ERROR_COLOR, anchor=tk.W)
        self.error_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            bottom_row, text="Reset Defaults", command=self.reset_defaults,
            bg=BUTTON_BG, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY,
            activeforeground="#FFFFFF", bd=0, padx=8, pady=3, font=("Segoe UI", 8, "bold"),
            cursor="hand2", relief=tk.FLAT,
        ).pack(side=tk.RIGHT)

    def _create_menu(self, parent: Any, var: Any, options: list[str]) -> Any:
        menu = tk.OptionMenu(parent, var, *options, command=lambda _val: self._on_auto_clear_changed())
        menu.config(bg=BUTTON_BG, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY, activeforeground="#FFFFFF", bd=0, highlightthickness=0, font=("Segoe UI", 8), relief=tk.FLAT, padx=6, pady=2)
        menu["menu"].config(bg=BUTTON_BG, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY, activeforeground="#FFFFFF", font=("Segoe UI", 8))
        return menu

    def _on_auto_clear_changed(self) -> None:
        if not self.config or not self.auto_clear_var or not self.duration_var:
            return
        secs = next((s for l, s in DURATION_OPTIONS if l == self.duration_var.get()), 60)
        self.config.set("auto_clear_enabled", bool(self.auto_clear_var.get()))
        self.config.set("auto_clear_seconds", secs)
        self.config.set("auto_clear_mode", "idle")

    def _on_hotkey_edited(self, action: str) -> bool:
        if action not in self.hotkey_vars:
            return False
        val = self.hotkey_vars[action].get().strip()
        combo = parse_hotkey(val)
        entry = self.hotkey_entries.get(action)

        if combo is None:
            if self.error_label:
                self.error_label.config(text=f"Invalid combo for {action.replace('_', ' ')}: '{val}'")
            if entry and hasattr(entry, "config"):
                entry.config(highlightbackground=ERROR_COLOR)
            return False

        if self.error_label:
            self.error_label.config(text="")
        if entry and hasattr(entry, "config"):
            entry.config(highlightbackground=BUTTON_BORDER)

        self.config.set_hotkey(action, val)
        if self.on_hotkeys_changed:
            self.on_hotkeys_changed()
        return True

    def reset_defaults(self) -> None:
        """Resets hotkeys to default values and invokes callback."""
        self.config.reset_hotkeys()
        for action, _label, default_val in HOTKEY_ACTIONS:
            if action in self.hotkey_vars:
                self.hotkey_vars[action].set(default_val)
            if self.hotkey_entries.get(action) and hasattr(self.hotkey_entries[action], "config"):
                self.hotkey_entries[action].config(highlightbackground=BUTTON_BORDER)

        if self.auto_clear_var:
            self.auto_clear_var.set(False)
            self.config.set("auto_clear_enabled", False)
        if self.duration_var:
            self.duration_var.set("1 Minute")
            self.config.set("auto_clear_seconds", 60)
        self.config.set("auto_clear_mode", "idle")

        if self.error_label:
            self.error_label.config(text="")
        if self.on_hotkeys_changed:
            self.on_hotkeys_changed()
