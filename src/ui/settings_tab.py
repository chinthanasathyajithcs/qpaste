"""
Settings Tab component for QPaste Inspector.
Encapsulates Auto-Clear timer settings and press-to-record Hotkey customization with validation.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]

from core.config import AppConfig
from core.hotkey_parser import HotkeyCombo, format_hotkey, parse_hotkey
from core.hotkey_rules import validate_hotkey
from ui.hotkey_recorder import HotkeyRecorderField, widget_is_within

DARK_BG, CARD_BG, LIST_BG = "#12161F", "#1A1F2C", "#1E2433"
TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_PRIMARY = "#F8FAFC", "#94A3B8", "#0EA5E9"
BUTTON_BG, BUTTON_BORDER, ERROR_COLOR = "#2A3142", "#3D465C", "#EF4444"
WARNING_COLOR = "#F59E0B"
MESSAGE_WRAP_PX = 260
UNSUPPORTED_KEY_ERROR = "That key can't be used as a hotkey"

DURATION_OPTIONS: list[tuple[str, int]] = [
    ("30 Seconds", 30), ("1 Minute", 60), ("5 Minutes", 300),
    ("15 Minutes", 900), ("30 Minutes", 1800), ("1 Hour", 3600),
]
HOTKEY_ACTIONS: list[tuple[str, str, str]] = [
    ("toggle_queue", "Toggle Queue Mode", "F4"),
    ("clear_queue", "Clear Queue", "Shift+F4"),
    ("toggle_notepad", "Quick Notepad", "F3"),
]
HOTKEY_LABELS: Dict[str, str] = {action: label for action, label, _default in HOTKEY_ACTIONS}

_BaseFrame = tk.Frame if tk is not None else object


class SettingsTab(_BaseFrame):  # type: ignore[misc]
    """Settings frame with Auto-Clear controls and Hotkey customization."""

    def __init__(
        self,
        parent: Any,
        config: Optional[AppConfig] = None,
        on_hotkeys_changed: Optional[Callable[[], None]] = None,
        on_recording_changed: Optional[Callable[[bool], None]] = None,
        **kwargs: Any,
    ) -> None:
        if tk is not None and isinstance(getattr(tk, "Frame", None), type):
            try:
                super().__init__(parent, bg=CARD_BG, **kwargs)
            except Exception:
                pass
        self.config: AppConfig = config or AppConfig()
        self.on_hotkeys_changed: Optional[Callable[[], None]] = on_hotkeys_changed
        # Called with True when a row starts recording and False when it ends, so global
        # hotkeys can be paused while keys are being captured.
        self.on_recording_changed: Optional[Callable[[bool], None]] = on_recording_changed

        self.auto_clear_var: Optional[Any] = None
        self.duration_var: Optional[Any] = None
        self.hotkey_fields: Dict[str, HotkeyRecorderField] = {}
        self.record_buttons: Dict[str, Any] = {}
        self.reset_buttons: Dict[str, Any] = {}
        self.error_label: Optional[Any] = None
        self._recording_action: Optional[str] = None

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
            self._build_hotkey_row(inner, action, label_text, default_val)

        bottom_row = tk.Frame(inner, bg=CARD_BG)
        bottom_row.pack(fill=tk.X, pady=(8, 0))
        self.error_label = tk.Label(
            bottom_row, text="", font=("Segoe UI", 8), bg=CARD_BG, fg=ERROR_COLOR,
            anchor=tk.W, justify=tk.LEFT, wraplength=MESSAGE_WRAP_PX,
        )
        self.error_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(
            bottom_row, text="Reset Defaults", command=self.reset_defaults,
            bg=BUTTON_BG, fg=TEXT_PRIMARY, activebackground=ACCENT_PRIMARY,
            activeforeground="#FFFFFF", bd=0, padx=8, pady=3, font=("Segoe UI", 8, "bold"),
            cursor="hand2", relief=tk.FLAT,
        ).pack(side=tk.RIGHT)

        self._bind_window_click()

    def _build_hotkey_row(self, inner: Any, action: str, label_text: str, default_val: str) -> None:
        row = tk.Frame(inner, bg=CARD_BG)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label_text, font=("Segoe UI", 9), bg=CARD_BG, fg=TEXT_SECONDARY, width=16, anchor=tk.W).pack(side=tk.LEFT)

        field = HotkeyRecorderField(
            row,
            combo=self._configured_combo(action, default_val),
            fallback_text=default_val,
            on_start=lambda a=action: self._on_record_start(a),
            on_submit=lambda combo, a=action: self._on_combo_recorded(a, combo),
            on_stop=lambda committed, a=action: self._on_record_stop(a, committed),
        )
        self.hotkey_fields[action] = field

        # Right-side controls are packed first so a long combo can't squeeze them out.
        self.reset_buttons[action] = self._make_row_button(row, "\u21ba", lambda a=action: self._reset_row(a))
        self.record_buttons[action] = self._make_row_button(row, "Record", field.start_recording)
        field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

    def _make_row_button(self, row: Any, text: str, command: Callable[[], None]) -> Any:
        button = tk.Button(
            row, text=text, command=command, bg=BUTTON_BG, fg=TEXT_PRIMARY,
            activebackground=ACCENT_PRIMARY, activeforeground="#FFFFFF", bd=0, padx=6, pady=1,
            font=("Segoe UI", 8, "bold"), cursor="hand2", relief=tk.FLAT, takefocus=0,
        )
        button.pack(side=tk.RIGHT, padx=(4, 0))
        return button

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

    def _configured_combo(self, action: str, default_val: str) -> Optional[HotkeyCombo]:
        """The combo the listener will actually use: the stored one, else the default."""
        return parse_hotkey(self.config.get_hotkey(action, default=default_val)) or parse_hotkey(default_val)

    def _assignments(self) -> Dict[str, str]:
        return {action: self.config.get_hotkey(action, default=default) for action, _label, default in HOTKEY_ACTIONS}

    # --- recording ------------------------------------------------------------

    def _on_record_start(self, action: str) -> None:
        previous = self._recording_action
        self._recording_action = action
        self._clear_message()
        if previous is None:
            self._notify_recording(True)
        elif previous != action:
            # Hotkeys are already paused; the old row just stops (its stop callback sees it is stale).
            self.hotkey_fields[previous].cancel()

    def _on_record_stop(self, action: str, committed: bool) -> None:
        if self._recording_action != action:
            return
        self._recording_action = None
        if not committed:
            self._clear_message()
        self._notify_recording(False)

    def _notify_recording(self, recording: bool) -> None:
        if not self.on_recording_changed:
            return
        try:
            self.on_recording_changed(recording)
        except Exception:
            pass

    def cancel_recording(self) -> None:
        """Cancels any active recording (tab switch, window close) and resumes global hotkeys."""
        action = self._recording_action
        if action is not None and action in self.hotkey_fields:
            self.hotkey_fields[action].cancel()

    def _bind_window_click(self) -> None:
        # Tk frames and labels don't take focus on click, so FocusOut alone would miss
        # "clicking elsewhere"; a click anywhere in the window cancels instead.
        try:
            self.winfo_toplevel().bind("<Button-1>", self._on_window_click, add="+")
        except Exception:
            pass

    def _on_window_click(self, event: Any) -> None:
        if self._recording_action is None:
            return
        if any(widget_is_within(event.widget, owned) for owned in self._recorder_controls()):
            return
        self.cancel_recording()

    def _recorder_controls(self) -> list[Any]:
        fields = [field.frame for field in self.hotkey_fields.values()]
        return [*fields, *self.record_buttons.values(), *self.reset_buttons.values()]

    def _on_combo_recorded(self, action: str, combo: Optional[HotkeyCombo]) -> bool:
        """Recorder callback: True ends recording, False keeps it open for another try."""
        if combo is None:
            self._show_message(UNSUPPORTED_KEY_ERROR, ERROR_COLOR)
            return False
        return self._apply_combo(action, combo)

    def _apply_combo(self, action: str, combo: HotkeyCombo) -> bool:
        """Validates and, only for a complete valid combo, saves it and reloads hotkeys."""
        result = validate_hotkey(combo, action, self._assignments(), HOTKEY_LABELS)
        if not result.ok:
            self._show_message(result.error or "", ERROR_COLOR)
            return False

        self.config.set_hotkey(action, format_hotkey(combo))
        if action in self.hotkey_fields:
            self.hotkey_fields[action].set_combo(combo)
        if result.warning:
            self._show_message(result.warning, WARNING_COLOR)
        else:
            self._clear_message()
        if self.on_hotkeys_changed:
            self.on_hotkeys_changed()
        return True

    def _reset_row(self, action: str) -> None:
        """Restores one action's default hotkey, subject to the same validation as recording."""
        self.cancel_recording()
        default = next((d for a, _label, d in HOTKEY_ACTIONS if a == action), None)
        combo = parse_hotkey(default) if default else None
        if combo is not None:
            self._apply_combo(action, combo)

    def _show_message(self, text: str, color: str) -> None:
        if self.error_label:
            self.error_label.config(text=text, fg=color)

    def _clear_message(self) -> None:
        self._show_message("", ERROR_COLOR)

    def reset_defaults(self) -> None:
        """Resets hotkeys to default values and invokes callback."""
        self.cancel_recording()
        self.config.reset_hotkeys()
        for action, _label, default_val in HOTKEY_ACTIONS:
            if action in self.hotkey_fields:
                self.hotkey_fields[action].set_combo(parse_hotkey(default_val))

        if self.auto_clear_var:
            self.auto_clear_var.set(False)
            self.config.set("auto_clear_enabled", False)
        if self.duration_var:
            self.duration_var.set("1 Minute")
            self.config.set("auto_clear_seconds", 60)
        self.config.set("auto_clear_mode", "idle")

        self._clear_message()
        if self.on_hotkeys_changed:
            self.on_hotkeys_changed()
