"""
Unit tests for QPaste Task 1: Persistent Configuration & Auto-Clear Queue Expiration Engine.
"""
import os
import tempfile
import time
import pytest

from core.config import AppConfig
from core.clipboard_queue import ClipboardQueue


def test_app_config_defaults_and_persistence():
    """Test loading, setting, and persisting AppConfig values to temporary JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "test_config.json")
        config = AppConfig(config_path=config_path)

        assert config.get("auto_clear_enabled") is False
        assert config.get("auto_clear_seconds") == 60

        config.set("auto_clear_enabled", True)
        config.set("auto_clear_seconds", 300)

        assert config.get("auto_clear_enabled") is True
        assert config.get("auto_clear_seconds") == 300

        # Reload from disk
        config_reloaded = AppConfig(config_path=config_path)
        assert config_reloaded.get("auto_clear_enabled") is True
        assert config_reloaded.get("auto_clear_seconds") == 300


def test_clipboard_queue_purge_expired():
    """Test ClipboardQueue purge_expired purges items older than specified timeout."""
    queue = ClipboardQueue(max_size=10)
    queue.push("Item 1")
    queue.push("Item 2")
    queue.push("Item 3")

    assert len(queue) == 3

    # Backdate item 1 and item 2 timestamps by 10 seconds
    with queue._lock:
        now = time.time()
        queue._queue[0] = (queue._queue[0][0], now - 10.0)
        queue._queue[1] = (queue._queue[1][0], now - 10.0)
        # Item 3 remains fresh (now)

    # Purge items older than 5 seconds
    purged_count = queue.purge_expired(timeout_seconds=5.0)

    assert purged_count == 2
    assert len(queue) == 1
    assert queue.get_items() == ["Item 3"]


def test_clipboard_queue_purge_expired_none_purged():
    """Test purge_expired returns 0 when no items exceed timeout."""
    queue = ClipboardQueue(max_size=10)
    queue.push("Fresh Item 1")
    queue.push("Fresh Item 2")

    purged_count = queue.purge_expired(timeout_seconds=60.0)
    assert purged_count == 0
    assert len(queue) == 2


def test_clipboard_queue_purge_expired_all_purged():
    """Test purge_expired purges all items if all exceed timeout."""
    queue = ClipboardQueue(max_size=10)
    queue.push("Old 1")
    queue.push("Old 2")

    with queue._lock:
        now = time.time()
        queue._queue[0] = (queue._queue[0][0], now - 100.0)
        queue._queue[1] = (queue._queue[1][0], now - 100.0)

    purged_count = queue.purge_expired(timeout_seconds=60.0)
    assert purged_count == 2
    assert len(queue) == 0
    assert queue.is_empty() is True
