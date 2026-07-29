import os
import sys
import winreg

APP_NAME = "QPaste"

def is_running_as_exe() -> bool:
    """Check if the app is bundled as a PyInstaller executable."""
    return getattr(sys, 'frozen', False)

def get_executable_path() -> str:
    """Get the path to the executable or python script."""
    if is_running_as_exe():
        return sys.executable
    return os.path.abspath(sys.argv[0])

def get_startup_command() -> str:
    """Get formatted command string for Windows startup registry key."""
    if is_running_as_exe():
        return f'"{sys.executable}"'
    script_path = os.path.abspath(sys.argv[0])
    return f'"{sys.executable}" "{script_path}"'

def enable_startup() -> bool:
    """Add the application to the Windows startup registry."""
    if sys.platform != "win32":
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE
        )
        cmd = get_startup_command()
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Failed to enable startup: {e}")
        return False

def disable_startup() -> bool:
    """Remove the application from the Windows startup registry."""
    if sys.platform != "win32":
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_WRITE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        print(f"Failed to disable startup: {e}")
        return False

def is_startup_enabled() -> bool:
    """Check if the application is in the Windows startup registry."""
    if sys.platform != "win32":
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False
