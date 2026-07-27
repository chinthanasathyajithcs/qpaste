"""
Unit tests for QPaste Application State Manager (F4 Master Toggle).
Ref: PRD REQ-1.1 / POC TC-1
"""
import pytest
from core.state import AppState


def test_initial_state_active():
    """Verify AppState defaults to ACTIVE (Queue Mode ON)."""
    state = AppState()
    assert state.is_active() is True


def test_toggle_state():
    """Verify toggling switches state between ACTIVE and PAUSED."""
    state = AppState()

    # Toggle ON -> OFF
    assert state.toggle() is False
    assert state.is_active() is False

    # Toggle OFF -> ON
    assert state.toggle() is True
    assert state.is_active() is True


def test_explicit_set_active():
    """Verify explicitly setting state."""
    state = AppState()
    state.set_active(False)
    assert state.is_active() is False

    state.set_active(True)
    assert state.is_active() is True
