"""
Native Windows ToolWindow Toast Overlay for QPaste.
Uses Tkinter Toplevel + ctypes Win32 API (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
to guarantee zero taskbar presence and zero focus stealing.
"""
try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]
import ctypes
import time
from typing import Callable, Optional, Tuple

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

TOAST_BG = "#181B24"
TOAST_BORDER = "#2D323E"
TOAST_TEXT_FG = "#94A3B8"
TEXT_TOAST_SIZE = (220, 48)
TEXT_TOAST_TIMEOUT_MS = 2000

# Count toast: a small box where only the number moves (odometer-style roll).
COUNT_TOAST_SIZE = (70, 50)
COUNT_TOAST_TIMEOUT_MS = 800
COUNT_FONT = ("Segoe UI", 16, "bold")
COUNT_ANIM_DURATION_MS = 170
COUNT_ANIM_FRAME_MS = 16
# Inner drawing area: the box minus the frame's 1px pad and 1px highlight border on each side.
COUNT_CANVAS_WIDTH = COUNT_TOAST_SIZE[0] - 4
COUNT_CANVAS_HEIGHT = COUNT_TOAST_SIZE[1] - 4

ROLL_UP = -1    # copy: old number exits upward, new one enters from below
ROLL_DOWN = 1   # paste: old number exits downward, new one enters from above

ROLLING_TOAST_DIRECTIONS = {"copy_count": ROLL_UP, "paste_count": ROLL_DOWN}
# Rolling types plus a static variant (a copy at queue capacity changes no number).
COUNT_TOAST_TYPES = frozenset(ROLLING_TOAST_DIRECTIONS) | {"count_static"}


def ease_out_cubic(progress: float) -> float:
    """Ease-out curve over [0, 1]; clamps so the endpoints are exact."""
    clamped = min(max(progress, 0.0), 1.0)
    return 1.0 - (1.0 - clamped) ** 3


def roll_offsets(progress: float, direction: int, height: float) -> Tuple[float, float]:
    """Vertical offsets (old, new) from the centre line for a roll of the given direction."""
    eased = ease_out_cubic(progress)
    return direction * eased * height, direction * (eased - 1.0) * height


def resolve_count_roll(text: str, toast_type: str) -> Optional[Tuple[str, str, int]]:
    """Returns (old_text, new_text, direction) for a rolling count toast, or None if it should be static.

    The previous number is derived from the direction instead of tracked, so a clear,
    auto-clear or inspector delete between toasts can never leave it stale.
    """
    direction = ROLLING_TOAST_DIRECTIONS.get(toast_type)
    if direction is None:
        return None
    try:
        new_count = int(text)
    except ValueError:
        return None
    old_count = new_count - 1 if direction == ROLL_UP else new_count + 1
    return str(old_count), text, direction


