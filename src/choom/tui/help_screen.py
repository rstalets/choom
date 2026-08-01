from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from choom.core.editor_commands import EDITOR_COMMANDS
from choom.tui.commands import VERB_TABLE

KEY_BINDINGS_HELP = """\
  tab / shift+tab         Next / previous collection
  ↑↓ / j k                Move the highlight
  h / l                   Focus the scope pane / the list pane
  enter                   Open the highlighted document
  e                       Edit the highlighted document, or a task's details
  space                   Toggle the highlighted task
  /                       Open the command bar
  ctrl+q                  Quit
"""


def _render_body() -> str:
    lines = ["Commands", ""]
    for verb in VERB_TABLE:
        token = f"/{verb.name} {verb.argument}".rstrip()
        alias = f"(/{verb.alias})" if verb.alias else ""
        lines.append(f"  {token:<24}{alias:<6}{verb.description}")
    lines.append("")
    lines.append("In-editor commands")
    lines.append("")
    for command in EDITOR_COMMANDS:
        token = f"/{command.name} {command.argument}".rstrip()
        lines.append(f"  {token:<24}{command.description}")
    lines.append("")
    lines.append("Keys")
    lines.append("")
    lines.append(KEY_BINDINGS_HELP)
    lines.append("esc to close")
    return "\n".join(lines)


class HelpScreen(ModalScreen[None]):
    """A bottom-docked modal listing every command verb and key binding (FR-038-041).
    Escape dismisses; the list screen underneath is never popped, so its state
    (highlighted row, displayed month, active filter) survives untouched."""

    BINDINGS = [Binding("escape", "dismiss_help", "Close", show=True)]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-pane"):
            yield Static(_render_body(), id="help-body")

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
