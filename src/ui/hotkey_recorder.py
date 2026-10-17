"""
Press-to-record hotkey field for the QPaste Settings tab.
Shows a combo as dark key-caps and, while recording, captures it from Tk key events.
Tk reports the Windows virtual-key code as event.keycode, which lines up with the
virtual-key-first matcher in core.hotkey_parser.
"""
from __future__ import annotations

from typing import Any, Callable, List, Optional

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]

from core.hotkey_parser import (
    MODIFIER_DISPLAY,
    MODIFIER_ORDER,
    HotkeyCombo,
    hotkey_parts,
    key_name_from_vk,
    modifier_from_vk,
)

LIST_BG = "#1E2433"
TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_PRIMARY = "#F8FAFC", "#94A3B8", "#0EA5E9"
BUTTON_BG, BUTTON_BORDER = "#2A3142", "#3D465C"
ACCENT_TINT_BG = "#0C4A6E"  # live modifier caps while recording

CAP_FONT = ("Segoe UI", 8, "bold")
CAP_PAD_X, CAP_PAD_Y, CAP_GAP = 6, 1, 2
FIELD_PAD = 3
BORDER_WIDTH = 1
PROMPT_TEXT = "Press keys…"

EVENT_BREAK = "break"
ESCAPE_KEY = "escape"


def widget_is_within(widget: Any, container: Any) -> bool:
    """True when `widget` is `container` or one of its descendants (compared by Tk path)."""
    if widget is None or container is None:
        return False
    path, container_path = str(widget), str(container)
    return path == container_path or path.startswith(container_path + ".")


