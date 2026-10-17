"""
Unit tests for Quick Notepad HUD overlay.
Supports headless execution via Tkinter mocking.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.config import DEFAULT_CONFIG, AppConfig
import ui.notepad as notepad_mod
from ui.notepad import (
    QuickNotepadHUD,
    DARK_BG,
    CARD_BG,
    EDITOR_BG,
    ACCENT_PRIMARY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    DEFAULT_FONT_SIZE,
    MIN_FONT_SIZE,
    MAX_FONT_SIZE,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
)
from ui.dark_scrollbar import DarkScrollbar


class MockTkEvent:
    """Mock Tkinter event object."""

    def __init__(self, x: int = 0, y: int = 0, x_root: int = 0, y_root: int = 0, delta: int = 0) -> None:
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root
        self.delta = delta


class TestQuickNotepadHUD(unittest.TestCase):
    """Test suite for QuickNotepadHUD."""

    def setUp(self) -> None:
        self.mock_config = MagicMock(spec=AppConfig)
        self.mock_config.get.side_effect = lambda key, default=None: {
            "notepad_text": "Saved notes test",
            "notepad_geometry": "400x300+100+100",
        }.get(key, default)

        # Setup mock Tkinter environment
        self.mock_tk = MagicMock()
        self.mock_master = MagicMock()
        self.mock_window = MagicMock()
        self.mock_text = MagicMock()

        self.mock_tk.Tk.return_value = self.mock_master
        self.mock_tk.Toplevel.return_value = self.mock_window
        self.mock_tk.Text.return_value = self.mock_text

        # Synchronous execution of after callbacks in base mock
        self.mock_master.after.side_effect = lambda _ms, fn, *args: fn(*args)
        self.mock_window.after.side_effect = lambda _ms, fn, *args: fn(*args)

        # Track viewable state for window
        self._window_viewable = 0
        self.mock_window.deiconify.side_effect = lambda: setattr(self, "_window_viewable", 1)
        self.mock_window.withdraw.side_effect = lambda: setattr(self, "_window_viewable", 0)
        self.mock_window.winfo_viewable.side_effect = lambda: self._window_viewable

        self.mock_tk.WORD = "word"
        self.mock_tk.BOTH = "both"
        self.mock_tk.X = "x"
        self.mock_tk.Y = "y"
        self.mock_tk.TOP = "top"
        self.mock_tk.LEFT = "left"
        self.mock_tk.RIGHT = "right"
        self.mock_tk.FLAT = "flat"

        self.orig_tk = notepad_mod.tk
        notepad_mod.tk = self.mock_tk

    def tearDown(self) -> None:
        notepad_mod.tk = self.orig_tk

    def test_initialization_defaults(self) -> None:
        """Verify HUD initialization with default config."""
        hud = QuickNotepadHUD()
        self.assertIsNotNone(hud.config)
        self.assertIsNone(hud.window)
        self.assertIsNone(hud.text_widget)
        self.assertFalse(hud.is_visible())

    def test_initialization_and_content_loading(self) -> None:
        """Verify HUD builds GUI and loads initial text and geometry from config."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.mock_tk.Toplevel.assert_called_once()
        self.mock_window.overrideredirect.assert_called_with(True)
        self.mock_window.attributes.assert_called_with("-topmost", True)
        self.mock_window.configure.assert_called_with(bg=DARK_BG)
        self.mock_window.geometry.assert_called_with("400x300+100+100")

        self.mock_text.insert.assert_called_with("1.0", "Saved notes test")

    def test_show_and_hide(self) -> None:
        """Verify show and hide lifecycle."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud.show()

        self.mock_window.deiconify.assert_called_once()
        self.mock_window.lift.assert_called_once()
        self.mock_text.focus_set.assert_called_once()
        self.assertTrue(hud.is_visible())

        # Test hide persists content and geometry
        self.mock_text.get.return_value = "Updated note content"
        self.mock_window.geometry.return_value = "450x350+120+120"

        hud.hide()
        self.mock_config.set.assert_any_call("notepad_text", "Updated note content")
        self.mock_config.set.assert_any_call("notepad_geometry", "450x350+120+120")
        self.mock_window.withdraw.assert_called_once()
        self.assertFalse(hud.is_visible())

    def test_toggle(self) -> None:
        """Verify toggle alternates visibility."""
        hud = QuickNotepadHUD(config=self.mock_config)
        self.assertFalse(hud.is_visible())

        hud.toggle()
        self.assertTrue(hud.is_visible())
        self.mock_window.deiconify.assert_called_once()

        hud.toggle()
        self.assertFalse(hud.is_visible())
        self.mock_window.withdraw.assert_called_once()

    def test_text_persistence_on_edit(self) -> None:
        """Verify text persistence and auto-save scheduling on edit."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.mock_text.get.return_value = "Auto-saved text"
        self.mock_text.edit_modified.return_value = True

        hud._on_text_modified(None)
        self.mock_text.edit_modified.assert_called_with(False)
        self.mock_window.after.assert_called_with(300, hud.save_content)

        # Directly invoke save_content
        hud.save_content()
        self.mock_config.set.assert_called_with("notepad_text", "Auto-saved text")

    def test_escape_key_binding_hides_window(self) -> None:
        """Verify Escape key handler triggers hide."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        # Find escape binding on window
        escape_calls = [
            call for call in self.mock_window.bind.call_args_list
            if call[0][0] == "<Escape>"
        ]
        self.assertTrue(len(escape_calls) > 0)
        escape_handler = escape_calls[0][0][1]

        with patch.object(hud, "hide") as mock_hide:
            escape_handler(MockTkEvent())
            mock_hide.assert_called_once()

    def test_drag_handling_and_geometry_save(self) -> None:
        """Verify mouse dragging updates geometry and release persists geometry."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.mock_window.winfo_x.return_value = 100
        self.mock_window.winfo_y.return_value = 100

        # Start drag at root (120, 115) -> offset is (20, 15)
        hud._start_drag(MockTkEvent(x_root=120, y_root=115))
        self.assertEqual(hud._drag_offset_x, 20)
        self.assertEqual(hud._drag_offset_y, 15)

        # Drag motion to root (220, 215) -> new position is (200, 200)
        hud._on_drag(MockTkEvent(x_root=220, y_root=215))
        self.mock_window.geometry.assert_called_with("+200+200")

        # End drag persists geometry
        self.mock_window.geometry.return_value = "400x300+200+200"
        hud.save_geometry()
        self.mock_config.set.assert_called_with("notepad_geometry", "400x300+200+200")

    def test_thread_safe_dispatch(self) -> None:
        """Verify master.after is used for thread safety when master exists."""
        master_mock = MagicMock()
        hud = QuickNotepadHUD(config=self.mock_config, master=master_mock)
        hud.show()
        master_mock.after.assert_called_with(0, hud._show_main_thread)

        hud.hide()
        master_mock.after.assert_called_with(0, hud._hide_main_thread)

    def test_key_release_triggers_auto_save(self) -> None:
        """Verify KeyRelease binding triggers auto-save."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        keyrelease_calls = [
            call for call in self.mock_text.bind.call_args_list
            if call[0][0] == "<KeyRelease>"
        ]
        self.assertTrue(len(keyrelease_calls) > 0)
        key_handler = keyrelease_calls[0][0][1]

        with patch.object(hud, "_schedule_auto_save") as mock_save:
            key_handler(MockTkEvent())
            mock_save.assert_called_once()

    def test_timer_cancel_on_reschedule(self) -> None:
        """Verify pending save timer is cancelled when rescheduled."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        hud._save_timer_id = "timer_123"

        hud._schedule_auto_save()
        self.mock_window.after_cancel.assert_called_with("timer_123")

    def test_safe_fallbacks_when_tk_none(self) -> None:
        """Verify methods execute safely when tk or widgets are None."""
        notepad_mod.tk = None
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        self.assertIsNone(hud.window)

        # Calling save methods when widgets are None should not crash
        hud.save_content()
        hud.save_geometry()
        self.assertFalse(hud.is_visible())

    # ------------------------------------------------------------------ zoom

    def _bound_handler(self, sequence: str):
        calls = [c for c in self.mock_text.bind.call_args_list if c[0][0] == sequence]
        self.assertTrue(calls, f"no binding for {sequence}")
        return calls[0][0][1]

    def _last_font(self):
        return self.mock_text.configure.call_args.kwargs["font"]

    def test_initial_font_size_is_default(self) -> None:
        """Verify the Text widget is built with Consolas at the default size."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.assertEqual(DEFAULT_FONT_SIZE, 10)
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE)
        font = self.mock_tk.Text.call_args.kwargs["font"]
        self.assertEqual(font, ("Consolas", DEFAULT_FONT_SIZE))

    def test_saved_font_size_is_loaded(self) -> None:
        """Verify notepad_font_size from config is applied when building the GUI."""
        self.mock_config.get.side_effect = lambda key, default=None: {
            "notepad_font_size": 16,
        }.get(key, default)
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.assertEqual(hud._font_size, 16)
        self.assertEqual(self.mock_tk.Text.call_args.kwargs["font"], ("Consolas", 16))

    def test_saved_font_size_out_of_range_or_invalid_is_sanitised(self) -> None:
        """Verify bad saved sizes are clamped or fall back to the default."""
        cases = {99: MAX_FONT_SIZE, 1: MIN_FONT_SIZE, "junk": DEFAULT_FONT_SIZE, None: DEFAULT_FONT_SIZE}
        for saved, expected in cases.items():
            with self.subTest(saved=saved):
                self.mock_config.get.side_effect = lambda key, default=None, v=saved: (
                    v if key == "notepad_font_size" else default
                )
                hud = QuickNotepadHUD(config=self.mock_config)
                hud._build_gui()
                self.assertEqual(hud._font_size, expected)

    def test_zoom_in_out_and_reset_via_key_handlers(self) -> None:
        """Verify zoom handlers change the size by one point and return break."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        zoom_in = self._bound_handler("<Control-equal>")
        zoom_out = self._bound_handler("<Control-minus>")
        reset = self._bound_handler("<Control-0>")

        self.assertEqual(zoom_in(MockTkEvent()), "break")
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE + 1)
        self.assertEqual(self._last_font(), ("Consolas", DEFAULT_FONT_SIZE + 1))

        self.assertEqual(zoom_out(MockTkEvent()), "break")
        self.assertEqual(zoom_out(MockTkEvent()), "break")
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE - 1)

        self.assertEqual(reset(MockTkEvent()), "break")
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE)
        self.assertEqual(self._last_font(), ("Consolas", DEFAULT_FONT_SIZE))

    def test_all_zoom_key_sequences_are_bound(self) -> None:
        """Verify every requested zoom shortcut is bound on the Text widget."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        bound = {c[0][0] for c in self.mock_text.bind.call_args_list}
        for seq in (
            "<Control-equal>", "<Control-plus>", "<Control-KP_Add>",
            "<Control-minus>", "<Control-KP_Subtract>",
            "<Control-0>", "<Control-KP_0>", "<Control-MouseWheel>",
        ):
            self.assertIn(seq, bound)

    def test_zoom_clamps_at_both_ends(self) -> None:
        """Verify zoom never leaves the MIN..MAX font size range."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        for _ in range(MAX_FONT_SIZE * 2):
            hud.zoom_in()
        self.assertEqual(hud._font_size, MAX_FONT_SIZE)

        for _ in range(MAX_FONT_SIZE * 2):
            hud.zoom_out()
        self.assertEqual(hud._font_size, MIN_FONT_SIZE)

    def test_zoom_persists_font_size(self) -> None:
        """Verify each zoom change is saved under notepad_font_size."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        hud.zoom_in()
        self.mock_config.set.assert_called_with("notepad_font_size", DEFAULT_FONT_SIZE + 1)
        hud.reset_zoom()
        self.mock_config.set.assert_called_with("notepad_font_size", DEFAULT_FONT_SIZE)

    def test_ctrl_wheel_zooms_and_plain_wheel_is_untouched(self) -> None:
        """Verify Ctrl+wheel zooms by delta sign and no plain wheel binding is added."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        wheel = self._bound_handler("<Control-MouseWheel>")

        self.assertEqual(wheel(MockTkEvent(delta=120)), "break")
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE + 1)
        self.assertEqual(wheel(MockTkEvent(delta=-120)), "break")
        self.assertEqual(wheel(MockTkEvent(delta=-120)), "break")
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE - 1)

        bound = {c[0][0] for c in self.mock_text.bind.call_args_list}
        self.assertNotIn("<MouseWheel>", bound)

    def test_ctrl_wheel_accumulates_small_touchpad_deltas(self) -> None:
        """Verify precision-touchpad deltas zoom one step per 120 units, not one per event."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        wheel = self._bound_handler("<Control-MouseWheel>")

        for _ in range(3):
            wheel(MockTkEvent(delta=30))
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE)
        wheel(MockTkEvent(delta=30))
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE + 1)

        wheel(MockTkEvent(delta=-60))
        wheel(MockTkEvent(delta=-60))
        self.assertEqual(hud._font_size, DEFAULT_FONT_SIZE)

    def test_font_size_default_registered_in_config(self) -> None:
        """Verify config ships a notepad_font_size default matching the HUD default."""
        self.assertEqual(DEFAULT_CONFIG["notepad_font_size"], DEFAULT_FONT_SIZE)

    def test_zoom_before_gui_built_is_safe(self) -> None:
        """Verify zoom helpers do not crash when the window does not exist."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud.zoom_in()
        hud.zoom_out()
        hud.reset_zoom()

    # ---------------------------------------------------------------- resize

    def test_resize_grip_uses_diagonal_cursor_and_bindings(self) -> None:
        """Verify a resize grip is created with the size_nw_se cursor."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        cursors = [c.kwargs.get("cursor") for c in self.mock_tk.Label.call_args_list]
        self.assertIn("size_nw_se", cursors)

    def test_resize_drag_changes_size_and_keeps_position(self) -> None:
        """Verify dragging the grip grows the window by the pointer delta."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        self.mock_window.winfo_width.return_value = 400
        self.mock_window.winfo_height.return_value = 300

        hud._start_resize(MockTkEvent(x_root=500, y_root=400))
        hud._on_resize(MockTkEvent(x_root=560, y_root=430))

        self.mock_window.geometry.assert_called_with("460x330")

    def test_resize_enforces_minimum_size(self) -> None:
        """Verify shrinking past the minimum clamps to MIN_WINDOW_WIDTH x HEIGHT."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        self.mock_window.winfo_width.return_value = 400
        self.mock_window.winfo_height.return_value = 300

        self.assertGreaterEqual(MIN_WINDOW_WIDTH, 260)
        self.assertGreaterEqual(MIN_WINDOW_HEIGHT, 160)

        hud._start_resize(MockTkEvent(x_root=500, y_root=400))
        hud._on_resize(MockTkEvent(x_root=0, y_root=0))

        self.mock_window.geometry.assert_called_with(f"{MIN_WINDOW_WIDTH}x{MIN_WINDOW_HEIGHT}")

    def test_resize_release_saves_geometry(self) -> None:
        """Verify releasing the grip persists the geometry."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()
        self.mock_window.geometry.return_value = "460x330+100+100"

        hud._end_resize(MockTkEvent())

        self.mock_config.set.assert_called_with("notepad_geometry", "460x330+100+100")

    def test_resize_handlers_safe_without_window(self) -> None:
        """Verify resize handlers no-op before the GUI is built."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._start_resize(MockTkEvent())
        hud._on_resize(MockTkEvent())
        hud._end_resize(MockTkEvent())

    def test_text_uses_dark_scrollbar_not_native(self) -> None:
        """Verify the Text yscrollcommand is wired to the custom scrollbar."""
        hud = QuickNotepadHUD(config=self.mock_config)
        hud._build_gui()

        self.mock_tk.Canvas.assert_called()
        self.mock_tk.Scrollbar.assert_not_called()
        self.assertIsInstance(hud.scrollbar, DarkScrollbar)
        self.mock_text.configure.assert_any_call(yscrollcommand=hud.scrollbar.set)


class TestDarkScrollbar(unittest.TestCase):
    """Display-free tests of the custom scrollbar geometry and behaviour."""

    HEIGHT = 200

    def setUp(self) -> None:
        self.canvas = MagicMock()
        self.canvas.winfo_height.return_value = self.HEIGHT
        self.canvas.create_rectangle.return_value = 7
        self.command = MagicMock()
        self.bar = DarkScrollbar(
            self.canvas, self.command, trough_color="#111", thumb_color="#222", thumb_active_color="#333",
        )

    def test_thumb_hidden_when_content_fits(self) -> None:
        self.bar.set("0.0", "1.0")
        self.assertFalse(self.bar.thumb_visible)

    def test_thumb_shown_when_content_overflows(self) -> None:
        self.bar.set("0.0", "0.5")
        self.assertTrue(self.bar.thumb_visible)

    def test_thumb_geometry_tracks_view_fraction(self) -> None:
        self.bar.set("0.25", "0.75")
        top, bottom = self.bar.thumb_bounds()
        # Span 0.5 -> 100px thumb; first=0.25 of a 0.5 max -> halfway along 100px travel.
        self.assertAlmostEqual(top, 50)
        self.assertAlmostEqual(bottom, 150)

    def test_thumb_has_minimum_length(self) -> None:
        self.bar.set("0.0", "0.001")
        top, bottom = self.bar.thumb_bounds()
        self.assertGreaterEqual(bottom - top, DarkScrollbar.MIN_THUMB_LENGTH)

    def test_thumb_stays_inside_trough_at_bottom(self) -> None:
        self.bar.set("0.999", "1.0")
        top, bottom = self.bar.thumb_bounds()
        self.assertLessEqual(bottom, self.HEIGHT)
        self.assertGreaterEqual(top, 0)

    def test_trough_click_above_thumb_pages_up(self) -> None:
        self.bar.set("0.5", "0.6")
        self.bar.on_press(MockTkEvent(y=2))
        self.command.assert_called_with("scroll", -1, "pages")

    def test_trough_click_below_thumb_pages_down(self) -> None:
        self.bar.set("0.0", "0.1")
        self.bar.on_press(MockTkEvent(y=self.HEIGHT - 2))
        self.command.assert_called_with("scroll", 1, "pages")

    def test_dragging_thumb_issues_moveto(self) -> None:
        self.bar.set("0.0", "0.5")  # thumb spans 0..100 of 200
        self.bar.on_press(MockTkEvent(y=10))
        self.assertTrue(self.bar.dragging)
        self.bar.on_drag(MockTkEvent(y=60))  # thumb top moves 0 -> 50 of 100 travel
        name, fraction = self.command.call_args[0]
        self.assertEqual(name, "moveto")
        self.assertAlmostEqual(fraction, 0.25)  # first = 0.5 * (50/100)

    def test_drag_is_clamped_to_valid_range(self) -> None:
        self.bar.set("0.0", "0.5")
        self.bar.on_press(MockTkEvent(y=10))
        self.bar.on_drag(MockTkEvent(y=-500))
        self.assertEqual(self.command.call_args[0], ("moveto", 0.0))
        self.bar.on_drag(MockTkEvent(y=5000))
        self.assertAlmostEqual(self.command.call_args[0][1], 0.5)

    def test_release_ends_drag(self) -> None:
        self.bar.set("0.0", "0.5")
        self.bar.on_press(MockTkEvent(y=10))
        self.bar.on_release(MockTkEvent())
        self.assertFalse(self.bar.dragging)

    def test_hover_and_drag_use_active_color(self) -> None:
        self.bar.set("0.0", "0.5")
        self.assertEqual(self.bar.current_thumb_color(), "#222")
        self.bar.on_enter(MockTkEvent())
        self.assertEqual(self.bar.current_thumb_color(), "#333")
        self.bar.on_leave(MockTkEvent())
        self.assertEqual(self.bar.current_thumb_color(), "#222")
        self.bar.on_press(MockTkEvent(y=10))
        self.bar.on_leave(MockTkEvent())
        self.assertEqual(self.bar.current_thumb_color(), "#333")

    def test_press_and_drag_ignored_when_content_fits(self) -> None:
        self.bar.set("0.0", "1.0")
        self.bar.on_press(MockTkEvent(y=50))
        self.bar.on_drag(MockTkEvent(y=80))
        self.command.assert_not_called()

    def test_wheel_over_bar_scrolls_text(self) -> None:
        self.bar.set("0.0", "0.5")
        self.bar.on_wheel(MockTkEvent(delta=-120))
        self.command.assert_called_with("scroll", 3, "units")


if __name__ == "__main__":
    unittest.main()
