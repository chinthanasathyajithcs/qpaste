"""
Win32 Named Mutex implementation for single-instance application enforcement.
Prevents multiple instances of QPaste from running simultaneously.
"""
import atexit
import ctypes
import sys

MUTEX_NAME = "Local\\QPaste_SingleInstance_Mutex"
ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, mutex_name: str = MUTEX_NAME) -> None:
        self.mutex_name = mutex_name
        self.mutex = None

    def acquire(self) -> bool:
        """
        Attempts to create/acquire the named Win32 mutex.
        Returns True if this is the single running instance.
        Returns False if another instance is already running.

        Registers an atexit handler so the mutex is released even if
        the process exits unexpectedly (KeyboardInterrupt, sys.exit, etc.).
        """
        if sys.platform != "win32":
            return True

        kernel32 = ctypes.windll.kernel32
        self.mutex = kernel32.CreateMutexW(None, False, self.mutex_name)
        last_error = kernel32.GetLastError()

        if last_error == ERROR_ALREADY_EXISTS:
            if self.mutex:
                kernel32.CloseHandle(self.mutex)
                self.mutex = None
            return False

        # Guarantee cleanup on any normal exit path
        atexit.register(self.release)
        return True

    def release(self) -> None:
        """Release and close the Win32 mutex handle."""
        if sys.platform == "win32" and self.mutex:
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(self.mutex)
            kernel32.CloseHandle(self.mutex)
            self.mutex = None
