from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Markdown

from endpaper.core.models import Document
from endpaper.tui.rendering import render_preview_markdown
from endpaper.tui.status_bar import PREVIEW_HELP, StatusBar


class PreviewScreen(Screen[None]):
    BINDINGS = [Binding("escape", "close_preview", "Back", show=False)]

    def __init__(self, path: Path, document: Document | None, *, note: str | None = None) -> None:
        super().__init__()
        self.path = path
        self.document = document
        self._note = note

    @property
    def meeting(self) -> Document | None:
        """Feature 001 compatibility alias for `document`."""
        return self.document

    def compose(self) -> ComposeResult:
        yield Markdown(id="full-preview")
        with Vertical(id="bottom-bar"):
            yield StatusBar(PREVIEW_HELP, id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#full-preview", Markdown).update(
            render_preview_markdown(self.path, self.document)
        )
        if self._note:
            self.query_one(StatusBar).update(f"⚠ {self._note}   {PREVIEW_HELP}")

    def action_close_preview(self) -> None:
        self.app.pop_screen()
