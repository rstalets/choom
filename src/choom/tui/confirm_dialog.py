from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label


class ConfirmDialog(ModalScreen[bool]):
    """The one confirmation in the product (FR-026): a slim, centred,
    single-question bar with exactly two options, each labelled with its key
    and the outcome that key produces. No `Button`, no focusable child -- there
    is nothing to highlight or move (FR-022), and with nothing focusable, a key
    other than `Esc`/`Enter` does nothing and never reaches the screen
    underneath (FR-025, research R7).

    `Esc` always halts the request that raised the dialog and changes nothing
    (FR-023); `Enter` always proceeds with it (FR-024).
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("enter", "confirm", show=False),
    ]

    def __init__(self, question: str, *, cancel_label: str, confirm_label: str) -> None:
        super().__init__()
        self._question = question
        self._cancel_label = cancel_label
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self._question)
            yield Label(f"(Esc) {self._cancel_label}       (Enter) {self._confirm_label}")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)
