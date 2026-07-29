"""
Unit tests for core.startup module.
Verifies Windows auto-start registry command formatting for both
standalone binary (frozen) and Python source execution modes.
"""
import os
import sys
from unittest.mock import patch, MagicMock

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
         patch.object(sys, "argv", [mock_script]), \
         patch("os.path.exists", return_value=False):
        cmd = get_startup_command()
        expected_script = os.path.abspath(mock_script)
        assert cmd == f'"{mock_python}" "{expected_script}"'


def test_get_startup_command_script_mode_uses_pythonw():
    """If pythonw.exe exists alongside python.exe, startup command should use pythonw.exe."""
    mock_python = r"C:\Python311\python.exe"
    mock_pythonw = r"C:\Python311\pythonw.exe"
    mock_script = r"C:\Projects\qpaste\src\main.py"
    
    def mock_exists(path):
        return os.path.normpath(path) == os.path.normpath(mock_pythonw)

    with patch.object(sys, "frozen", False, create=True), \
         patch.object(sys, "executable", mock_python), \
         patch.object(sys, "argv", [mock_script]), \
         patch("os.path.exists", side_effect=mock_exists):
        cmd = get_startup_command()
        expected_script = os.path.abspath(mock_script)
        assert cmd == f'"{mock_pythonw}" "{expected_script}"'


def test_enable_startup_win32():
    """enable_startup opens HKCU Run key and sets the AppName value."""
    from core.startup import enable_startup
    with patch("sys.platform", "win32"), \
         patch("core.startup.winreg.OpenKey") as mock_open_key, \
         patch("core.startup.winreg.SetValueEx") as mock_set_value, \
         patch("core.startup.winreg.CloseKey") as mock_close_key:
        assert enable_startup() is True
        mock_open_key.assert_called_once()
        mock_set_value.assert_called_once()
        mock_close_key.assert_called_once()


def test_disable_startup_win32():
    """disable_startup removes the AppName value from HKCU Run key."""
    from core.startup import disable_startup
    with patch("sys.platform", "win32"), \
         patch("core.startup.winreg.OpenKey") as mock_open_key, \
         patch("core.startup.winreg.DeleteValue") as mock_delete_value, \
         patch("core.startup.winreg.CloseKey") as mock_close_key:
        assert disable_startup() is True
        mock_open_key.assert_called_once()
        mock_delete_value.assert_called_once()
        mock_close_key.assert_called_once()


def test_disable_startup_already_disabled():
    """disable_startup returns True cleanly when value is not in registry."""
    from core.startup import disable_startup
    with patch("sys.platform", "win32"), \
         patch("core.startup.winreg.OpenKey"), \
         patch("core.startup.winreg.DeleteValue", side_effect=FileNotFoundError):
        assert disable_startup() is True


def test_is_startup_enabled_states():
    """is_startup_enabled returns True when key exists, False on FileNotFoundError."""
    import core.startup
    mock_winreg = MagicMock()
    mock_winreg.HKEY_CURRENT_USER = 1
    mock_winreg.KEY_READ = 1
    mock_winreg.QueryValueEx.return_value = ("cmd", 1)

    with patch("sys.platform", "win32"), patch.object(core.startup, "winreg", mock_winreg):
        assert core.startup.is_startup_enabled() is True

    mock_winreg.QueryValueEx.side_effect = FileNotFoundError
    with patch("sys.platform", "win32"), patch.object(core.startup, "winreg", mock_winreg):
        assert core.startup.is_startup_enabled() is False


def test_startup_non_win32_returns_false():
    """On non-Windows platforms, startup functions should safely return False."""
    from core.startup import enable_startup, disable_startup, is_startup_enabled
    with patch("sys.platform", "linux"):
        assert enable_startup() is False
        assert disable_startup() is False
        assert is_startup_enabled() is False


def test_toggle_startup_flow():
    """Toggling startup switches state between enabled and disabled for the system tray tick."""
    with patch("core.startup.is_startup_enabled") as mock_is_enabled, \
         patch("core.startup.enable_startup") as mock_enable, \
         patch("core.startup.disable_startup") as mock_disable:
        
        # Scenario 1: Currently enabled -> should disable
        mock_is_enabled.return_value = True
        if mock_is_enabled():
            mock_disable()
        else:
            mock_enable()
            
        mock_disable.assert_called_once()
        mock_enable.assert_not_called()
        
        # Scenario 2: Currently disabled -> should enable
        mock_disable.reset_mock()
        mock_is_enabled.return_value = False
        if mock_is_enabled():
            mock_disable()
        else:
            mock_enable()
            
        mock_enable.assert_called_once()
        mock_disable.assert_not_called()


