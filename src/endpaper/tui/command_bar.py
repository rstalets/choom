from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input, Static

VERBS = {"meeting", "meetings", "init"}


def _normalize(text: str) -> str:
    """Tolerate a literal leading '/' in the typed text.

    The bar is opened by pressing '/', which is not inserted into the input --
    but users naturally retype it anyway (the footer hint reads "/ filter or
    command", and it's the universal command-prefix convention), so a leading
    '/' must not be treated as part of the query/verb.
    """
    return text[1:] if text.startswith("/") else text


def resolve_mode(text: str) -> tuple[str, str]:
    """Return (mode, first_token). mode is 'filter' or 'command'.

    A leading space is an escape hatch that forces filter mode (research.md R4).
    """
    if text.startswith(" "):
        return "filter", ""
    text = _normalize(text)
    stripped = text.lstrip()
    if not stripped:
        return "filter", ""
    first_token = stripped.split(None, 1)[0]
    stem = first_token.split(".", 1)[0].lower()
    if stem in VERBS:
        return "command", first_token
    return "filter", ""


class CommandBar(Static):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    class ModeChanged(Message):
        def __init__(self, mode: str, verb: str) -> None:
            self.mode = mode
            self.verb = verb
            super().__init__()

    class FilterChanged(Message):
        def __init__(self, query: str) -> None:
            self.query = query
            super().__init__()

    class CreateRequested(Message):
        def __init__(self, description: str, type: str) -> None:
            self.description = description
            self.type = type
            super().__init__()

    class ClearRequested(Message):
        pass

    class Closed(Message):
        pass

    def compose(self) -> ComposeResult:
        yield Input(placeholder="/ filter or command", id="bar-input")

    def open(self) -> None:
        self.display = True
        bar = self.query_one(Input)
        bar.value = ""
        bar.focus()
        self.post_message(self.ModeChanged("filter", ""))

    def close(self) -> None:
        self.display = False
        self.post_message(self.Closed())

    def action_cancel(self) -> None:
        self.query_one(Input).value = ""
        self.post_message(self.ClearRequested())
        self.close()

    @on(Input.Changed, "#bar-input")
    def _on_changed(self, event: Input.Changed) -> None:
        mode, verb = resolve_mode(event.value)
        self.post_message(self.ModeChanged(mode, verb))
        if mode == "filter":
            # A leading space is the explicit escape hatch for a literal filter
            # (e.g. the literal word "meetings"); anywhere else, a leading '/' is
            # the retyped activation key, not part of the query.
            query = event.value[1:] if event.value.startswith(" ") else _normalize(event.value)
            self.post_message(self.FilterChanged(query))

    @on(Input.Submitted, "#bar-input")
    def _on_submitted(self, event: Input.Submitted) -> None:
        mode, verb_token = resolve_mode(event.value)
        if mode == "command":
            self._run_command(event.value, verb_token)
        self.close()

    def _run_command(self, text: str, verb_token: str) -> None:
        text = _normalize(text)
        rest = text[len(verb_token) :].lstrip()
        stem, _, type_part = verb_token.partition(".")
        stem = stem.lower()
        if stem == "meeting":
            self.post_message(self.CreateRequested(rest, type_part))
        elif stem == "meetings":
            self.post_message(self.ClearRequested())
        # "init" is a registered verb for future features; no TUI action this feature.
