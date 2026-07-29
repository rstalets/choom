from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class DiscardDialog(ModalScreen[bool]):
    def compose(self) -> ComposeResult:
        with Vertical(id="discard-dialog"):
            yield Label("Discard unsaved changes?")
            with Horizontal(id="discard-buttons"):
                yield Button("Discard", id="discard", variant="error")
                yield Button("Cancel", id="cancel", variant="primary")

    @on(Button.Pressed, "#discard")
    def _on_discard(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(False)
