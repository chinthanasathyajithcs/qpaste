"""
Thread-safe persistent configuration manager for QPaste settings.
"""
import json
import os
import sys
import threading
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "auto_clear_enabled": False,
    "auto_clear_seconds": 60,
}


def get_config_path() -> str:
    """Returns absolute path to config.json, ensuring directory exists."""
    # Place config.json in user's AppData directory or root project directory
    if sys.platform == "win32":
        appdata_dir = os.environ.get("APPDATA", "")
        if appdata_dir:
            config_dir = os.path.join(appdata_dir, "QPaste")
            os.makedirs(config_dir, exist_ok=True)
            return os.path.join(config_dir, "config.json")

    # Fallback to current working directory or src parent
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "..", "config.json")


class AppConfig:
    """Thread-safe persistent settings manager."""

    def __init__(self, config_path: str = None) -> None:
        self.config_path: str = config_path or get_config_path()
        self._lock: threading.Lock = threading.Lock()
        self._settings: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Loads settings from JSON file, falling back to defaults if missing/corrupt."""
        with self._lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self._settings.update(data)
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
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"[AppConfig] Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Gets a configuration setting."""
        with self._lock:
            return self._settings.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any) -> None:
        """Sets a configuration setting and persists to file."""
        with self._lock:
            self._settings[key] = value
            self._save_unlocked()
