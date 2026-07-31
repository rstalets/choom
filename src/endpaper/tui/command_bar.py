from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Static

from endpaper.tui.commands import resolve_verb


def resolve_mode(text: str) -> tuple[str, str]:
    """Return (mode, first_token). `text` never includes the leading `/` -- that is
    a separate widget (research R3). mode is "filter" once `filter`/`f` is a
    complete token (a trailing space follows it); otherwise "command".
    """
    stripped = text.lstrip()
    if not stripped:
        return "filter", ""
    first_token = stripped.split(None, 1)[0]
    verb_complete = len(stripped) > len(first_token)
    stem = first_token.split(".", 1)[0].lower()
    if stem in ("filter", "f") and verb_complete:
        return "filter", first_token
    return "command", first_token


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
        def __init__(self, kind: str, description: str, type: str) -> None:
            self.kind = kind  # "meeting" | "note" | "task"
            self.description = description
            self.type = type
            super().__init__()

    class DailyRequested(Message):
        pass

    class CollectionRequested(Message):
        def __init__(self, name: str) -> None:
            self.name = name
            super().__init__()

    class ConfigRequested(Message):
        def __init__(self, argument: str) -> None:
            self.argument = argument
            super().__init__()

    class HelpRequested(Message):
        pass

    class BarError(Message):
        def __init__(self, message: str) -> None:
            self.message = message
            super().__init__()

    class Closed(Message):
        pass

    def compose(self) -> ComposeResult:
        with Horizontal(id="bar-row"):
            yield Static("/", id="bar-prefix")
            yield Input(placeholder="filter or command", id="bar-input")

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
        self.post_message(self.FilterChanged(""))
        self.close()

    @on(Input.Changed, "#bar-input")
    def _on_changed(self, event: Input.Changed) -> None:
        mode, first_token = resolve_mode(event.value)
        self.post_message(self.ModeChanged(mode, first_token))
        if mode == "filter" and first_token:
            stripped = event.value.lstrip()
            term = stripped[len(first_token) :].lstrip()
            self.post_message(self.FilterChanged(term))

    @on(Input.Submitted, "#bar-input")
    def _on_submitted(self, event: Input.Submitted) -> None:
        mode, first_token = resolve_mode(event.value)
        if mode == "command" and first_token:
            self._run_command(event.value, first_token)
        self.close()

    def _run_command(self, text: str, first_token: str) -> None:
        stripped = text.lstrip()
        rest = stripped[len(first_token) :].lstrip()
        stem, _, type_part = first_token.partition(".")
        verb = resolve_verb(stem.lower())
        if verb is None:
            self.post_message(
                self.BarError(
                    f"unknown command: '{first_token}'. Press / then 'help' for the list."
                )
            )
            return

        if verb.name == "meeting":
            self.post_message(self.CreateRequested("meeting", rest, type_part))
        elif verb.name == "meetings":
            self.post_message(self.CollectionRequested("meetings"))
        elif verb.name == "note":
            if not rest:
                if type_part:
                    self.post_message(self.BarError(f"note.{type_part} needs a description"))
                else:
                    self.post_message(self.DailyRequested())
            else:
                self.post_message(self.CreateRequested("note", rest, type_part))
        elif verb.name == "notes":
            self.post_message(self.CollectionRequested("notes"))
        elif verb.name == "task":
            if not rest:
                self.post_message(self.BarError("task needs a description"))
            else:
                self.post_message(self.CreateRequested("task", rest, type_part))
        elif verb.name == "tasks":
            self.post_message(self.CollectionRequested("tasks"))
        elif verb.name == "help":
            self.post_message(self.HelpRequested())
        elif verb.name == "config":
            if not rest:
                self.post_message(self.BarError("config needs a setting name"))
            else:
                self.post_message(self.ConfigRequested(rest))
        elif verb.name == "filter":
            pass  # already live-applied; enter just confirms and closes
        # "init" is a registered verb for future features; no TUI action this feature.
