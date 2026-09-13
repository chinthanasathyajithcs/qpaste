"""
Pure Python Hotkey Parser and Combo Matcher for QPaste.
Normalized keyboard shortcut parser, string formatter, and event matcher.
Compatible with pynput Key/KeyCode and standard string representations.
"""

from dataclasses import dataclass
import re
from typing import Any, Optional, Set

MODIFIER_ORDER: tuple[str, ...] = ("ctrl", "shift", "alt", "win")
MODIFIER_DISPLAY: dict[str, str] = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win"}

MODIFIER_ALIASES: dict[str, str] = {
    "ctrl": "ctrl", "control": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
    "alt": "alt", "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "menu": "alt", "option": "alt", "opt": "alt",
    "win": "win", "cmd": "win", "cmd_l": "win", "cmd_r": "win",
    "super": "win", "windows": "win", "command": "win", "meta": "win",
}

KEY_ALIASES: dict[str, str] = {
    "esc": "escape", "escape": "escape", "return": "enter", "enter": "enter",
    "space": "space", "spacebar": "space", "tab": "tab", "backspace": "backspace", "bksp": "backspace",
    "delete": "delete", "del": "delete", "insert": "insert", "ins": "insert",
    "home": "home", "end": "end", "pageup": "pageup", "page_up": "pageup", "pgup": "pageup",
    "pagedown": "pagedown", "page_down": "pagedown", "pgdn": "pagedown",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "capslock": "capslock", "caps_lock": "capslock", "printscreen": "printscreen",
    "print_screen": "printscreen", "prtsc": "printscreen", "pause": "pause",
    "scrolllock": "scrolllock", "scroll_lock": "scrolllock",
}

KEY_DISPLAY_MAP: dict[str, str] = {
    "escape": "Escape", "enter": "Enter", "space": "Space", "tab": "Tab",
    "backspace": "Backspace", "delete": "Delete", "insert": "Insert",
    "home": "Home", "end": "End", "pageup": "PageUp", "pagedown": "PageDown",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "capslock": "CapsLock", "printscreen": "PrintScreen", "pause": "Pause", "scrolllock": "ScrollLock",
}

VK_KEY_MAP: dict[int, str] = {
    0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x1B: "escape", 0x20: "space",
    0x21: "pageup", 0x22: "pagedown", 0x23: "end", 0x24: "home", 0x25: "left",
    0x26: "up", 0x27: "right", 0x28: "down", 0x2D: "insert", 0x2E: "delete",
}

VK_MOD_MAP: dict[int, str] = {
    0x10: "shift", 0xA0: "shift", 0xA1: "shift",
    0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
    0x12: "alt", 0xA4: "alt", 0xA5: "alt",
    0x5B: "win", 0x5C: "win",
}

