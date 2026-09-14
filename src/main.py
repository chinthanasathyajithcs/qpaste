"""
QPaste - Sequential Clipboard Manager Application Entry Point.
Launches the Win32 Named Mutex single-instance check, global keyboard listener,
System Tray icon, Native Toast Overlay, Visual Queue Inspector, and Quick Notepad HUD.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional

try:
    import tkinter as tk
except ImportError:
    tk = None  # type: ignore[assignment]

from PIL import Image
import pystray
from pystray import MenuItem as item

src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from core.clipboard_queue import ClipboardQueue
from core.config import AppConfig
from core.listener import GlobalKeyboardListener, NativeClipboardListener, ShortcutHandler
from core.single_instance import SingleInstance
from core.startup import disable_startup, enable_startup, is_startup_enabled
from core.state import AppState
from ui.inspector import QueueInspectorWindow
from ui.notepad import QuickNotepadHUD
from ui.toast import NativeToastOverlay


def get_asset_path(filename: str) -> str:
    """Get absolute path to asset resource, supporting PyInstaller bundles."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", filename)
    return os.path.join(src_dir, "..", "assets", filename)


def apply_window_icons(window: tk.Tk | tk.Toplevel, png_path: str, ico_path: str) -> None:
    """Sets crisp titlebar and taskbar icons for Tkinter windows."""
    if sys.platform == "win32" and ico_path and os.path.exists(ico_path):
        try:
            window.iconbitmap(ico_path)
            return
        except Exception:
            pass
    if png_path and os.path.exists(png_path):
        try:
            from PIL import ImageTk
            base = Image.open(png_path).convert("RGBA")
            img = ImageTk.PhotoImage(base)
            window.iconphoto(True, img)
            setattr(window, "_icon_photo", img)
        except Exception:
            pass


def main() -> None:
    single_inst = SingleInstance()
    if not single_inst.acquire():
        print("[QPaste] Another instance is already running. Exiting.")
        sys.exit(0)

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QPaste.ClipboardManager.1.0")
        except Exception:
            pass

    root = tk.Tk()
    root.withdraw()
    apply_window_icons(root, get_asset_path("icon.png"), get_asset_path("icon.ico"))

    config = AppConfig()
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    icon_instance: list[pystray.Icon] = []

    toast_overlay = NativeToastOverlay(master=root)
    toast_overlay.start()

    def on_notify(message: str, toast_type: str = "info") -> None:
        toast_overlay.show_toast(message, toast_type)

    notepad = QuickNotepadHUD(root=root, config=config)
    inspector: Optional[QueueInspectorWindow] = None

    def on_update() -> None:
        if inspector and hasattr(inspector, "master") and inspector.master:
            try:
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

    def get_toggle_queue_label(_item: object = None) -> str:
        hk = config.get_hotkey("toggle_queue", default="F4")
        return f"Toggle Queue Mode ({hk})" if hk else "Toggle Queue Mode"

    def get_clear_queue_label(_item: object = None) -> str:
        hk = config.get_hotkey("clear_queue", default="Shift+F4")
        return f"Clear Queue ({hk})" if hk else "Clear Queue"

    def get_notepad_label(_item: object = None) -> str:
        hk = config.get_hotkey("toggle_notepad", default="F3")
        return f"Quick Notepad ({hk})" if hk else "Quick Notepad"

    def on_toggle_startup(_icon: pystray.Icon, _item: object) -> None:
        disable_startup() if is_startup_enabled() else enable_startup()

    def on_exit(_icon: Optional[pystray.Icon] = None, _item: object = None) -> None:
        try:
            notepad.hide()
            config.save()
            if inspector:
                inspector.hide()
        except Exception:
            pass
        clipboard_listener.stop()
        listener.stop()
        single_inst.release()
        if icon_instance:
            try:
                icon_instance[0].stop()
            except Exception:
                pass
        try:
            root.quit()
        except Exception:
            pass
        os._exit(0)

    def build_tray_menu() -> pystray.Menu:
        return pystray.Menu(
            item(get_toggle_queue_label, lambda _icon, _it: handler.handle_f4()),
            item(get_clear_queue_label, lambda _icon, _it: handler.handle_shift_f4()),
            item(get_notepad_label, lambda _icon, _it: notepad.toggle()),
            item("Open Queue Inspector", lambda _icon, _it: inspector.show() if inspector else None, default=True),
            pystray.Menu.SEPARATOR,
            item("Start with Windows", on_toggle_startup, checked=lambda _it: is_startup_enabled()),
            pystray.Menu.SEPARATOR,
            item("Exit", on_exit),
        )

    def on_hotkeys_changed() -> None:
        listener.reload_hotkeys()
        if icon_instance:
            try:
                icon_instance[0].menu = build_tray_menu()
                if hasattr(icon_instance[0], "update_menu"):
                    icon_instance[0].update_menu()
            except Exception:
                pass

    inspector = QueueInspectorWindow(
        queue,
        config=config,
        master=root,
        on_hotkeys_changed=on_hotkeys_changed,
    )

    def run_expiration_manager() -> None:
        while True:
            time.sleep(1)
            try:
                if config.get("auto_clear_enabled", False):
                    timeout = config.get("auto_clear_seconds", 60)
                    purged = queue.purge_idle(timeout)
                    if purged > 0:
                        on_notify("QPaste : Cleared", "cleared")
                        on_update()
            except Exception:
                pass

    exp_thread = threading.Thread(target=run_expiration_manager, daemon=True)
    exp_thread.start()

    icon_path = get_asset_path("icon.png")
    if os.path.exists(icon_path):
        from PIL import ImageEnhance
        image = Image.open(icon_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        image = ImageEnhance.Sharpness(image).enhance(1.8)
    else:
        image = Image.new("RGB", (64, 64), color=(40, 180, 220))

    tray_icon = pystray.Icon("QPaste", image, "QPaste", build_tray_menu())
    icon_instance.append(tray_icon)
    tray_icon.run_detached()

    print("[QPaste] Application running silently in System Tray.")

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            notepad.hide()
            config.save()
        except Exception:
            pass
        clipboard_listener.stop()
        listener.stop()
        single_inst.release()
        os._exit(0)


if __name__ == "__main__":
    main()

