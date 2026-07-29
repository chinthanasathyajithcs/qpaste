"""
Unit tests for core.startup module.
Verifies Windows auto-start registry command formatting for both
standalone binary (frozen) and Python source execution modes.
"""
import os
import sys
from unittest.mock import patch

from core.startup import get_startup_command, is_running_as_exe


def test_is_running_as_exe_default():
    """By default in test environment, sys.frozen should be False or unset."""
    assert is_running_as_exe() is False


def test_get_startup_command_frozen():
    """In frozen PyInstaller mode, command should be quoted executable path only."""
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", r"C:\Program Files\QPaste\qpaste.exe"):
        cmd = get_startup_command()
        assert cmd == r'"C:\Program Files\QPaste\qpaste.exe"'


def test_get_startup_command_script_mode():
    """In Python source script mode, command should include python executable AND script path."""
    mock_python = r"C:\Python311\python.exe"
    mock_script = r"C:\Projects\qpaste\src\main.py"
    
    with patch.object(sys, "frozen", False, create=True), \
         patch.object(sys, "executable", mock_python), \
         patch.object(sys, "argv", [mock_script]):
        cmd = get_startup_command()
        expected_script = os.path.abspath(mock_script)
        assert cmd == f'"{mock_python}" "{expected_script}"'
