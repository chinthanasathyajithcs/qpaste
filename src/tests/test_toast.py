"""
Unit tests for the NativeToastOverlay rolling-digit count animation.
Runs headless: Tkinter is mocked, `after` is driven by a manual scheduler and time by a fake clock.
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import ui.toast as toast_mod
from ui.toast import (
    COUNT_ANIM_DURATION_MS,
    COUNT_CANVAS_HEIGHT,
    COUNT_TOAST_TIMEOUT_MS,
    ROLL_DOWN,
    ROLL_UP,
    NativeToastOverlay,
    ease_out_cubic,
    resolve_count_roll,
    roll_offsets,
)

CENTER_Y = COUNT_CANVAS_HEIGHT / 2
HEIGHT = COUNT_CANVAS_HEIGHT


class ManualScheduler:
    """Records Tk `after` callbacks so tests decide when they fire."""

    def __init__(self) -> None:
        self._next_id = 0
        self.pending: Dict[str, Tuple[int, Callable[..., None]]] = {}
        self.cancelled: List[str] = []

    def after(self, ms: int, fn: Callable[..., None], *args: Any) -> str:
        self._next_id += 1
        timer_id = f"after#{self._next_id}"
        self.pending[timer_id] = (ms, lambda: fn(*args))
        return timer_id

    def after_cancel(self, timer_id: str) -> None:
        self.cancelled.append(timer_id)
        self.pending.pop(timer_id, None)

    def delays(self) -> List[int]:
        return [ms for ms, _ in self.pending.values()]

    def fire_next_frame(self) -> None:
        """Fires the pending animation frame (any pending timer except the hide timer)."""
        for timer_id, (ms, fn) in list(self.pending.items()):
            if ms != COUNT_TOAST_TIMEOUT_MS and ms != 2000:
                del self.pending[timer_id]
                fn()
                return
        raise AssertionError("no animation frame pending")

    def fire_hide(self) -> None:
        for timer_id, (ms, fn) in list(self.pending.items()):
            if ms in (COUNT_TOAST_TIMEOUT_MS, 2000):
                del self.pending[timer_id]
                fn()
                return
        raise AssertionError("no hide timer pending")


class TestRollMath(unittest.TestCase):
    """Pure helpers: derivation of old/new numbers and easing positions."""

    def test_copy_count_rolls_up_from_previous_number(self) -> None:
        self.assertEqual(resolve_count_roll("2", "copy_count"), ("1", "2", ROLL_UP))

    def test_first_copy_rolls_up_from_zero(self) -> None:
        self.assertEqual(resolve_count_roll("1", "copy_count"), ("0", "1", ROLL_UP))

    def test_paste_count_rolls_down_from_next_number(self) -> None:
        self.assertEqual(resolve_count_roll("1", "paste_count"), ("2", "1", ROLL_DOWN))

    def test_last_paste_rolls_down_to_zero(self) -> None:
        self.assertEqual(resolve_count_roll("0", "paste_count"), ("1", "0", ROLL_DOWN))

    def test_static_and_text_types_do_not_roll(self) -> None:
        for toast_type in ("count_static", "on", "off", "cleared", "notepad", "info"):
            self.assertIsNone(resolve_count_roll("25", toast_type))

    def test_non_numeric_count_text_does_not_roll(self) -> None:
        self.assertIsNone(resolve_count_roll("abc", "copy_count"))

    def test_ease_out_hits_exact_endpoints(self) -> None:
        self.assertEqual(ease_out_cubic(0.0), 0.0)
        self.assertEqual(ease_out_cubic(1.0), 1.0)

    def test_ease_out_clamps_out_of_range_progress(self) -> None:
        self.assertEqual(ease_out_cubic(-0.5), 0.0)
        self.assertEqual(ease_out_cubic(3.0), 1.0)

    def test_ease_out_decelerates(self) -> None:
        self.assertGreater(ease_out_cubic(0.5), 0.5)
        self.assertGreater(ease_out_cubic(0.25), 0.25)
        self.assertLess(ease_out_cubic(0.9) - ease_out_cubic(0.8), ease_out_cubic(0.2) - ease_out_cubic(0.1))

    def test_roll_up_offsets_reach_exact_final_values(self) -> None:
        self.assertEqual(roll_offsets(0.0, ROLL_UP, HEIGHT), (0, HEIGHT))
        self.assertEqual(roll_offsets(1.0, ROLL_UP, HEIGHT), (-HEIGHT, 0))

    def test_roll_down_offsets_reach_exact_final_values(self) -> None:
        self.assertEqual(roll_offsets(0.0, ROLL_DOWN, HEIGHT), (0, -HEIGHT))
        self.assertEqual(roll_offsets(1.0, ROLL_DOWN, HEIGHT), (HEIGHT, 0))


class TestCountToast(unittest.TestCase):
    """Toast behavior with mocked Tk, scheduler and clock."""

    def setUp(self) -> None:
        self.scheduler = ManualScheduler()
        self.now = 100.0

        self.mock_tk = MagicMock()
        self.window = MagicMock()
        self.frame = MagicMock()
        self.label = MagicMock()
        self.canvas = MagicMock()
        self.canvas.create_text.side_effect = ["old_item", "new_item"]
        self.mock_tk.Toplevel.return_value = self.window
        self.mock_tk.Frame.return_value = self.frame
        self.mock_tk.Label.return_value = self.label
        self.mock_tk.Canvas.return_value = self.canvas
        self.window.after.side_effect = self.scheduler.after
        self.window.after_cancel.side_effect = self.scheduler.after_cancel

        self.master = MagicMock()
        self.master.after.side_effect = lambda _ms, fn, *args: fn(*args)

        # Keep the real Win32 API out of the test: it cannot take mock window handles
        self.mock_ctypes = MagicMock()
        user32 = self.mock_ctypes.windll.user32
        user32.GetParent.return_value = 1
        user32.GetWindowLongW.return_value = 0
        user32.GetSystemMetrics.side_effect = lambda index: 1920 if index == 0 else 1080

        self.orig_tk = toast_mod.tk
        self.orig_ctypes = toast_mod.ctypes
        toast_mod.tk = self.mock_tk
        toast_mod.ctypes = self.mock_ctypes

        self.toast = NativeToastOverlay(master=self.master, clock=lambda: self.now)
        self.toast.start()

    def tearDown(self) -> None:
        toast_mod.tk = self.orig_tk
        toast_mod.ctypes = self.orig_ctypes

    # ---- helpers -----------------------------------------------------------

    def _item_y(self, item: str) -> float:
        """Last y passed to canvas.coords for an item."""
        for call in reversed(self.canvas.coords.call_args_list):
            if call.args[0] == item:
                return call.args[-1]
        raise AssertionError(f"{item} was never positioned")

    def _item_text(self, item: str) -> str:
        for call in reversed(self.canvas.itemconfigure.call_args_list):
            if call.args[0] == item and "text" in call.kwargs:
                return call.kwargs["text"]
        raise AssertionError(f"{item} never had text set")

    def _run_animation_to_end(self) -> None:
        self.now += COUNT_ANIM_DURATION_MS / 1000.0 + 0.001
        self.scheduler.fire_next_frame()

    # ---- tests -------------------------------------------------------------

    def test_copy_count_starts_with_old_number_centered_and_new_below(self) -> None:
        self.toast.show_toast("2", "copy_count")

        self.assertEqual(self._item_text("old_item"), "1")
        self.assertEqual(self._item_text("new_item"), "2")
        self.assertEqual(self._item_y("old_item"), CENTER_Y)
        self.assertEqual(self._item_y("new_item"), CENTER_Y + HEIGHT)
        self.window.deiconify.assert_called()

    def test_copy_count_ends_with_old_out_above_and_new_centered(self) -> None:
        self.toast.show_toast("2", "copy_count")

        self._run_animation_to_end()

        self.assertEqual(self._item_y("old_item"), CENTER_Y - HEIGHT)
        self.assertEqual(self._item_y("new_item"), CENTER_Y)

    def test_paste_count_rolls_down(self) -> None:
        self.toast.show_toast("1", "paste_count")

        self.assertEqual(self._item_text("old_item"), "2")
        self.assertEqual(self._item_text("new_item"), "1")
        self.assertEqual(self._item_y("new_item"), CENTER_Y - HEIGHT)

        self._run_animation_to_end()

        self.assertEqual(self._item_y("old_item"), CENTER_Y + HEIGHT)
        self.assertEqual(self._item_y("new_item"), CENTER_Y)

    def test_last_paste_shows_zero(self) -> None:
        self.toast.show_toast("0", "paste_count")

        self.assertEqual(self._item_text("old_item"), "1")
        self.assertEqual(self._item_text("new_item"), "0")

        self._run_animation_to_end()

        self.assertEqual(self._item_y("new_item"), CENTER_Y)

    def test_mid_animation_frame_is_between_endpoints_and_schedules_next_frame(self) -> None:
        self.toast.show_toast("2", "copy_count")

        self.now += (COUNT_ANIM_DURATION_MS / 1000.0) / 2
        self.scheduler.fire_next_frame()

        self.assertLess(CENTER_Y - HEIGHT, self._item_y("old_item"))
        self.assertLess(self._item_y("old_item"), CENTER_Y)
        self.assertGreater(self._item_y("new_item"), CENTER_Y)
        self.assertLess(self._item_y("new_item"), CENTER_Y + HEIGHT)
        self.assertEqual(len(self.scheduler.pending), 1)

    def test_hide_timer_starts_only_after_animation_finishes(self) -> None:
        self.toast.show_toast("2", "copy_count")
        self.assertNotIn(COUNT_TOAST_TIMEOUT_MS, self.scheduler.delays())

        self._run_animation_to_end()

        self.assertEqual(self.scheduler.delays(), [COUNT_TOAST_TIMEOUT_MS])
        self.scheduler.fire_hide()
        self.window.withdraw.assert_called()

    def test_count_static_shows_number_without_animation(self) -> None:
        self.toast.show_toast("25", "count_static")

        self.assertEqual(self._item_text("new_item"), "25")
        self.assertEqual(self._item_y("new_item"), CENTER_Y)
        self.assertEqual(self.scheduler.delays(), [COUNT_TOAST_TIMEOUT_MS])
        self.window.deiconify.assert_called()

    def test_non_numeric_count_text_falls_back_to_static(self) -> None:
        self.toast.show_toast("abc", "copy_count")

        self.assertEqual(self._item_text("new_item"), "abc")
        self.assertEqual(self.scheduler.delays(), [COUNT_TOAST_TIMEOUT_MS])

    def test_new_count_mid_animation_cancels_running_animation(self) -> None:
        self.toast.show_toast("2", "copy_count")
        self.now += 0.05
        self.scheduler.fire_next_frame()
        first_frame_timer = next(iter(self.scheduler.pending))

        self.toast.show_toast("3", "copy_count")

        self.assertIn(first_frame_timer, self.scheduler.cancelled)
        self.assertEqual(len(self.scheduler.pending), 1)
        self.assertEqual(self._item_text("old_item"), "2")
        self.assertEqual(self._item_text("new_item"), "3")
        self.assertEqual(self._item_y("old_item"), CENTER_Y)
        self.assertEqual(self._item_y("new_item"), CENTER_Y + HEIGHT)

    def test_new_count_after_animation_cancels_hide_timer(self) -> None:
        self.toast.show_toast("2", "copy_count")
        self._run_animation_to_end()
        hide_timer = next(iter(self.scheduler.pending))

        self.toast.show_toast("1", "paste_count")

        self.assertIn(hide_timer, self.scheduler.cancelled)
        self.assertNotIn(COUNT_TOAST_TIMEOUT_MS, self.scheduler.delays())

    def test_interrupted_toast_ends_with_single_hide_timer(self) -> None:
        self.toast.show_toast("2", "copy_count")
        self.toast.show_toast("3", "copy_count")
        self.toast.show_toast("2", "paste_count")

        self._run_animation_to_end()

        self.assertEqual(self.scheduler.delays(), [COUNT_TOAST_TIMEOUT_MS])
        self.assertEqual(self._item_y("new_item"), CENTER_Y)

    def test_text_toast_after_count_toast_restores_label_and_cancels_animation(self) -> None:
        self.toast.show_toast("2", "copy_count")
        frame_timer = next(iter(self.scheduler.pending))

        self.toast.show_toast("QPaste : OFF", "off")

        self.assertIn(frame_timer, self.scheduler.cancelled)
        self.canvas.pack_forget.assert_called()
        self.label.configure.assert_called()
        self.assertEqual(self.label.configure.call_args.kwargs["text"], "QPaste : OFF")
        self.assertEqual(self.scheduler.delays(), [2000])

    def test_count_toast_uses_existing_box_and_font(self) -> None:
        self.toast.show_toast("2", "copy_count")

        geometry = self.window.geometry.call_args.args[0]
        self.assertTrue(geometry.startswith("70x50+"))
        font = self.canvas.create_text.call_args.kwargs["font"]
        self.assertEqual(font, ("Segoe UI", 16, "bold"))
        self.assertEqual(self.canvas.create_text.call_args.kwargs["fill"], "#94A3B8")


if __name__ == "__main__":
    unittest.main()
