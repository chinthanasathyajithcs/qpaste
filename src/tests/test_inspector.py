"""
Unit tests for QueueInspectorWindow HUD GUI.
Tests queue operations, settings tab integration, tab switching, and hotkey callback forwarding.
Gracefully mocks Tkinter for headless environments.
"""
from __future__ import annotations

import os
import sys
import unittest
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig
import ui.inspector as inspector_mod
from ui.inspector import QueueInspectorWindow


class MockWidget:
    """Mock Tkinter widget supporting config, pack, and bindings."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._config: Dict[str, Any] = dict(kwargs)
        self._binds: Dict[str, Any] = {}
        self._items: list[str] = []
        self._selection: tuple[int, ...] = ()

    def pack(self, *args: Any, **kwargs: Any) -> None:
        pass

    def pack_forget(self, *args: Any, **kwargs: Any) -> None:
        pass

    def place(self, *args: Any, **kwargs: Any) -> None:
        pass

    def place_forget(self, *args: Any, **kwargs: Any) -> None:
        pass

    def config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def configure(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def bind(self, event: str, handler: Any) -> None:
        self._binds[event] = handler

    def set(self, *args: Any) -> None:
        pass

    def yview(self, *args: Any) -> None:
        pass

    def protocol(self, _name: str, _handler: Any) -> None:
        pass

    def title(self, _t: str) -> None:
        pass

    def geometry(self, _g: str = "") -> str:
        return _g

    def minsize(self, _w: int, _h: int) -> None:
        pass

    def deiconify(self) -> None:
        pass

    def lift(self) -> None:
        pass

    def withdraw(self) -> None:
        pass

    def focus_force(self) -> None:
        pass

    def delete(self, _start: Any, _end: Any = None) -> None:
        self._items.clear()

    def insert(self, _idx: Any, item: str) -> None:
        self._items.append(item)

    def curselection(self) -> tuple[int, ...]:
        return self._selection

    def selection_set(self, idx: int) -> None:
        self._selection = (idx,)


class TestQueueInspector(unittest.TestCase):
    """Test suite for QueueInspectorWindow and queue manipulation."""

    def setUp(self) -> None:
        self.queue = ClipboardQueue()
        self.queue.push("Snippet 1")
        self.queue.push("Snippet 2")
        self.queue.push("Snippet 3")

        self.mock_config = MagicMock(spec=AppConfig)
        self.hotkeys_reloaded = False

        # Mock Tkinter module
        self.mock_tk = MagicMock()
        self.mock_tk.Tk = MockWidget
        self.mock_tk.Toplevel = MockWidget
        self.mock_tk.Frame = MockWidget
        self.mock_tk.Label = MockWidget
        self.mock_tk.Button = MockWidget
        self.mock_tk.Listbox = MockWidget
        self.mock_tk.Scrollbar = MockWidget
        self.mock_tk.Checkbutton = MockWidget
        self.mock_tk.Entry = MockWidget
        self.mock_tk.OptionMenu = MockWidget
        self.mock_tk.BooleanVar = MagicMock()
        self.mock_tk.StringVar = MagicMock()

        self.mock_tk.BOTH = "both"
        self.mock_tk.X = "x"
        self.mock_tk.Y = "y"
        self.mock_tk.LEFT = "left"
        self.mock_tk.RIGHT = "right"
        self.mock_tk.FLAT = "flat"
        self.mock_tk.SOLID = "solid"
        self.mock_tk.SINGLE = "single"
        self.mock_tk.END = "end"
        self.mock_tk.CENTER = "center"

        self.orig_tk = inspector_mod.tk
        inspector_mod.tk = self.mock_tk

        self.inspector = QueueInspectorWindow(
            queue=self.queue,
            config=self.mock_config,
            on_hotkeys_changed=self._on_hotkeys_changed,
        )

    def tearDown(self) -> None:
        inspector_mod.tk = self.orig_tk

    def _on_hotkeys_changed(self) -> None:
        self.hotkeys_reloaded = True

    def test_queue_manipulation_methods(self) -> None:
        self.assertEqual(len(self.queue), 3)

        # Test move_item
        self.queue.move_item(1, 0)
        items = self.queue.get_items()
        self.assertEqual(items[0], "Snippet 2")
        self.assertEqual(items[1], "Snippet 1")

        # Test delete
        self.queue.remove_at(1)
        items = self.queue.get_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0], "Snippet 2")
        self.assertEqual(items[1], "Snippet 3")

        # Test clear
        self.queue.clear()
        self.assertEqual(len(self.queue), 0)

    def test_get_item_by_index(self) -> None:
        self.assertEqual(self.queue.get_item(0), "Snippet 1")
        self.assertEqual(self.queue.get_item(2), "Snippet 3")
        self.assertIsNone(self.queue.get_item(99))

    def test_promote_to_front(self) -> None:
        result = self.queue.promote_to_front(2)
        self.assertTrue(result)
        items = self.queue.get_items()
        self.assertEqual(items[0], "Snippet 3")
        self.assertEqual(items[1], "Snippet 1")
        self.assertEqual(items[2], "Snippet 2")

    def test_promote_invalid_index(self) -> None:
        self.assertFalse(self.queue.promote_to_front(-1))
        self.assertFalse(self.queue.promote_to_front(10))

    def test_inspector_gui_build_and_settings_tab(self) -> None:
        self.inspector._build_gui()
        self.assertIsNotNone(self.inspector.root)
        self.assertIsNotNone(self.inspector.settings_tab)
        self.assertIsNotNone(self.inspector.listbox)

    def test_tab_switching(self) -> None:
        self.inspector._build_gui()

        # Switch to settings tab
        self.inspector._switch_to_settings_tab()
        self.assertEqual(self.inspector.settings_tab_btn._config.get("fg"), inspector_mod.ACCENT_PRIMARY)

        # Switch back to queue tab
        self.inspector._switch_to_queue_tab()
        self.assertEqual(self.inspector.queue_tab_btn._config.get("fg"), inspector_mod.ACCENT_PRIMARY)

    def test_on_hotkeys_changed_forwarding(self) -> None:
        self.inspector._on_hotkeys_changed()
        self.assertTrue(self.hotkeys_reloaded)

    def test_refresh_and_delete_selected(self) -> None:
        self.inspector._build_gui()
        self.inspector.refresh()
        self.assertEqual(len(self.inspector.listbox._items), 3)

        # Select item 0 and delete
        self.inspector.listbox.selection_set(0)
        self.inspector.delete_selected()
        self.assertEqual(len(self.queue), 2)

    def test_clear_all_gui(self) -> None:
        self.inspector._build_gui()
        self.inspector.clear_all()
        self.assertEqual(len(self.queue), 0)


if __name__ == "__main__":
    unittest.main()
