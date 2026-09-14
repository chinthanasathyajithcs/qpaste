"""
Unit tests for SettingsTab GUI component.
Tests Auto-Clear controls, Hotkey customization, validation, reset defaults, and callbacks.
Gracefully mocks Tkinter for headless environments.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.config import DEFAULT_CONFIG, AppConfig
import ui.settings_tab as settings_mod
from ui.settings_tab import SettingsTab, DURATION_OPTIONS, HOTKEY_ACTIONS


class MockVar:
    """Mock Tkinter StringVar and BooleanVar."""

    def __init__(self, value: Any = None) -> None:
        self._value = value

    def get(self) -> Any:
        return self._value

    def set(self, val: Any) -> None:
        self._value = val


class MockWidget:
    """Mock Tkinter widget supporting config, pack, and event bindings."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._config: Dict[str, Any] = dict(kwargs)
        self._binds: Dict[str, Any] = {}
        self._menu: Optional[MockWidget] = None

    def pack(self, *args: Any, **kwargs: Any) -> None:
        pass

    def pack_forget(self, *args: Any, **kwargs: Any) -> None:
        pass

    def config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def configure(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def __getitem__(self, item: str) -> Any:
        if item == "menu":
            if self._menu is None:
                self._menu = MockWidget()
            return self._menu
        return self._config.get(item, MagicMock())

    def bind(self, event: str, handler: Any) -> None:
        self._binds[event] = handler

    def set(self, *args: Any) -> None:
        pass

    def yview(self, *args: Any) -> None:
        pass


class TestSettingsTab(unittest.TestCase):
    """Test suite for SettingsTab component."""

    def setUp(self) -> None:
        self.temp_dir: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        self.config_path: str = os.path.join(self.temp_dir.name, "config.json")
        self.config = AppConfig(config_path=self.config_path)

        # Mock Tkinter module
        self.mock_tk = MagicMock()
        self.mock_tk.Frame = MockWidget
        self.mock_tk.Label = MockWidget
        self.mock_tk.Button = MockWidget
        self.mock_tk.Checkbutton = MockWidget
        self.mock_tk.Entry = MockWidget
        self.mock_tk.OptionMenu = MockWidget
        self.mock_tk.Scrollbar = MockWidget
        self.mock_tk.BooleanVar = lambda value=False: MockVar(value)
        self.mock_tk.StringVar = lambda value="": MockVar(value)

        self.mock_tk.BOTH = "both"
        self.mock_tk.X = "x"
        self.mock_tk.Y = "y"
        self.mock_tk.LEFT = "left"
        self.mock_tk.RIGHT = "right"
        self.mock_tk.FLAT = "flat"
        self.mock_tk.W = "w"

        self.orig_tk = settings_mod.tk
        settings_mod.tk = self.mock_tk

        self.parent_mock = MockWidget()
        self.hotkeys_changed_called = False

    def tearDown(self) -> None:
        settings_mod.tk = self.orig_tk
        self.temp_dir.cleanup()

    def _on_hotkeys_changed(self) -> None:
        self.hotkeys_changed_called = True

    def test_initialization_defaults_from_config(self) -> None:
        """Given a fresh AppConfig, SettingsTab loads default values for auto-clear and hotkeys."""
        tab = SettingsTab(
            self.parent_mock,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )

        self.assertFalse(tab.auto_clear_var.get())
        self.assertEqual(tab.duration_var.get(), "1 Minute")

        self.assertEqual(tab.hotkey_vars["toggle_queue"].get(), "F4")
        self.assertEqual(tab.hotkey_vars["clear_queue"].get(), "Shift+F4")
        self.assertEqual(tab.hotkey_vars["toggle_notepad"].get(), "F3")

    def test_auto_clear_settings_change_persists_to_config(self) -> None:
        """When auto-clear checkbox or duration changes, AppConfig is updated."""
        tab = SettingsTab(
            self.parent_mock,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )

        tab.auto_clear_var.set(True)
        tab.duration_var.set("5 Minutes")
        tab._on_auto_clear_changed()

        self.assertTrue(self.config.get("auto_clear_enabled"))
        self.assertEqual(self.config.get("auto_clear_seconds"), 300)
        self.assertEqual(self.config.get("auto_clear_mode"), "idle")

        # Verify disk persistence
        reloaded = AppConfig(config_path=self.config_path)
        self.assertTrue(reloaded.get("auto_clear_enabled"))
        self.assertEqual(reloaded.get("auto_clear_seconds"), 300)
        self.assertEqual(reloaded.get("auto_clear_mode"), "idle")

    def test_valid_hotkey_editing_persists_and_triggers_callback(self) -> None:
        """When a valid hotkey combo is entered, it saves to config and invokes on_hotkeys_changed."""
        tab = SettingsTab(
            self.parent_mock,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )

        tab.hotkey_vars["toggle_queue"].set("Ctrl+Alt+Q")
        result = tab._on_hotkey_edited("toggle_queue")

        self.assertTrue(result)
        self.assertTrue(self.hotkeys_changed_called)
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "Ctrl+Alt+Q")
        self.assertEqual(tab.error_label._config.get("text"), "")

    def test_invalid_hotkey_editing_shows_error_and_does_not_persist(self) -> None:
        """When an invalid hotkey is entered, error feedback is shown and config is not updated."""
        self.config.set_hotkey("toggle_queue", "F4")
        tab = SettingsTab(
            self.parent_mock,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )

        tab.hotkey_vars["toggle_queue"].set("InvalidKeyComboXYZ")
        result = tab._on_hotkey_edited("toggle_queue")

        self.assertFalse(result)
        self.assertFalse(self.hotkeys_changed_called)
        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        error_text = tab.error_label._config.get("text", "")
        self.assertIn("Invalid combo", error_text)

    def test_reset_defaults_restores_all_hotkeys_and_triggers_callback(self) -> None:
        """When reset_defaults is clicked, hotkeys revert to F4, Shift+F4, F3 and callback is called."""
        self.config.set_hotkey("toggle_queue", "Ctrl+Alt+1")
        self.config.set_hotkey("clear_queue", "Ctrl+Alt+2")
        self.config.set_hotkey("toggle_notepad", "Ctrl+Alt+3")

        tab = SettingsTab(
            self.parent_mock,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )
        self.hotkeys_changed_called = False

        tab.reset_defaults()

        self.assertTrue(self.hotkeys_changed_called)
        self.assertEqual(tab.hotkey_vars["toggle_queue"].get(), "F4")
        self.assertEqual(tab.hotkey_vars["clear_queue"].get(), "Shift+F4")
        self.assertEqual(tab.hotkey_vars["toggle_notepad"].get(), "F3")

        self.assertEqual(self.config.get_hotkey("toggle_queue"), "F4")
        self.assertEqual(self.config.get_hotkey("clear_queue"), "Shift+F4")
        self.assertEqual(self.config.get_hotkey("toggle_notepad"), "F3")
        self.assertEqual(tab.error_label._config.get("text"), "")

    def test_safe_fallbacks_when_tk_is_none(self) -> None:
        """When tk is None (headless without mock), SettingsTab initializes safely."""
        settings_mod.tk = None
        tab = SettingsTab(
            self.parent_mock,
            config=self.config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )
        self.assertIsNotNone(tab.config)
        tab.reset_defaults()
        self.assertTrue(self.hotkeys_changed_called)


if __name__ == "__main__":
    unittest.main()
