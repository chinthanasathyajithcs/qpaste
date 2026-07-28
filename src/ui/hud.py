"""
Flet Floating HUD Overlay Interface for QPaste.
Provides a modern glassmorphic UI displaying Queue state and live snippets.
"""
os_import = __import__("os")
sys_import = __import__("sys")
_src_dir = os_import.path.dirname(os_import.path.dirname(os_import.path.abspath(__file__)))
if _src_dir not in sys_import.path:
    sys_import.path.insert(0, _src_dir)

from typing import Callable, Optional
import flet as ft

from core.clipboard_queue import ClipboardQueue
from core.state import AppState



class QPasteHUD:
    """Manages the Flet desktop overlay interface."""

    def __init__(
        self,
        state: AppState,
        queue: ClipboardQueue,
        on_toggle_callback: Optional[Callable[[], None]] = None,
        on_clear_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.state = state
        self.queue = queue
        self.on_toggle_callback = on_toggle_callback
        self.on_clear_callback = on_clear_callback
        self.page: Optional[ft.Page] = None

        # UI Components
        self.status_badge = ft.Container()
        self.queue_container = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=8)
        self.queue_count_text = ft.Text("0 items", size=12, color=ft.Colors.WHITE_54)

    def build(self, page: ft.Page) -> None:
        """Initializes Flet page window settings and layout structure."""
        self.page = page
        page.title = "QPaste HUD"
        page.window.width = 340
        page.window.height = 480
        page.window.always_on_top = True
        page.window.resizable = False
        page.window.frameless = True
        page.window.bgcolor = ft.Colors.TRANSPARENT
        page.bgcolor = ft.Colors.TRANSPARENT
        page.padding = 10

        # Title bar & Controls
        header = ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PASTE_ROUNDED, color=ft.Colors.CYAN_400, size=22),
                        ft.Text("QPaste", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_color=ft.Colors.WHITE_54,
                            icon_size=18,
                            tooltip="Close QPaste",
                            on_click=lambda _: page.window.close(),
                        )
                    ]
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Quick Control Bar
        self.toggle_button = ft.ElevatedButton(
            text="Toggle (F4)",
            icon=ft.Icons.POWER_SETTINGS_NEW,
            on_click=self._handle_toggle_click,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.BLUE_GREY_800,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )

        self.clear_button = ft.OutlinedButton(
            text="Clear (Shift+F4)",
            icon=ft.Icons.DELETE_SWEEP_OUTLINED,
            on_click=self._handle_clear_click,
            style=ft.ButtonStyle(
                color=ft.Colors.RED_300,
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )

        controls_row = ft.Row(
            controls=[self.toggle_button, self.clear_button],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Status Bar
        status_row = ft.Row(
            controls=[
                self.status_badge,
                self.queue_count_text,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Main Glass Container
        main_card = ft.Container(
            content=ft.Column(
                controls=[
                    header,
                    status_row,
                    ft.Divider(color=ft.Colors.WHITE10, height=1),
                    controls_row,
                    ft.Divider(color=ft.Colors.WHITE10, height=1),
                    ft.Container(
                        content=self.queue_container,
                        expand=True,
                        padding=ft.padding.only(top=5, bottom=5),
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            bgcolor=ft.Colors.with_opacity(0.88, "#121824"),
            border_radius=14,
            padding=16,
            border=ft.border.all(1, ft.Colors.WHITE10),
            shadow=ft.BoxShadow(
                blur_radius=20,
                color=ft.Colors.BLACK54,
                offset=ft.Offset(0, 8),
            ),
            expand=True,
        )

        page.add(main_card)
        self.refresh_ui()

    def _handle_toggle_click(self, e: ft.ControlEvent) -> None:
        if self.on_toggle_callback:
            self.on_toggle_callback()

    def _handle_clear_click(self, e: ft.ControlEvent) -> None:
        if self.on_clear_callback:
            self.on_clear_callback()

    def refresh_ui(self) -> None:
        """Thread-safely re-renders the HUD state and queue list items."""
        if not self.page:
            return

        is_active = self.state.is_active()
        items = self.queue.get_items()

        # Update status badge
        badge_bg = ft.Colors.GREEN_700 if is_active else ft.Colors.GREY_800
        badge_text = "● ACTIVE (QUEUE MODE)" if is_active else "○ PAUSED (DIRECT MODE)"
        badge_color = ft.Colors.GREEN_200 if is_active else ft.Colors.WHITE38

        self.status_badge.content = ft.Container(
            content=ft.Text(badge_text, size=11, weight=ft.FontWeight.BOLD, color=badge_color),
            bgcolor=badge_bg,
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        # Update queue counter
        count = len(items)
        self.queue_count_text.value = f"{count} snippet{'s' if count != 1 else ''} queued"

        # Clear and repopulate queue view
        self.queue_container.controls.clear()

        if count == 0:
            self.queue_container.controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.CONTENT_PASTE_OFF, color=ft.Colors.WHITE24, size=36),
                            ft.Text("Queue is Empty", size=13, color=ft.Colors.WHITE38),
                            ft.Text(
                                "Copy snippets using Ctrl+C\n(F4 to toggle Queue Mode)",
                                size=11,
                                color=ft.Colors.WHITE24,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                    padding=20,
                )
            )
        else:
            for index, snippet in enumerate(items):
                is_next = index == 0
                bg = ft.Colors.with_opacity(0.2, ft.Colors.CYAN_700) if is_next else ft.Colors.WHITE_05
                border_color = ft.Colors.CYAN_400 if is_next else ft.Colors.TRANSPARENT
                label_color = ft.Colors.CYAN_300 if is_next else ft.Colors.WHITE54

                # Truncate preview text
                preview = snippet.strip()
                if len(preview) > 90:
                    preview = preview[:87] + "..."

                item_card = ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Container(
                                content=ft.Text(
                                    f"#{index + 1}",
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                    color=label_color,
                                ),
                                width=28,
                            ),
                            ft.Expanded(
                                content=ft.Text(
                                    preview,
                                    size=12,
                                    color=ft.Colors.WHITE,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    max_lines=2,
                                )
                            ),
                            ft.Container(
                                content=ft.Text(
                                    "NEXT" if is_next else "",
                                    size=9,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.CYAN_300,
                                ),
                                visible=is_next,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=bg,
                    border_radius=8,
                    padding=10,
                    border=ft.border.all(1, border_color),
                )
                self.queue_container.controls.append(item_card)

        self.page.update()
