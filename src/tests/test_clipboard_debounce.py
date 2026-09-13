"""
Unit tests for QPaste clipboard debounce and deduplication engine.
Tests Word multi-format burst, consecutive identical copy within/outside window,
rapid distinct copies, inactive state suppression, and programmatic paste protection.
"""

import os
import sys
import time
import unittest
from typing import List, Tuple
from unittest.mock import MagicMock, patch

# Ensure src directory is on sys.path for direct unittest invocation
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.clipboard_queue import ClipboardQueue
from core.listener import ShortcutHandler
from core.state import AppState


class MockClock:
    """Controllable clock for deterministic time-dependent tests."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self.current_time = initial_time

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


class TestClipboardDebounce(unittest.TestCase):
    """Tests debounce and deduplication logic in ShortcutHandler."""

    def setUp(self) -> None:
        self.state = AppState(initial_active=True)
        self.queue = ClipboardQueue()
        self.notifications: List[Tuple[str, str]] = []
        self.updates_count = 0

        def on_notify(msg: str, toast_type: str) -> None:
            self.notifications.append((msg, toast_type))

        def on_update() -> None:
            self.updates_count += 1

        self.handler = ShortcutHandler(
            state=self.state,
            queue=self.queue,
            on_notify_callback=on_notify,
            on_update_callback=on_update,
            debounce_ms=200.0,
            ignore_consecutive_duplicates=True,
            duplicate_window_sec=1.0,
        )

    def test_word_multi_format_burst_within_50ms(self) -> None:
        """
        Given an active ShortcutHandler,
        When simulating a Word multi-format burst of 3 consecutive identical copies within 50ms,
        Then only 1 item is enqueued, and only 1 notify callback with '1' is fired.
        """
        clock = MockClock(1000.0)
        text = "Word text snippet"

        with patch("core.listener.time.time", clock):
            # 1st format update (e.g. CF_UNICODETEXT) at 0ms
            self.handler.on_clipboard_changed(text)

            # 2nd format update (e.g. CF_TEXT) at 20ms (<50ms)
            clock.advance(0.02)
            self.handler.on_clipboard_changed(text)

            # 3rd format update (e.g. HTML Format) at 45ms (<50ms)
            clock.advance(0.025)
            self.handler.on_clipboard_changed(text)

        self.assertEqual(len(self.queue), 1)
        self.assertEqual(self.queue.get_items(), [text])
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0], ("1", "copy_count"))
        self.assertEqual(self.updates_count, 1)

    def test_word_multi_format_burst_real_timer(self) -> None:
        """
        Given an active ShortcutHandler with real-world clock,
        When 3 rapid consecutive identical copies occur within 50ms of real time,
        Then only 1 item is added to the queue and notified.
        """
        text = "Word text snippet real"
        start_time = time.time()

        self.handler.on_clipboard_changed(text)
        time.sleep(0.01)
        self.handler.on_clipboard_changed(text)
        time.sleep(0.01)
        self.handler.on_clipboard_changed(text)

        elapsed = time.time() - start_time
        self.assertLess(elapsed, 0.10)  # Verify burst occurred quickly
        self.assertEqual(len(self.queue), 1)
        self.assertEqual(self.queue.get_items(), [text])
        self.assertEqual(self.notifications, [("1", "copy_count")])

    def test_consecutive_identical_copy_within_one_second_dropped(self) -> None:
        """
        Given an active ShortcutHandler,
        When a duplicate copy occurs within the 1-second duplicate window (e.g. 0.5s),
        Then the second copy is dropped silently.
        """
        clock = MockClock(2000.0)
        text = "Repeated item"

        with patch("core.listener.time.time", clock):
            self.handler.on_clipboard_changed(text)

            clock.advance(0.5)
            self.handler.on_clipboard_changed(text)

        self.assertEqual(len(self.queue), 1)
        self.assertEqual(self.queue.get_items(), [text])
        self.assertEqual(len(self.notifications), 1)
        self.assertEqual(self.notifications[0], ("1", "copy_count"))

    def test_consecutive_identical_copy_after_one_point_five_seconds_accepted(self) -> None:
        """
        Given an active ShortcutHandler,
        When an identical copy occurs after 1.5 seconds (outside duplicate window),
        Then the second copy is accepted into the queue.
        """
        clock = MockClock(3000.0)
        text = "Repeated item after delay"

        with patch("core.listener.time.time", clock):
            self.handler.on_clipboard_changed(text)

            clock.advance(1.5)
            self.handler.on_clipboard_changed(text)

        self.assertEqual(len(self.queue), 2)
        self.assertEqual(self.queue.get_items(), [text, text])
        self.assertEqual(len(self.notifications), 2)
        self.assertEqual(self.notifications[0], ("1", "copy_count"))
        self.assertEqual(self.notifications[1], ("2", "copy_count"))

    def test_rapid_distinct_copies_both_added(self) -> None:
        """
        Given an active ShortcutHandler,
        When distinct items are copied in rapid succession within 20ms,
        Then both items are accepted and enqueued in sequence.
        """
        clock = MockClock(4000.0)

        with patch("core.listener.time.time", clock):
            self.handler.on_clipboard_changed("Item 1")

            clock.advance(0.02)
            self.handler.on_clipboard_changed("Item 2")

        self.assertEqual(len(self.queue), 2)
        self.assertEqual(self.queue.get_items(), ["Item 1", "Item 2"])
        self.assertEqual(len(self.notifications), 2)
        self.assertEqual(self.notifications[0], ("1", "copy_count"))
        self.assertEqual(self.notifications[1], ("2", "copy_count"))

    def test_queue_inactive_state_ignored(self) -> None:
        """
        Given an inactive ShortcutHandler (state.is_active() == False),
        When clipboard changes occur,
        Then all events are silently ignored and the queue remains empty.
        """
        self.state.set_active(False)

        self.handler.on_clipboard_changed("Inactive Copy")

        self.assertEqual(len(self.queue), 0)
        self.assertEqual(len(self.notifications), 0)
        self.assertEqual(self.updates_count, 0)

    def test_empty_or_none_clipboard_text_ignored(self) -> None:
        """
        Given an active ShortcutHandler,
        When clipboard changed event receives empty string or None,
        Then no action is taken.
        """
        self.handler.on_clipboard_changed("")
        self.handler.on_clipboard_changed(None)  # type: ignore[arg-type]

        self.assertEqual(len(self.queue), 0)
        self.assertEqual(len(self.notifications), 0)

    def test_handle_paste_updates_last_copied_text_preventing_echo(self) -> None:
        """
        Given a queue with an item,
        When handle_paste executes programmatic copy,
        Then _last_copied_text is set to the pasted text, preventing re-entry
        if an echo notification fires within debounce/duplicate window.
        """
        clock = MockClock(6000.0)
        self.queue.push("Pasted Text")
        self.assertEqual(len(self.queue), 1)

        with patch("core.listener.time.time", clock):
            with patch("core.listener.safe_copy") as mock_safe_copy:
                mock_safe_copy.return_value = True
                result = self.handler.handle_paste()

            self.assertTrue(result)
            self.assertEqual(self.handler._last_copied_text, "Pasted Text")
            self.assertTrue(self.handler._ignore_programmatic_copy)

            # First echo consumed by _ignore_programmatic_copy
            self.handler.on_clipboard_changed("Pasted Text")
            self.assertFalse(self.handler._ignore_programmatic_copy)
            self.assertEqual(len(self.queue), 0)

            # Second echo (burst format update from Windows echo) within debounce window
            clock.advance(0.05)
            self.handler.on_clipboard_changed("Pasted Text")

            self.assertEqual(len(self.queue), 0)

    def test_config_integration_allow_duplicates_when_disabled(self) -> None:
        """
        Given a ShortcutHandler linked to config with ignore_consecutive_duplicates=False,
        When identical text is copied after debounce_ms but within 1 second,
        Then the second copy is accepted.
        """
        mock_config = {
            "debounce_ms": 100.0,
            "ignore_consecutive_duplicates": False,
            "duplicate_window_sec": 2.0,
        }
        handler = ShortcutHandler(
            state=self.state,
            queue=self.queue,
            config=mock_config,
        )

        clock = MockClock(5000.0)
        with patch("core.listener.time.time", clock):
            # First copy at t0
            handler.on_clipboard_changed("Allow Dups")

            # Second copy at t0 + 0.15s (>100ms debounce, but <2.0s duplicate window)
            clock.advance(0.15)
            handler.on_clipboard_changed("Allow Dups")

        self.assertEqual(len(self.queue), 2)
        self.assertEqual(self.queue.get_items(), ["Allow Dups", "Allow Dups"])


if __name__ == "__main__":
    unittest.main()