RE_FUNCTION_KEY = re.compile(r"^f([1-9]|1[0-9]|2[0-4])$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class HotkeyCombo:
    modifiers: frozenset[str]
    key: str


def _normalize_key_token(token: str) -> Optional[str]:
    cleaned = token.lower().strip()
    if not cleaned or cleaned in MODIFIER_ALIASES:
        return None
    if cleaned in KEY_ALIASES:
        return KEY_ALIASES[cleaned]
    if RE_FUNCTION_KEY.match(cleaned) or len(cleaned) == 1:
        return cleaned
    return None


def _normalize_vk(vk: int) -> Optional[str]:
    if vk in VK_KEY_MAP:
        return VK_KEY_MAP[vk]
    if 0x70 <= vk <= 0x87:
        return f"f{vk - 0x70 + 1}"
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    return None


def _extract_modifier_name(key: Any) -> Optional[str]:
    if key is None:
        return None
    if isinstance(key, str):
        cleaned = key.lower().strip()
        return MODIFIER_ALIASES.get(cleaned[4:] if cleaned.startswith("key.") else cleaned)
    if isinstance(key, int):
        return VK_MOD_MAP.get(key)
    name = getattr(key, "name", None)
    if isinstance(name, str):
        cleaned = name.lower().strip()
        if cleaned in MODIFIER_ALIASES:
            return MODIFIER_ALIASES[cleaned]
    vk = getattr(key, "vk", None)
    if isinstance(vk, int) and vk in VK_MOD_MAP:
        return VK_MOD_MAP[vk]
    s = str(key).lower().strip()
    return MODIFIER_ALIASES.get(s[4:] if s.startswith("key.") else s)


def _extract_key_name(key: Any) -> Optional[str]:
    if key is None:
        return None
    if isinstance(key, str):
        cleaned = key.lower().strip()
        return _normalize_key_token(cleaned[4:] if cleaned.startswith("key.") else cleaned)
    if isinstance(key, int):
        return _normalize_vk(key)

    char = getattr(key, "char", None)
    if isinstance(char, str) and char:
        if len(char) == 1 and 1 <= ord(char) <= 26:
            return chr(ord(char) + 96)
        token = _normalize_key_token(char)
        if token:
            return token

    name = getattr(key, "name", None)
    if isinstance(name, str):
        token = _normalize_key_token(name)
        if token:
            return token

    vk = getattr(key, "vk", None)
    if isinstance(vk, int):
        token = _normalize_vk(vk)
        if token:
            return token

    s = str(key).lower().strip()
    if s.startswith("key."):
        s = s[4:]
    elif s.startswith("'") and s.endswith("'") and len(s) >= 3:
        s = s[1:-1]
    return _normalize_key_token(s)


def parse_hotkey(hotkey_str: str) -> Optional[HotkeyCombo]:
    """
    Parses a hotkey string into a normalized HotkeyCombo.
    Returns None on empty or unparsable string without raising exceptions.
    """
    if not isinstance(hotkey_str, str):
        return None
    s = hotkey_str.strip()
    if not s:
        return None

    if s.endswith("++"):
        prefix = s[:-2].strip()
        parts = [p.strip() for p in prefix.split("+") if p.strip()] + ["+"]
    else:
        parts = [p.strip() for p in s.split("+") if p.strip()]

    if not parts:
        return None

    modifiers: set[str] = set()
    keys: list[str] = []

    for part in parts:
        part_lower = part.lower()
        if part_lower in MODIFIER_ALIASES:
            modifiers.add(MODIFIER_ALIASES[part_lower])
        else:
            key = _normalize_key_token(part)
            if key is None:
                return None
            keys.append(key)

    if len(keys) != 1:
        return None

    return HotkeyCombo(modifiers=frozenset(modifiers), key=keys[0])


def format_hotkey(combo: HotkeyCombo) -> str:
    """
    Formats a HotkeyCombo into a standard capitalized string (e.g. 'Ctrl+Shift+N', 'F4').
    """
    if not isinstance(combo, HotkeyCombo):
        raise TypeError(f"Expected HotkeyCombo, got {type(combo).__name__}")

    parts = [MODIFIER_DISPLAY.get(m, m.capitalize()) for m in MODIFIER_ORDER if m in combo.modifiers]
    parts.extend(MODIFIER_DISPLAY.get(m, m.capitalize()) for m in sorted(combo.modifiers) if m not in MODIFIER_ORDER)

    key = combo.key
    if key in KEY_DISPLAY_MAP:
        parts.append(KEY_DISPLAY_MAP[key])
    elif RE_FUNCTION_KEY.match(key) or len(key) == 1:
        parts.append(key.upper())
    else:
        parts.append(key.capitalize())

    return "+".join(parts)


def match_hotkey(combo: HotkeyCombo, pressed_keys: Set[Any], current_key: Any) -> bool:
    """
    Tests whether the current key and currently pressed keys match the HotkeyCombo.
    Compatible with pynput.keyboard.Key, KeyCode, strings, and virtual key codes.
    """
    if not isinstance(combo, HotkeyCombo):
        return False

    if current_key is not None:
        if _extract_key_name(current_key) != combo.key:
            return False
    else:
        if not any(_extract_key_name(k) == combo.key for k in pressed_keys):
            return False

    active_modifiers: set[str] = set()
    for k in pressed_keys:
        mod = _extract_modifier_name(k)
        if mod is not None:
            active_modifiers.add(mod)

    return active_modifiers == combo.modifiers