class NativeToastOverlay:
    """Manages a native, non-focus-stealing Windows toolwindow toast overlay."""

    def __init__(
        self,
        master: Optional[tk.Tk] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.master = master
        self.window: Optional[tk.Toplevel] = None
        self.frame: Optional[tk.Frame] = None
        self.label: Optional[tk.Label] = None
        self.canvas: Optional[tk.Canvas] = None
        self._old_digit_item: Optional[int] = None
        self._new_digit_item: Optional[int] = None
        self._hide_timer_id: Optional[str] = None
        self._anim_timer_id: Optional[str] = None
        self._anim_start: float = 0.0
        self._anim_direction: int = ROLL_UP
        self._clock = clock

    def start(self) -> None:
        """Initializes the Toast window under the main Tk root."""
        if self.master is None:
            self.master = tk.Tk()
            self.master.withdraw()

        self.window = tk.Toplevel(self.master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.94)
        self.window.configure(bg="#121824")
        self.window.withdraw()

        # Apply Win32 Extended Window Styles (ToolWindow + NoActivate + TopMost)
        self.window.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(self.window.winfo_id())  # type: ignore[attr-defined]
            if not hwnd:
                hwnd = self.window.winfo_id()
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)  # type: ignore[attr-defined]
            ex_style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)  # type: ignore[attr-defined]
        except Exception:
            pass

        # Outer Frame with Subtle Dark Border
        self.frame = tk.Frame(self.window, bg="#181B24", highlightthickness=1, highlightbackground="#2D323E")
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

        # Canvas for count toasts: it clips whatever rolls outside its bounds. Swapped in for the label.
        self.canvas = tk.Canvas(
            self.frame,
            width=COUNT_CANVAS_WIDTH,
            height=COUNT_CANVAS_HEIGHT,
            bg=TOAST_BG,
            highlightthickness=0,
            bd=0,
        )
        centre = (COUNT_CANVAS_WIDTH / 2, COUNT_CANVAS_HEIGHT / 2)
        self._old_digit_item = self.canvas.create_text(*centre, text="", font=COUNT_FONT, fill=TOAST_TEXT_FG)
        self._new_digit_item = self.canvas.create_text(*centre, text="", font=COUNT_FONT, fill=TOAST_TEXT_FG)

    def _cancel_timers(self) -> None:
        """Cancels the running animation frame and the hide timer, if any."""
        if not self.window:
            return
        for timer_id in (self._hide_timer_id, self._anim_timer_id):
            if timer_id:
                self.window.after_cancel(timer_id)
        self._hide_timer_id = None
        self._anim_timer_id = None

    def _show_label(self, text: str, fg_color: str, bg_color: str, font_style: tuple) -> None:
        self.canvas.pack_forget()
        self.label.configure(text=text, fg=fg_color, bg=bg_color, font=font_style)
        self.label.pack(expand=True)

    def _show_canvas(self) -> None:
        self.label.pack_forget()
        self.canvas.configure(bg=TOAST_BG)
        self.canvas.pack(fill="both", expand=True)

    def _draw_roll(self, progress: float) -> None:
        old_offset, new_offset = roll_offsets(progress, self._anim_direction, COUNT_CANVAS_HEIGHT)
        x, centre_y = COUNT_CANVAS_WIDTH / 2, COUNT_CANVAS_HEIGHT / 2
        self.canvas.coords(self._old_digit_item, x, centre_y + old_offset)
        self.canvas.coords(self._new_digit_item, x, centre_y + new_offset)

    def _start_count(self, text: str, toast_type: str) -> None:
        """Shows a count toast: rolls old to new when known, otherwise shows the number statically."""
        self._show_canvas()
        roll = resolve_count_roll(text, toast_type)
        if roll is None:
            self.canvas.itemconfigure(self._new_digit_item, text=text)
            self.canvas.itemconfigure(self._old_digit_item, text="")
            self._anim_direction = ROLL_UP
            self._draw_roll(1.0)
            self._schedule_hide(COUNT_TOAST_TIMEOUT_MS)
            return

        old_text, new_text, self._anim_direction = roll
        self.canvas.itemconfigure(self._old_digit_item, text=old_text)
        self.canvas.itemconfigure(self._new_digit_item, text=new_text)
        self._anim_start = self._clock()
        self._draw_roll(0.0)
        self._anim_timer_id = self.window.after(COUNT_ANIM_FRAME_MS, self._animation_step)

    def _animation_step(self) -> None:
        """Advances the roll by wall-clock time, then starts the hide timer once it lands."""
        self._anim_timer_id = None
        progress = (self._clock() - self._anim_start) * 1000.0 / COUNT_ANIM_DURATION_MS
        self._draw_roll(progress)
        if progress >= 1.0:
            self._schedule_hide(COUNT_TOAST_TIMEOUT_MS)
        else:
            self._anim_timer_id = self.window.after(COUNT_ANIM_FRAME_MS, self._animation_step)

    def _schedule_hide(self, timeout: int) -> None:
        self._hide_timer_id = self.window.after(timeout, self.window.withdraw)

    def show_toast(self, text: str, toast_type: str = "info") -> None:
        """Thread-safely displays the toast overlay at the bottom-right corner."""
        if not self.window and not self.master:
            return

        def _update_ui() -> None:
            if not self.window:
                self.start()

            if not self.window or not self.frame or not self.label or not self.canvas:
                return

            # Cancel any active hide timer or running count animation
            self._cancel_timers()

            bg_color = TOAST_BG         # Rich Dark Charcoal
            border_color = TOAST_BORDER  # Subtle Dark Border

            w, h = TEXT_TOAST_SIZE
            font_style = ("Segoe UI", 11, "bold")
            timeout = TEXT_TOAST_TIMEOUT_MS
            is_count = toast_type in COUNT_TOAST_TYPES

            if toast_type == "on":
                fg_color = TOAST_TEXT_FG    # Clean Sky Cyan
            elif toast_type == "off":
                fg_color = TOAST_TEXT_FG    # Muted Slate
            elif is_count:
                fg_color = TOAST_TEXT_FG
                w, h = COUNT_TOAST_SIZE
            else:  # "cleared"
                fg_color = TOAST_TEXT_FG    # Pure Pearl White

            self.frame.configure(bg=bg_color, highlightbackground=border_color)
            if not is_count:
                self._show_label(text, fg_color, bg_color, font_style)

            # Calculate bottom-right position dynamically
            try:
                user32 = ctypes.windll.user32  # type: ignore[attr-defined]
                sw = user32.GetSystemMetrics(0)
                sh = user32.GetSystemMetrics(1)
            except Exception:
                sw, sh = 1920, 1080

            x = max(0, sw - w - 30)
            y = max(0, sh - h - 70)

            if is_count:
                # Draw the first frame before the window appears so it never flashes the final number
                self._start_count(text, toast_type)
            self.window.geometry(f"{w}x{h}+{x}+{y}")
            self.window.deiconify()

            # Auto-hide after timeout (count toasts hide after their animation lands)
            if not is_count:
                self._schedule_hide(timeout)

        if self.master:
            self.master.after(0, _update_ui)
