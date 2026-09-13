"""
QPaste - Sequential Clipboard Manager Application Entry Point.
Launches the Win32 Named Mutex single-instance check, global keyboard listener,
System Tray icon, Native Toast Overlay, and Visual Queue Inspector GUI.
"""
import os
import sys
try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]
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
from ui.notepad import QuickNotepadHUD


def get_asset_path(filename: str) -> str:
    """Get absolute path to asset resource, supporting PyInstaller bundles."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", filename)
    return os.path.join(src_dir, "..", "assets", filename)


def apply_window_icons(window, png_path: str, ico_path: str) -> None:
    """Sets crisp, multi-resolution titlebar and taskbar icons for Tkinter windows."""
    if sys.platform == "win32" and ico_path and os.path.exists(ico_path):
        try:
            window.iconbitmap(ico_path)
            return
        except Exception:
            pass
    if png_path and os.path.exists(png_path):
        try:
            from PIL import Image, ImageTk
            base = Image.open(png_path).convert("RGBA")
            img = ImageTk.PhotoImage(base)
            window.iconphoto(True, img)
            window._icon_photo = img
        except Exception:
            pass


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
    apply_window_icons(root, icon_png, icon_ico)

    config = AppConfig()
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    icon_instance = []

    notepad = QuickNotepadHUD(master=root, config=config)

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
        on_notepad_toggle_callback=notepad.toggle,
        config=config,
    )
    listener = GlobalKeyboardListener(handler, config=config)
    listener.start()
    
    clipboard_listener = NativeClipboardListener(handler)
    clipboard_listener.start()

    def on_hotkeys_changed() -> None:
        listener.reload_hotkeys()
        if icon_instance:
            try:
                icon_instance[0].menu = build_tray_menu()
                if hasattr(icon_instance[0], "update_menu"):
                    icon_instance[0].update_menu()
            except Exception:
                pass

    # Visual Queue Inspector Window
    inspector = QueueInspectorWindow(
        queue,
        config=config,
        master=root,
        on_hotkeys_changed=on_hotkeys_changed,
    )

    # Background Queue Expiration Manager Thread
    def run_expiration_manager():
        while True:
            time.sleep(1)
            try:
                if config.get("auto_clear_enabled", False):
                    mode = config.get("auto_clear_mode", "idle")
                    timeout = config.get("auto_clear_seconds", 60)
                    if mode == "idle":
                        purged_count = queue.purge_idle(timeout)
                        if purged_count > 0:
                            on_notify("QPaste : Cleared", "cleared")
                            on_update()
                    else:
                        purged_count = queue.purge_expired(timeout)
                        if purged_count > 0:
                            if len(queue) == 0:
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

    def on_toggle_notepad(icon, item):
        notepad.toggle()

    def on_open_inspector(icon, item):
        inspector.show()

    def on_toggle_startup(icon, item):
        if is_startup_enabled():
            disable_startup()
        else:
            enable_startup()

    def on_exit(icon, item):
        notepad.hide()
        config.save()
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

    def build_tray_menu():
        return pystray.Menu(
            item(f"Toggle Queue Mode ({config.get_hotkey('toggle_queue', 'F4')})", on_toggle_queue),
            item(f"Clear Queue ({config.get_hotkey('clear_queue', 'Shift+F4')})", on_clear_queue),
            item(f"Quick Notepad ({config.get_hotkey('toggle_notepad', 'F3')})", on_toggle_notepad),
            item("Open Queue Inspector", on_open_inspector, default=True),
            pystray.Menu.SEPARATOR,
            item("Start with Windows", on_toggle_startup, checked=lambda item: is_startup_enabled()),
            pystray.Menu.SEPARATOR,
            item("Exit", on_exit),
        )

    # Prepare Tray Icon
    icon_path = get_asset_path("icon.png")
    if os.path.exists(icon_path):
        from PIL import ImageEnhance
        image = Image.open(icon_path).convert("RGBA")
        image = image.resize((64, 64), Image.Resampling.LANCZOS)
        image = ImageEnhance.Sharpness(image).enhance(1.8)
    else:
        # Fallback image
        image = Image.new("RGB", (64, 64), color=(40, 180, 220))

    menu = build_tray_menu()
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
        notepad.hide()
        config.save()
        clipboard_listener.stop()
        listener.stop()
        single_inst.release()
        os._exit(0)


if __name__ == "__main__":
    main()
