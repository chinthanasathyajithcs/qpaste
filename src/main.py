"""
QPaste - Sequential Clipboard Manager Application Entry Point.
Launches the global pynput keyboard listener, System Tray icon, and Native Toast Overlay.
"""
import os
import sys
import threading
from PIL import Image

# Ensure src directory is on sys.path for robust cross-environment module resolution
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import pystray
from pystray import MenuItem as item

from core.clipboard_queue import ClipboardQueue
from core.listener import GlobalKeyboardListener, ShortcutHandler
from core.state import AppState
from core.startup import is_startup_enabled, enable_startup, disable_startup
from ui.toast import NativeToastOverlay


def main() -> None:
    state = AppState(initial_active=True)
    queue = ClipboardQueue()
    icon_instance = []

    # Native ToolWindow Toast Overlay
    toast_overlay = NativeToastOverlay()
    toast_thread = threading.Thread(target=toast_overlay.start, daemon=True)
    toast_thread.start()

    def on_notify(message: str, toast_type: str = "info") -> None:
        toast_overlay.show_toast(message, toast_type)

    handler = ShortcutHandler(
        state,
        queue,
        on_notify_callback=on_notify,
    )
    listener = GlobalKeyboardListener(handler)
    listener.start()

    # --- System Tray Menu ---
    def on_toggle_queue(icon, item):
        handler.handle_f4()

    def on_clear_queue(icon, item):
        handler.handle_shift_f4()

    def on_toggle_startup(icon, item):
        if is_startup_enabled():
            disable_startup()
        else:
            enable_startup()

    def on_exit(icon, item):
        listener.stop()
        if icon_instance:
            icon_instance[0].stop()
        os._exit(0)

    # Prepare Tray Icon
    icon_path = os.path.join(src_dir, "..", "assets", "icon.png")
    if os.path.exists(icon_path):
        image = Image.open(icon_path)
    else:
        # Fallback image
        image = Image.new("RGB", (64, 64), color=(40, 180, 220))

    menu = pystray.Menu(
        item("Toggle Queue Mode (F4)", on_toggle_queue),
        item("Clear Queue (Shift+F4)", on_clear_queue),
        pystray.Menu.SEPARATOR,
        item("Start with Windows", on_toggle_startup, checked=lambda item: is_startup_enabled()),
        pystray.Menu.SEPARATOR,
        item("Exit", on_exit),
    )

    tray_icon = pystray.Icon("QPaste", image, "QPaste", menu)
    icon_instance.append(tray_icon)

    print("[QPaste] Application running silently in System Tray.")

    try:
        tray_icon.run()
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        os._exit(0)


if __name__ == "__main__":
    main()
