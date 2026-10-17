"""
Validation rules for user-assigned QPaste hotkeys.
Pure functions with no UI or config dependency, so the Settings recorder and its tests
share one definition of what a savable hotkey is.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from core.hotkey_parser import HotkeyCombo, format_hotkey, is_altgr_risky, parse_hotkey

# Modifiers that make a typing key safe to bind. Shift is excluded: Shift+A is just typing.
SAFE_MODIFIERS: frozenset[str] = frozenset({"ctrl", "alt", "win"})

ESCAPE_ALONE = HotkeyCombo(frozenset(), "escape")

# Combos QPaste depends on (clipboard shortcuts) or Windows owns (window switching,
# task manager, lock). Escape alone is included because it cancels recording.
RESERVED_COMBOS: frozenset[HotkeyCombo] = frozenset({
    HotkeyCombo(frozenset({"ctrl"}), "c"),
    HotkeyCombo(frozenset({"ctrl"}), "v"),
    HotkeyCombo(frozenset({"ctrl"}), "x"),
    HotkeyCombo(frozenset({"alt"}), "f4"),
    HotkeyCombo(frozenset({"alt"}), "tab"),
    HotkeyCombo(frozenset({"ctrl"}), "escape"),
    HotkeyCombo(frozenset({"alt"}), "escape"),
    HotkeyCombo(frozenset({"ctrl", "shift"}), "escape"),
    HotkeyCombo(frozenset({"ctrl", "alt"}), "delete"),
    HotkeyCombo(frozenset({"win"}), "l"),
    ESCAPE_ALONE,
})

QUEUE_PASTE_KEY = "v"  # The Ctrl+V hook intercepts V whenever Ctrl is down, whatever else is held

ALTGR_WARNING = "Ctrl+Alt may clash with AltGr typing on some layouts"
ESCAPE_ERROR = "Esc is reserved for cancelling"
NEEDS_MODIFIER_ERROR = "Add Ctrl, Alt or Win to this key"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validate_hotkey: an error blocks saving, a warning does not."""

    error: Optional[str] = None
    warning: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _is_function_key(key: str) -> bool:
    return len(key) > 1 and key[0] == "f" and key[1:].isdigit()


def _reserved_error(combo: HotkeyCombo) -> Optional[str]:
    if combo == ESCAPE_ALONE:
        return ESCAPE_ERROR
    if combo in RESERVED_COMBOS:
        return f"{format_hotkey(combo)} is reserved"
    if "ctrl" in combo.modifiers and combo.key == QUEUE_PASTE_KEY:
        return f"{format_hotkey(combo)} would also trigger queue paste"
    return None


def _modifier_error(combo: HotkeyCombo) -> Optional[str]:
    if _is_function_key(combo.key) or combo.modifiers & SAFE_MODIFIERS:
        return None
    return NEEDS_MODIFIER_ERROR


def _duplicate_error(
    combo: HotkeyCombo,
    action: str,
    assignments: Mapping[str, str],
    labels: Mapping[str, str],
) -> Optional[str]:
    for other, raw in assignments.items():
        if other == action:
            continue
        if parse_hotkey(raw) == combo:
            return f"Already used by {labels.get(other, other.replace('_', ' ').title())}"
    return None


def validate_hotkey(
    combo: HotkeyCombo,
    action: str,
    assignments: Mapping[str, str],
    labels: Optional[Mapping[str, str]] = None,
) -> ValidationResult:
    """
    Checks whether `combo` may be saved for `action`.
    `assignments` maps every action to its stored hotkey string; `labels` maps actions to
    display names for the duplicate message. An AltGr clash is only a warning.
    """
    error = (
        _reserved_error(combo)
        or _modifier_error(combo)
        or _duplicate_error(combo, action, assignments, labels or {})
    )
    if error:
        return ValidationResult(error=error)
    return ValidationResult(warning=ALTGR_WARNING if is_altgr_risky(combo) else None)
