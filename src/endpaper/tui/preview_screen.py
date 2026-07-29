from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Markdown

from endpaper.core.models import Meeting
from endpaper.tui.rendering import render_preview_markdown
from endpaper.tui.status_bar import PREVIEW_HELP, StatusBar


class PreviewScreen(Screen[None]):
    BINDINGS = [Binding("escape", "close_preview", "Back", show=False)]

    def __init__(self, meeting: Meeting) -> None:
        super().__init__()
        self.meeting = meeting

    def compose(self) -> ComposeResult:
        yield Markdown(id="full-preview")
        with Vertical(id="bottom-bar"):
            yield StatusBar(PREVIEW_HELP, id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#full-preview", Markdown).update(render_preview_markdown(self.meeting))

    def action_close_preview(self) -> None:
        self.app.pop_screen()