class HotkeyRecorderField:
    """
    One key-cap display that records a combo when started.

    Callbacks (all optional):
      on_start()                 recording began
      on_submit(combo) -> bool   a combo (None for an unsupported key) was completed;
                                 return True to accept it, False to keep recording
      on_stop(committed)         recording ended, by an accepted combo or by cancelling
    """

    def __init__(
        self,
        parent: Any,
        combo: Optional[HotkeyCombo],
        fallback_text: str = "",
        on_start: Optional[Callable[[], None]] = None,
        on_submit: Optional[Callable[[Optional[HotkeyCombo]], bool]] = None,
        on_stop: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self._combo = combo
        self._fallback_text = fallback_text
        self._on_start = on_start
        self._on_submit = on_submit
        self._on_stop = on_stop
        self._recording = False
        self._held: frozenset[str] = frozenset()

        self.frame: Any = None
        self._cap_widgets: List[Any] = []
        self.displayed_tokens: List[str] = []

        if tk is not None:
            self._build(parent)

    # --- public state ---------------------------------------------------------

    @property
    def combo(self) -> Optional[HotkeyCombo]:
        return self._combo

    @property
    def recording(self) -> bool:
        return self._recording

    def pack(self, *args: Any, **kwargs: Any) -> None:
        if self.frame is not None:
            self.frame.pack(*args, **kwargs)

    def set_combo(self, combo: Optional[HotkeyCombo]) -> None:
        """Replaces the stored combo and redraws the caps."""
        self._combo = combo
        self._render()

    # --- recording lifecycle --------------------------------------------------

    def start_recording(self) -> None:
        """Begins capturing keys; a no-op if already recording."""
        if self._recording:
            return
        self._recording = True
        self._held = frozenset()
        try:
            if self._on_start:
                self._on_start()
        except Exception:
            self._recording = False
            raise
        self._apply_border()
        self._render()
        self._focus()

    def cancel(self) -> None:
        """Stops recording without changing the stored combo."""
        if self._recording:
            self._end(committed=False)

    def _end(self, committed: bool) -> None:
        self._recording = False
        self._held = frozenset()
        try:
            self._apply_border()
            self._render()
        finally:
            if self._on_stop:
                self._on_stop(committed)

    # --- Tk event handlers ----------------------------------------------------

    def on_key_press(self, event: Any) -> Optional[str]:
        """Handles a KeyPress while recording; returning 'break' keeps Alt/F10 from reaching Tk menus."""
        if not self._recording:
            return None
        try:
            self._handle_key_down(event.keycode)
        except Exception:
            self.cancel()
            raise
        return EVENT_BREAK

    def on_key_release(self, event: Any) -> Optional[str]:
        if not self._recording:
            return None
        modifier = modifier_from_vk(event.keycode)
        if modifier:
            self._set_held(self._held - {modifier})
        return EVENT_BREAK

    def on_focus_out(self, _event: Any = None) -> None:
        self.cancel()

    def _on_click(self, _event: Any = None) -> None:
        self.start_recording()

    def _on_destroy(self, event: Any = None) -> None:
        if event is None or event.widget is self.frame:
            self.cancel()

    def _handle_key_down(self, keycode: int) -> None:
        modifier = modifier_from_vk(keycode)
        if modifier:
            self._set_held(self._held | {modifier})
            return

        key = key_name_from_vk(keycode)
        if key == ESCAPE_KEY and not self._held:
            self._end(committed=False)
            return

        combo = HotkeyCombo(self._held, key) if key else None
        if self._on_submit is None or self._on_submit(combo):
            self._combo = combo
            self._end(committed=True)

    def _set_held(self, held: frozenset[str]) -> None:
        if held == self._held:
            return
        self._held = held
        self._render()

    # --- rendering ------------------------------------------------------------

    def _build(self, parent: Any) -> None:
        self.frame = tk.Frame(
            parent, bg=LIST_BG, cursor="hand2", takefocus=0,
            highlightthickness=BORDER_WIDTH, highlightbackground=BUTTON_BORDER, highlightcolor=BUTTON_BORDER,
        )
        self.frame.bind("<KeyPress>", self.on_key_press)
        self.frame.bind("<KeyRelease>", self.on_key_release)
        self.frame.bind("<FocusOut>", self.on_focus_out)
        self.frame.bind("<Button-1>", self._on_click)
        self.frame.bind("<Destroy>", self._on_destroy)
        self._render()

    def _focus(self) -> None:
        try:
            self.frame.focus_set()
        except Exception:
            pass

    def _apply_border(self) -> None:
        color = ACCENT_PRIMARY if self._recording else BUTTON_BORDER
        try:
            self.frame.config(highlightbackground=color, highlightcolor=color)
        except Exception:
            pass

    def _tokens(self) -> List[str]:
        """Caps to show now: held modifiers while recording, otherwise the stored combo."""
        if self._recording:
            return [MODIFIER_DISPLAY[m] for m in MODIFIER_ORDER if m in self._held]
        if self._combo is not None:
            return hotkey_parts(self._combo)
        return [self._fallback_text] if self._fallback_text else []

    def _render(self) -> None:
        if self.frame is None:
            return
        self._clear_caps()
        self.displayed_tokens = self._tokens()
        try:
            if self._recording and not self.displayed_tokens:
                self._add_label(PROMPT_TEXT, bg=LIST_BG, fg=TEXT_SECONDARY, border=LIST_BG, bold=False)
            for token in self.displayed_tokens:
                self._add_cap(token)
        except Exception:
            pass

    def _clear_caps(self) -> None:
        for cap in self._cap_widgets:
            try:
                cap.destroy()
            except Exception:
                pass
        self._cap_widgets = []

    def _add_cap(self, text: str) -> None:
        if self._recording:
            self._add_label(text, bg=ACCENT_TINT_BG, fg=TEXT_PRIMARY, border=ACCENT_PRIMARY)
        else:
            self._add_label(text, bg=BUTTON_BG, fg=TEXT_PRIMARY, border=BUTTON_BORDER)

    def _add_label(self, text: str, bg: str, fg: str, border: str, bold: bool = True) -> None:
        font = CAP_FONT if bold else CAP_FONT[:2]
        label = tk.Label(
            self.frame, text=text, font=font, bg=bg, fg=fg, bd=0,
            padx=CAP_PAD_X, pady=CAP_PAD_Y, highlightthickness=BORDER_WIDTH,
            highlightbackground=border, cursor="hand2",
        )
        label.pack(side=tk.LEFT, padx=(FIELD_PAD, CAP_GAP), pady=FIELD_PAD)
        label.bind("<Button-1>", self._on_click)
        self._cap_widgets.append(label)
