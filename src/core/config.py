"""
Thread-safe persistent configuration manager for QPaste settings.
"""

import copy
import json
import os
import sys
import threading
from typing import Any, Dict, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "auto_clear_enabled": False,
    "auto_clear_seconds": 60,
    "auto_clear_mode": "idle",  # "idle" or "ttl"
    "ignore_consecutive_duplicates": True,
    "debounce_ms": 200.0,
    "duplicate_window_sec": 1.0,
    "hotkeys": {
        "toggle_queue": "F4",
        "clear_queue": "Shift+F4",
        "toggle_notepad": "F3",
    },
    "notepad_text": "",
    "notepad_geometry": "360x280+150+150",
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges override dictionary into base dictionary."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def get_config_path() -> str:
    """Returns absolute path to config.json, ensuring directory exists."""
    if sys.platform == "win32":
        appdata_dir = os.environ.get("APPDATA", "")
        if appdata_dir:
            config_dir = os.path.join(appdata_dir, "QPaste")
            os.makedirs(config_dir, exist_ok=True)
            return os.path.join(config_dir, "config.json")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "..", "config.json")


class AppConfig:
    """Thread-safe persistent settings manager."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config_path: str = config_path or get_config_path()
        self._lock: threading.Lock = threading.Lock()
        self._settings: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Loads settings from JSON file, falling back to defaults if missing/corrupt."""
        with self._lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self._settings = _deep_merge(DEFAULT_CONFIG, data)
                except Exception as e:
                    print(f"[AppConfig] Error loading config ({e}), using defaults.")
            else:
                self._save_unlocked()

    def save(self) -> None:
        """Saves current settings to JSON file."""
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self) -> None:
        try:
            parent_dir = os.path.dirname(self.config_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"[AppConfig] Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Gets a configuration setting."""
        with self._lock:
            if key in self._settings:
                return self._settings[key]
            if default is not None:
                return default
            return DEFAULT_CONFIG.get(key)

    def set(self, key: str, value: Any) -> None:
        """Sets a configuration setting and persists to file."""
        with self._lock:
            self._settings[key] = value
            self._save_unlocked()

    def get_hotkey(self, action: str, default: Optional[str] = None) -> str:
        """Gets hotkey string for a given action."""
        with self._lock:
            hotkeys = self._settings.get("hotkeys")
            if isinstance(hotkeys, dict) and action in hotkeys:
                return str(hotkeys[action])
            if default is not None:
                return default
            default_hotkeys = DEFAULT_CONFIG.get("hotkeys", {})
            if isinstance(default_hotkeys, dict) and action in default_hotkeys:
                return str(default_hotkeys[action])
            return ""

    def set_hotkey(self, action: str, hotkey: str) -> None:
        """Sets hotkey string for a given action and persists to file."""
        with self._lock:
            hotkeys = self._settings.get("hotkeys")
            if not isinstance(hotkeys, dict):
                hotkeys = copy.deepcopy(DEFAULT_CONFIG.get("hotkeys", {}))
                self._settings["hotkeys"] = hotkeys
            hotkeys[action] = hotkey
            self._save_unlocked()

    def get_all_hotkeys(self) -> Dict[str, str]:
        """Returns a copy of all hotkeys with defaults populated."""
        with self._lock:
            res = dict(DEFAULT_CONFIG.get("hotkeys", {}))
            current = self._settings.get("hotkeys")
            if isinstance(current, dict):
                res.update({str(k): str(v) for k, v in current.items()})
            return res

    def reset_hotkeys(self) -> None:
        """Resets hotkeys configuration to default values and persists to file."""
        with self._lock:
            self._settings["hotkeys"] = copy.deepcopy(DEFAULT_CONFIG.get("hotkeys", {}))
            self._save_unlocked()
