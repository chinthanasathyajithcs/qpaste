"""
QPaste - Sequential Clipboard Manager Application Entry Point.
Launches the Win32 Named Mutex single-instance check, global keyboard listener,
System Tray icon, Native Toast Overlay, and Visual Queue Inspector GUI.
"""
import os
import sys
import tkinter as tk
from PIL import Image

from typing import Optional

# Ensure src directory is on sys.path for robust cross-environment module resolution
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import pystray
from pystray import MenuItem as item

import time
import threading

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig
from core.listener import GlobalKeyboardListener, ShortcutHandler, NativeClipboardListener
from core.state import AppState
from core.single_instance import SingleInstance
from core.startup import is_startup_enabled, enable_startup, disable_startup
from ui.toast import NativeToastOverlay
from ui.inspector import QueueInspectorWindow


def get_asset_path(filename: str) -> str:
    """Get absolute path to asset resource, supporting PyInstaller bundles."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", filename)
    return os.path.join(src_dir, "..", "assets", filename)


def main() -> None:
    # Win32 Single-Instance Enforcement
    single_inst = SingleInstance()
    if not single_inst.acquire():
        print("[QPaste] Another instance is already running. Exiting.")
        sys.exit(0)

    # Set Windows AppUserModelID so Taskbar uses our custom app icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QPaste.ClipboardManager.1.0")
        except Exception:
            pass

    # Master Tk Root for Main Thread Event Loop
    root = tk.Tk()
    root.withdraw()

    icon_ico = get_asset_path("icon.ico")
    icon_png = get_asset_path("icon.png")
    if os.path.exists(icon_ico):
        try:
            root.iconbitmap(icon_ico)
        except Exception:
            pass
    elif os.path.exists(icon_png):
        try:
            img = tk.PhotoImage(file=icon_png)
            root.iconphoto(True, img)
        except Exception:
            pass

    config = AppConfig()
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    icon_instance = []

    # Native ToolWindow Toast Overlay
    toast_overlay = NativeToastOverlay(master=root)
    toast_overlay.start()

    def on_notify(message: str, toast_type: str = "info") -> None:
        toast_overlay.show_toast(message, toast_type)

    # Forward declaration for the update callback
    inspector: Optional[QueueInspectorWindow] = None

    def on_update():
        if inspector:
            try:
                # Tell tkinter to refresh on the main thread safely
                inspector.master.after(0, inspector.refresh)
            except Exception:
                pass

    handler = ShortcutHandler(
        state,
        queue,
        on_notify_callback=on_notify,
        on_update_callback=on_update,
    )
    listener = GlobalKeyboardListener(handler)
    listener.start()
    
    clipboard_listener = NativeClipboardListener(handler)
    clipboard_listener.start()

    # Visual Queue Inspector Window
    inspector = QueueInspectorWindow(queue, config=config, master=root)

    # Background Queue Expiration Manager Thread
    def run_expiration_manager():
        while True:
            time.sleep(1)
            try:
                if config.get("auto_clear_enabled", False):
                    timeout = config.get("auto_clear_seconds", 60)
                    purged_count = queue.purge_expired(timeout)
                    if purged_count > 0:
                        on_notify("QPaste : Cleared", "cleared")
                        on_update()
            except Exception:
                pass

    exp_thread = threading.Thread(target=run_expiration_manager, daemon=True)
    exp_thread.start()

    # --- System Tray Menu Handlers ---
    def on_toggle_queue(icon, item):
        handler.handle_f4()

    def on_clear_queue(icon, item):
        handler.handle_shift_f4()

    def on_open_inspector(icon, item):
        inspector.show()

    def on_toggle_startup(icon, item):
        if is_startup_enabled():
            disable_startup()
        else:
            enable_startup()

    def on_exit(icon, item):
        clipboard_listener.stop()
        listener.stop()
        single_inst.release()
        if icon_instance:
            icon_instance[0].stop()
        try:
            root.quit()
        except Exception:
            pass
        os._exit(0)

    # Prepare Tray Icon
    icon_path = get_asset_path("icon.png")
    if os.path.exists(icon_path):
        image = Image.open(icon_path)
    else:
        # Fallback image
        image = Image.new("RGB", (64, 64), color=(40, 180, 220))

    menu = pystray.Menu(
        item("Toggle Queue Mode (F4)", on_toggle_queue),
        item("Clear Queue (Shift+F4)", on_clear_queue),
        item("Open Queue Inspector", on_open_inspector, default=True),
        pystray.Menu.SEPARATOR,
        item("Start with Windows", on_toggle_startup, checked=lambda item: is_startup_enabled()),
        pystray.Menu.SEPARATOR,
        item("Exit", on_exit),
    )

    tray_icon = pystray.Icon("QPaste", image, "QPaste", menu)
    icon_instance.append(tray_icon)

    # Launch System Tray Icon (Detached Background Thread)
    tray_icon.run_detached()

    print("[QPaste] Application running silently in System Tray.")

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        clipboard_listener.stop()
        listener.stop()
        single_inst.release()
        os._exit(0)


if __name__ == "__main__":
    main()
