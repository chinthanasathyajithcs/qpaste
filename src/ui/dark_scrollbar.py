"""
Slim dark scrollbar for QPaste, drawn on a tk.Canvas.
The native Windows Tk scrollbar ignores colors, so this draws its own thumb.
"""

from __future__ import annotations

from typing import Any, Callable, Tuple

BAR_WIDTH = 8                # Slim bar, no arrow buttons
MIN_THUMB_LENGTH = 20        # Keeps the thumb grabbable on very long documents
THUMB_INSET = 1              # Horizontal padding of the thumb inside the bar
WHEEL_DELTA = 120            # Windows wheel delta per notch
WHEEL_LINES_PER_NOTCH = 3    # Lines scrolled per wheel notch over the bar
STATE_VISIBLE = "normal"
STATE_HIDDEN = "hidden"


class DarkScrollbar:
    """Canvas-backed scrollbar that follows a widget's yscrollcommand.

    Usage: build a tk.Canvas (width=BAR_WIDTH), pass it in with the widget's
    ``yview`` as ``command``, and give ``scrollbar.set`` to ``yscrollcommand``.
    """

    BAR_WIDTH = BAR_WIDTH
    MIN_THUMB_LENGTH = MIN_THUMB_LENGTH

    def __init__(
        self,
        canvas: Any,
        command: Callable[..., Any],
        trough_color: str,
        thumb_color: str,
        thumb_active_color: str,
    ) -> None:
        self.canvas: Any = canvas
        self.command: Callable[..., Any] = command
        self._thumb_color: str = thumb_color
        self._thumb_active_color: str = thumb_active_color
        self._first: float = 0.0
        self._last: float = 1.0
        self._hovering: bool = False
        self.dragging: bool = False
        self._grab_offset: float = 0.0

        try:
            canvas.configure(bg=trough_color)
        except Exception:
            pass
        self._thumb_id: Any = canvas.create_rectangle(
            0, 0, 0, 0, width=0, fill=thumb_color, state=STATE_HIDDEN,
        )

        canvas.bind("<ButtonPress-1>", self.on_press)
        canvas.bind("<B1-Motion>", self.on_drag)
        canvas.bind("<ButtonRelease-1>", self.on_release)
        canvas.bind("<Enter>", self.on_enter)
        canvas.bind("<Leave>", self.on_leave)
        canvas.bind("<Configure>", lambda _e: self._redraw())
        canvas.bind("<MouseWheel>", self.on_wheel)

    # -- scrollbar protocol -------------------------------------------------

    def set(self, first: Any, last: Any) -> None:
        """Receives the visible fraction from the widget's yscrollcommand."""
        try:
            self._first = float(first)
            self._last = float(last)
        except (TypeError, ValueError):
            return
        self._redraw()

    @property
    def thumb_visible(self) -> bool:
        """False when all content fits (nothing to scroll)."""
        return (self._last - self._first) < 1.0

    # -- geometry -----------------------------------------------------------

    def _trough_height(self) -> float:
        try:
            return float(self.canvas.winfo_height())
        except Exception:
            return 0.0

    def _thumb_length(self, height: float) -> float:
        span = self._last - self._first
        return min(height, max(float(MIN_THUMB_LENGTH), span * height))

    def thumb_bounds(self) -> Tuple[float, float]:
        """Returns (top, bottom) of the thumb in canvas pixels."""
        height = self._trough_height()
        length = self._thumb_length(height)
        travel = height - length
        first_max = 1.0 - (self._last - self._first)
        if first_max <= 0 or travel <= 0:
            return 0.0, length
        top = min(max(self._first / first_max, 0.0), 1.0) * travel
        return top, top + length

    # -- drawing ------------------------------------------------------------

    def current_thumb_color(self) -> str:
        """Thumb color: brighter while hovered or dragged."""
        return self._thumb_active_color if (self._hovering or self.dragging) else self._thumb_color

    def _redraw(self) -> None:
        try:
            if not self.thumb_visible:
                self.canvas.itemconfigure(self._thumb_id, state=STATE_HIDDEN)
                return
            top, bottom = self.thumb_bounds()
            self.canvas.coords(self._thumb_id, THUMB_INSET, top, BAR_WIDTH - THUMB_INSET, bottom)
            self.canvas.itemconfigure(
                self._thumb_id, state=STATE_VISIBLE, fill=self.current_thumb_color(),
            )
        except Exception:
            pass

    # -- mouse handlers -----------------------------------------------------

    def on_press(self, event: Any) -> None:
        """Starts a thumb drag, or pages when the trough is clicked."""
        if not self.thumb_visible:
            return
        top, bottom = self.thumb_bounds()
        if top <= event.y <= bottom:
            self.dragging = True
            self._grab_offset = event.y - top
            self._redraw()
        else:
            self.command("scroll", -1 if event.y < top else 1, "pages")

    def on_drag(self, event: Any) -> None:
        """Moves the view so the thumb follows the pointer."""
        if not self.dragging or not self.thumb_visible:
            return
        height = self._trough_height()
        travel = height - self._thumb_length(height)
        if travel <= 0:
            return
        ratio = min(max((event.y - self._grab_offset) / travel, 0.0), 1.0)
        self.command("moveto", ratio * (1.0 - (self._last - self._first)))

    def on_release(self, _event: Any) -> None:
        self.dragging = False
        self._redraw()

    def on_enter(self, _event: Any) -> None:
        self._hovering = True
        self._redraw()

    def on_leave(self, _event: Any) -> None:
        self._hovering = False
        self._redraw()

    def on_wheel(self, event: Any) -> None:
        """Scrolls the text when the wheel is used over the bar itself."""
        delta = getattr(event, "delta", 0)
        if not delta or not self.thumb_visible:
            return
        notches = max(1, round(abs(delta) / WHEEL_DELTA * WHEEL_LINES_PER_NOTCH))
        self.command("scroll", -notches if delta > 0 else notches, "units")
