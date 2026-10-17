"""
Shared Tkinter test doubles for headless UI tests.
MockWidget records constructor options, configuration changes, event bindings and
focus/destroy calls, and gives each widget a Tk-style path so containment checks work.
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

_ids = itertools.count(1)


class MockVar:
    """Mock Tkinter StringVar and BooleanVar."""

    def __init__(self, value: Any = None) -> None:
        self._value = value

    def get(self) -> Any:
        return self._value

    def set(self, val: Any) -> None:
        self._value = val


class MockWidget:
    """Mock Tkinter widget supporting config, pack, bindings, focus and destroy."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.master: Optional[MockWidget] = args[0] if args and isinstance(args[0], MockWidget) else None
        self._config: Dict[str, Any] = dict(kwargs)
        self._binds: Dict[str, Any] = {}
        self._menu: Optional[MockWidget] = None
        self.children: List[MockWidget] = []
        self.destroyed = False
        self.focused = False
        prefix = f"{self.master}." if self.master is not None else ""
        self._path = f"{prefix}w{next(_ids)}"
        if self.master is not None:
            self.master.children.append(self)

    def __str__(self) -> str:
        return self._path

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

    def bind(self, event: str, handler: Any, add: Any = None) -> None:
        self._binds[event] = handler

    def focus_set(self) -> None:
        self.focused = True

    def destroy(self) -> None:
        self.destroyed = True
        if self.master is not None and self in self.master.children:
            self.master.children.remove(self)

    def set(self, *args: Any) -> None:
        pass

    def yview(self, *args: Any) -> None:
        pass

    def click(self) -> None:
        """Invokes a Button's command."""
        self._config["command"]()


def make_mock_tk() -> MagicMock:
    """A stand-in for the tkinter module with the widget classes and constants the UI uses."""
    mock_tk = MagicMock()
    mock_tk.Frame = MockWidget
    mock_tk.Label = MockWidget
    mock_tk.Button = MockWidget
    mock_tk.Checkbutton = MockWidget
    mock_tk.Entry = MockWidget
    mock_tk.OptionMenu = MockWidget
    mock_tk.Scrollbar = MockWidget
    mock_tk.BooleanVar = lambda value=False: MockVar(value)
    mock_tk.StringVar = lambda value="": MockVar(value)
    mock_tk.BOTH = "both"
    mock_tk.X = "x"
    mock_tk.Y = "y"
    mock_tk.LEFT = "left"
    mock_tk.RIGHT = "right"
    mock_tk.FLAT = "flat"
    mock_tk.W = "w"
    return mock_tk


def key_event(keycode: int, widget: Any = None) -> Any:
    """A minimal Tk key event: Tk reports the Windows virtual-key code as keycode."""
    event = MagicMock()
    event.keycode = keycode
    event.widget = widget
    return event
