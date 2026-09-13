"""
Unit tests for QPaste configuration schema: hotkeys, notepad, and auto-clear.
Tests default schema, get/set hotkeys, reset hotkeys, backwards compatibility, and thread safety.
"""

import json
import os
import sys
import tempfile
import threading
import unittest
from typing import Any, Dict, List

# Ensure src directory is on sys.path for direct unittest invocation
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.config import DEFAULT_CONFIG, AppConfig


class TestConfigHotkeys(unittest.TestCase):
    """Tests hotkeys, notepad, and auto-clear configuration functionality."""

    def setUp(self) -> None:
        self.temp_dir: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.config_path: str = os.path.join(self.temp_dir.name, "config.json")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_schema_initialization(self) -> None:
        """Given a fresh AppConfig, Then all default keys and hotkeys should be initialized."""
        # When
        config = AppConfig(config_path=self.config_path)

        # Then
        self.assertFalse(config.get("auto_clear_enabled"))
        self.assertEqual(config.get("auto_clear_seconds"), 60)
        self.assertEqual(config.get("auto_clear_mode"), "idle")
        self.assertTrue(config.get("ignore_consecutive_duplicates"))
        self.assertEqual(config.get("notepad_text"), "")
        self.assertEqual(config.get("notepad_geometry"), "360x280+150+150")

        # Hotkeys defaults
        self.assertEqual(config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(config.get_hotkey("clear_queue"), "Shift+F4")
        self.assertEqual(config.get_hotkey("toggle_notepad"), "F3")

        expected_hotkeys: Dict[str, str] = {
            "toggle_queue": "F4",
            "clear_queue": "Shift+F4",
            "toggle_notepad": "F3",
        }
        self.assertEqual(config.get_all_hotkeys(), expected_hotkeys)

    def test_get_and_set_hotkeys(self) -> None:
        """Given an AppConfig instance, When setting hotkeys, Then changes persist to disk."""
        # Given
        config = AppConfig(config_path=self.config_path)

        # When
        config.set_hotkey("toggle_queue", "Ctrl+Alt+Q")
        config.set_hotkey("custom_action", "F10")

        # Then
        self.assertEqual(config.get_hotkey("toggle_queue"), "Ctrl+Alt+Q")
        self.assertEqual(config.get_hotkey("custom_action"), "F10")
        self.assertEqual(config.get_hotkey("unknown_action", default="DefaultKey"), "DefaultKey")
        self.assertEqual(config.get_hotkey("nonexistent"), "")

        # Verify persistence after reload from disk
        reloaded_config = AppConfig(config_path=self.config_path)
        self.assertEqual(reloaded_config.get_hotkey("toggle_queue"), "Ctrl+Alt+Q")
        self.assertEqual(reloaded_config.get_hotkey("custom_action"), "F10")
        self.assertEqual(reloaded_config.get_hotkey("clear_queue"), "Shift+F4")

    def test_reset_hotkeys(self) -> None:
        """Given an AppConfig with modified hotkeys, When reset_hotkeys is called, Then hotkeys revert to defaults."""
        # Given
        config = AppConfig(config_path=self.config_path)
        config.set_hotkey("toggle_queue", "Ctrl+Shift+T")
        config.set_hotkey("clear_queue", "Ctrl+Shift+C")
        config.set_hotkey("toggle_notepad", "Ctrl+Shift+N")

        # When
        config.reset_hotkeys()

        # Then
        self.assertEqual(config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(config.get_hotkey("clear_queue"), "Shift+F4")
        self.assertEqual(config.get_hotkey("toggle_notepad"), "F3")

        # Verify disk persistence of reset
        reloaded = AppConfig(config_path=self.config_path)
        self.assertEqual(reloaded.get_all_hotkeys(), DEFAULT_CONFIG["hotkeys"])

    def test_backwards_compatibility_legacy_config(self) -> None:
        """Given a legacy config file missing keys, When loaded, Then defaults are backfilled and legacy values preserved."""
        # Given: legacy config missing hotkeys, notepad_text, notepad_geometry, etc.
        legacy_data: Dict[str, Any] = {
            "auto_clear_enabled": True,
            "auto_clear_seconds": 180,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # When
        config = AppConfig(config_path=self.config_path)

        # Then: preserved existing legacy fields
        self.assertTrue(config.get("auto_clear_enabled"))
        self.assertEqual(config.get("auto_clear_seconds"), 180)

        # And populated new fields with defaults
        self.assertEqual(config.get("auto_clear_mode"), "idle")
        self.assertTrue(config.get("ignore_consecutive_duplicates"))
        self.assertEqual(config.get("notepad_text"), "")
        self.assertEqual(config.get("notepad_geometry"), "360x280+150+150")
        self.assertEqual(config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(config.get_hotkey("clear_queue"), "Shift+F4")
        self.assertEqual(config.get_hotkey("toggle_notepad"), "F3")

    def test_backwards_compatibility_partial_hotkeys(self) -> None:
        """Given a config with partial hotkeys, When loaded, Then missing hotkeys fall back to defaults."""
        # Given
        partial_data: Dict[str, Any] = {
            "hotkeys": {
                "toggle_queue": "Ctrl+Space",
            }
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(partial_data, f)

        # When
        config = AppConfig(config_path=self.config_path)

        # Then
        self.assertEqual(config.get_hotkey("toggle_queue"), "Ctrl+Space")
        self.assertEqual(config.get_hotkey("clear_queue"), "Shift+F4")
        self.assertEqual(config.get_hotkey("toggle_notepad"), "F3")

    def test_thread_safety(self) -> None:
        """Given concurrent readers and writers, When operating on AppConfig, Then operations remain consistent."""
        # Given
        config = AppConfig(config_path=self.config_path)
        errors: List[Exception] = []

        def worker(thread_idx: int) -> None:
            try:
                for i in range(50):
                    action = f"action_{thread_idx}"
                    key = f"Key_{i}"
                    config.set_hotkey(action, key)
                    val = config.get_hotkey(action)
                    if val != key:
                        raise ValueError(f"Expected {key}, got {val}")
                    all_keys = config.get_all_hotkeys()
                    if action not in all_keys:
                        raise ValueError(f"Action {action} not in all_keys")
                    config.set("notepad_text", f"Note {thread_idx}_{i}")
                    _ = config.get("notepad_text")
            except Exception as exc:
                errors.append(exc)

        # When
        threads: List[threading.Thread] = [
            threading.Thread(target=worker, args=(t,)) for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Then
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
