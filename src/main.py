"""
QPaste - Sequential Clipboard Manager Application Entry Point.
Launches the global pynput keyboard listener thread and the Flet HUD GUI.
"""
import os
import sys

# Ensure src directory is on sys.path for robust cross-environment module resolution
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import flet as ft

from core.clipboard_queue import ClipboardQueue
from core.listener import GlobalKeyboardListener, ShortcutHandler
from core.state import AppState
from ui.hud import QPasteHUD


def main() -> None:
    # Initialize core engine modules
    state = AppState(initial_active=True)
    queue = ClipboardQueue()

    # Pre-declare HUD container
    hud_instance: list[QPasteHUD] = []

    def on_update_ui() -> None:
        """Triggered whenever hotkeys alter Queue or State."""
        if hud_instance and hud_instance[0]:
            hud_instance[0].refresh_ui()

    # Initialize shortcut handler and listener
    handler = ShortcutHandler(state, queue, on_update_callback=on_update_ui)
    listener = GlobalKeyboardListener(handler)

    def flet_main(page: ft.Page) -> None:
        # Create HUD overlay
        hud = QPasteHUD(
            state=state,
            queue=queue,
            on_toggle_callback=handler.handle_f4,
            on_clear_callback=handler.handle_shift_f4,
        )
        hud_instance.append(hud)

        def on_window_event(e: ft.ControlEvent) -> None:
            if e.data == "close":
                listener.stop()
                page.window.destroy()

        page.window.prevent_close = True
        page.on_window_event = on_window_event

        hud.build(page)

    # Start background global keyboard listener thread
    listener.start()
    print("[QPaste] Global Keyboard Listener started. Press F4 to toggle Queue mode.")

    try:
        # Launch Flet GUI app
        ft.run(flet_main)
    finally:
        listener.stop()
        print("[QPaste] Application exited cleanly.")


if __name__ == "__main__":
    main()

