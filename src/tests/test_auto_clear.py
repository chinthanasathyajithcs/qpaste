"""Unit tests for QPaste auto-clear queue expiration and idle activity engine."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig


class MockClock:
    """Controllable clock for deterministic time tests."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self.current_time: float = initial_time

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


class TestAutoClear(unittest.TestCase):
    """Test suite for config persistence, purge_expired, and idle activity engine."""

    def test_app_config_defaults_and_persistence(self) -> None:
        """Test loading, setting, and persisting AppConfig values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "test_config.json")
            config = AppConfig(config_path=config_path)
            self.assertFalse(config.get("auto_clear_enabled"))
            self.assertEqual(config.get("auto_clear_seconds"), 60)

            config.set("auto_clear_enabled", True)
            config.set("auto_clear_seconds", 300)
            self.assertTrue(config.get("auto_clear_enabled"))
            self.assertEqual(config.get("auto_clear_seconds"), 300)

            config_reloaded = AppConfig(config_path=config_path)
            self.assertTrue(config_reloaded.get("auto_clear_enabled"))
            self.assertEqual(config_reloaded.get("auto_clear_seconds"), 300)

    def test_clipboard_queue_purge_expired(self) -> None:
        """Test backwards-compatible purge_expired purges items older than timeout."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            queue.push("Item 1")
            clock.advance(1.0)
            queue.push("Item 2")
            clock.advance(10.0)
            queue.push("Item 3")
            self.assertEqual(len(queue), 3)
            self.assertEqual(queue.purge_expired(timeout_seconds=5.0), 2)
            self.assertEqual(queue.get_items(), ["Item 3"])

    def test_clipboard_queue_purge_expired_none_purged(self) -> None:
        """Test purge_expired returns 0 when no items exceed timeout."""
        queue = ClipboardQueue(max_size=10)
        queue.push("Fresh 1")
        queue.push("Fresh 2")
        self.assertEqual(queue.purge_expired(timeout_seconds=60.0), 0)
        self.assertEqual(len(queue), 2)

    def test_clipboard_queue_purge_expired_all_purged(self) -> None:
        """Test purge_expired purges all items if all exceed timeout."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            queue.push("Old 1")
            queue.push("Old 2")
            clock.advance(100.0)
            self.assertEqual(queue.purge_expired(timeout_seconds=60.0), 2)
            self.assertEqual(len(queue), 0)
            self.assertTrue(queue.is_empty())

    def test_is_idle_expired_with_mocked_time(self) -> None:
        """Test is_idle_expired across empty queue, timeouts, and elapsed time."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            clock.advance(100.0)
            self.assertFalse(queue.is_idle_expired(idle_timeout_seconds=30.0))

            queue.push("Alpha")
            self.assertFalse(queue.is_idle_expired(idle_timeout_seconds=0.0))
            self.assertFalse(queue.is_idle_expired(idle_timeout_seconds=-5.0))

            clock.advance(29.9)
            self.assertFalse(queue.is_idle_expired(idle_timeout_seconds=30.0))
            clock.advance(0.1)
            self.assertTrue(queue.is_idle_expired(idle_timeout_seconds=30.0))
            clock.advance(10.0)
            self.assertTrue(queue.is_idle_expired(idle_timeout_seconds=30.0))

    def test_push_and_push_front_updates_last_activity_and_resets_idle(self) -> None:
        """Verify push() and push_front() update _last_activity_time and reset idle."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            self.assertEqual(queue.get_last_activity_time(), 1000.0)

            clock.advance(50.0)
            queue.push("First")
            self.assertEqual(queue.get_last_activity_time(), 1050.0)

            clock.advance(55.0)
            self.assertFalse(queue.is_idle_expired(60.0))

            queue.push("Second")
            self.assertEqual(queue.get_last_activity_time(), 1105.0)

            clock.advance(45.0)
            self.assertFalse(queue.is_idle_expired(60.0))

            clock.advance(5.0)
            queue.push_front("Front")
            self.assertEqual(queue.get_last_activity_time(), 1155.0)
            clock.advance(50.0)
            self.assertFalse(queue.is_idle_expired(60.0))

            clock.advance(10.0)
            self.assertTrue(queue.is_idle_expired(60.0))

    def test_pop_updates_last_activity_and_resets_idle(self) -> None:
        """Verify pop() updates _last_activity_time and resets idle expiration."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            queue.push("A")
            queue.push("B")
            self.assertEqual(queue.get_last_activity_time(), 1000.0)

            clock.advance(55.0)
            self.assertFalse(queue.is_idle_expired(60.0))

            popped = queue.pop()
            self.assertEqual(popped, "A")
            self.assertEqual(queue.get_last_activity_time(), 1055.0)

            clock.advance(25.0)
            self.assertFalse(queue.is_idle_expired(60.0))

            clock.advance(35.0)
            self.assertTrue(queue.is_idle_expired(60.0))

    def test_touch_activity_and_modifications_update_timestamp(self) -> None:
        """Verify touch_activity, remove_at, promote_to_front, move_item, clear update activity."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            queue.push("1")
            queue.push("2")
            queue.push("3")

            clock.advance(40.0)
            queue.touch_activity()
            self.assertEqual(queue.get_last_activity_time(), 1040.0)

            clock.advance(20.0)
            queue.promote_to_front(1)
            self.assertEqual(queue.get_last_activity_time(), 1060.0)

            clock.advance(15.0)
            queue.move_item(0, 2)
            self.assertEqual(queue.get_last_activity_time(), 1075.0)

            clock.advance(10.0)
            queue.remove_at(0)
            self.assertEqual(queue.get_last_activity_time(), 1085.0)

            clock.advance(10.0)
            queue.clear()
            self.assertEqual(queue.get_last_activity_time(), 1095.0)

    def test_purge_idle_clears_queue_on_expiration(self) -> None:
        """Verify purge_idle() empties queue and returns count when threshold reached."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            queue.push("Item 1")
            queue.push("Item 2")
            queue.push("Item 3")

            clock.advance(30.0)
            self.assertEqual(queue.purge_idle(idle_timeout_seconds=60.0), 0)
            self.assertEqual(len(queue), 3)

            clock.advance(30.0)
            purged_count = queue.purge_idle(idle_timeout_seconds=60.0)
            self.assertEqual(purged_count, 3)
            self.assertEqual(len(queue), 0)
            self.assertTrue(queue.is_empty())
            self.assertEqual(queue.get_items(), [])
            self.assertEqual(queue.purge_idle(idle_timeout_seconds=60.0), 0)

    def test_purge_idle_does_not_purge_if_user_active_recently(self) -> None:
        """Verify purge_idle() does NOT purge if user was active within idle window."""
        clock = MockClock(1000.0)
        with patch("core.clipboard_queue.time.time", side_effect=clock):
            queue = ClipboardQueue(max_size=10)
            queue.push("Doc 1")
            queue.push("Doc 2")

            clock.advance(50.0)
            queue.push("Doc 3")

            clock.advance(20.0)
            self.assertEqual(queue.purge_idle(idle_timeout_seconds=60.0), 0)
            self.assertEqual(len(queue), 3)

            clock.advance(20.0)
            queue.pop()
            clock.advance(30.0)
            self.assertEqual(queue.purge_idle(idle_timeout_seconds=60.0), 0)
            self.assertEqual(len(queue), 2)


if __name__ == "__main__":
    unittest.main()
