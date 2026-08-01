from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.widgets import TextArea

from endpaper.core.assistants import (
    AssistantRequest,
    compose_prompt,
    resolve_assistant,
    start_request,
)
from endpaper.core.config import get_assistant
from endpaper.core.editing import load_for_edit, save_buffer
from endpaper.core.editor_commands import parse_line
from endpaper.core.links import find_link_targets, format_link
from endpaper.core.models import AssistantReply, EditableFile, ParsedCommand, ResolvedAssistant
from endpaper.tui.discard_dialog import DiscardDialog
from endpaper.tui.status_bar import (
    EDIT_HELP,
    StatusBar,
    in_flight_status,
    link_ambiguous_status,
    link_no_match_status,
    pick_breadcrumb,
)

_PLACEHOLDER = "⋯"


def open_editor(app: App[None], path: Path) -> bool:
    """Push the editor for `path` -- the one route into `EditScreen`, used by list
    `e`, preview `e`, and every create path (research R10). Returns False and
    reports the reason in the caller's status bar if the file cannot be read,
    leaving the caller's screen in place rather than raising."""
    try:
        file = load_for_edit(path)
    except OSError as exc:
        try:
            status = app.screen.query_one(StatusBar)
        except NoMatches:
            pass
        else:
            status.update(f"⚠ could not open {path.name}: {exc}")
        return False
    app.push_screen(EditScreen(file))
    return True


def _resolution_message(resolved: ResolvedAssistant) -> str:
    if resolved.source == "none":
        return "no AI assistant configured (set to none); run /config assistant to change it"
    if resolved.source == "ambiguous":
        return (
            f"multiple AI assistants available ({', '.join(resolved.available)}); "
            "choose one with /config assistant"
        )
    return "no AI assistant found; install one or set it with /config assistant"


class EditorTextArea(TextArea):
    """A `TextArea` that intercepts Enter to run an in-editor command, e.g. `/ai
    <prompt>` (research R5). Every other line falls through to Textual's own
    newline handling -- the 99% case is untouched."""

    class EditorCommandSubmitted(Message):
        def __init__(self, parsed: ParsedCommand, line_index: int) -> None:
            self.parsed = parsed
            self.line_index = line_index
            super().__init__()

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter" and not self.read_only:
            row, _ = self.cursor_location
            parsed = parse_line(self.get_line(row).plain)
            if parsed is not None:
                event.stop()
                event.prevent_default()
                self.post_message(self.EditorCommandSubmitted(parsed, row))
                return
        await super()._on_key(event)


class EditScreen(Screen[None]):
    # TextArea itself binds ctrl+o is unbound but ctrl+s/ctrl+x are (cut); `priority=True`
    # means these are checked app-down-to-focused-widget, before TextArea's own
    # bindings, so they aren't shadowed by the focused editor (e.g. TextArea's
    # built-in ctrl+x -> cut).
    BINDINGS = [
        Binding("ctrl+o", "save", "Save", show=True, priority=True),
        Binding("ctrl+s", "save", "Save", show=False, priority=True),
        Binding("ctrl+x", "save_and_close", "Save & close", show=True, priority=True),
        Binding("escape", "close", "Discard", show=True),
        # The one justified deviation from Principle V's ctrl+c/ctrl+q reservation
        # (plan Complexity Tracking): active only while a request is in flight, and
        # the cancel hint is on screen for the whole wait via in_flight_status().
        Binding("ctrl+c", "cancel_request", "Cancel", show=False, priority=True),
    ]

    def __init__(self, file: EditableFile) -> None:
        super().__init__()
        self.file = file
        self.original_text = file.text
        self._request: AssistantRequest | None = None
        self._breadcrumb: str | None = None

    @property
    def is_dirty(self) -> bool:
        return self.query_one("#editor", TextArea).text != self.original_text

    def compose(self) -> ComposeResult:
        yield EditorTextArea(self.file.text, show_line_numbers=True, id="editor")
        with Vertical(id="bottom-bar"):
            yield StatusBar(EDIT_HELP, id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#editor", TextArea).focus()

    def on_resize(self, event: events.Resize) -> None:
        if self._request is not None:
            self._render_in_flight_status()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "cancel_request":
            return self._request is not None
        return True

    def _render_status(self, note: str | None = None) -> None:
        status = self.query_one(StatusBar)
        status.update(f"⚠ {note}   {EDIT_HELP}" if note else EDIT_HELP)

    def _render_in_flight_status(self) -> None:
        if self._breadcrumb is None:
            return
        status = self.query_one(StatusBar)
        status.update(in_flight_status(self._breadcrumb, status.size.width))

    def _save(self) -> bool:
        editor = self.query_one("#editor", TextArea)
        workspace = self.app.workspace  # type: ignore[attr-defined]
        result = save_buffer(self.file.path, editor.text, self.file, workspace=workspace)
        if not result.ok:
            self._render_status(result.message)
            return False

        if result.saved_text != editor.text:
            # The stamp changed the `updated:` line -- sync the buffer to match
            # what actually landed on disk, or the widget would read as dirty
            # the instant it saved (whenever the new timestamp differs from
            # what's still displayed). `load_text` resets cursor/selection, so
            # capture and restore it around the reload (FR-014).
            cursor = editor.cursor_location
            editor.text = result.saved_text
            editor.cursor_location = cursor

        self.original_text = result.saved_text
        self.file = replace(self.file, text=result.saved_text)
        self.app.refresh_document(self.file.path)  # type: ignore[attr-defined]
        if not result.stamped:
            self._render_status("frontmatter's updated: field could not be found; saved as typed")
        elif result.warnings:
            self._render_status("; ".join(w.message for w in result.warnings))
        else:
            self._render_status(None)
        return True

    def action_save(self) -> None:
        self._save()

    def action_save_and_close(self) -> None:
        if self._save():
            self.app.pop_screen()

    def action_close(self) -> None:
        if not self.is_dirty:
            self.app.pop_screen()
            return

        def _handle_dismiss(discard: bool | None) -> None:
            if discard:
                self.app.pop_screen()
            else:
                self.query_one("#editor", TextArea).focus()

        self.app.push_screen(DiscardDialog(), _handle_dismiss)

    # --- /ai in-editor command --------------------------------------------------

    @on(EditorTextArea.EditorCommandSubmitted)
    def _on_editor_command_submitted(self, message: EditorTextArea.EditorCommandSubmitted) -> None:
        if message.parsed.command.name == "ai":
            self._start_ai_request(message.parsed, message.line_index)
        elif message.parsed.command.name == "link":
            self._insert_link(message.parsed, message.line_index)

    def _insert_link(self, parsed: ParsedCommand, line_index: int) -> None:
        if not parsed.argument:
            self._render_status(f"/{parsed.command.name} needs search terms")
            return

        if not self._save():
            return  # save error already reported

        workspace = self.app.workspace  # type: ignore[attr-defined]
        matches = find_link_targets(workspace, parsed.argument)

        if not matches:
            self._render_status(link_no_match_status(parsed.argument))
            return
        if len(matches) > 1:
            self._render_status(link_ambiguous_status([m.title for m in matches]))
            return

        target = matches[0]
        editor = self.query_one("#editor", EditorTextArea)
        original_line = editor.get_line(line_index).plain
        link_text = format_link(self.file.path, target, target.title)
        editor.replace(
            link_text,
            (line_index, 0),
            (line_index, len(original_line)),
            maintain_selection_offset=False,
        )
        self._render_status(None)

    def _start_ai_request(self, parsed: ParsedCommand, line_index: int) -> None:
        if parsed.command.requires_argument and not parsed.argument:
            self._render_status(f"/{parsed.command.name} needs a prompt")
            return

        if not self._save():
            return  # save error already reported; the assistant is never invoked

        editor = self.query_one("#editor", EditorTextArea)
        original_line = editor.get_line(line_index).plain

        configured = get_assistant(self.app.workspace)  # type: ignore[attr-defined]
        resolved = resolve_assistant(configured)
        if resolved.profile is None:
            self._render_status(_resolution_message(resolved))
            return

        prompt = compose_prompt(parsed.argument, self.file.path, line_index + 1)
        request = start_request(
            resolved.profile,
            prompt,
            cwd=self.app.workspace.root,  # type: ignore[attr-defined]
        )

        self._request = request
        self._breadcrumb = pick_breadcrumb()
        editor.replace(_PLACEHOLDER, (line_index, 0), (line_index, len(original_line)))
        editor.read_only = True
        self._render_in_flight_status()

        self._run_assistant(request, line_index, original_line)

    @work(thread=True)
    def _run_assistant(
        self, request: AssistantRequest, line_index: int, original_line: str
    ) -> None:
        reply = request.wait()
        self.app.call_from_thread(self._finish_request, request, line_index, original_line, reply)

    def _finish_request(
        self,
        request: AssistantRequest,
        line_index: int,
        original_line: str,
        reply: AssistantReply,
    ) -> None:
        if request is not self._request:
            return  # superseded -- discard rather than touch a buffer that moved on

        self._request = None
        self._breadcrumb = None
        editor = self.query_one("#editor", EditorTextArea)
        editor.read_only = False

        if reply.ok:
            editor.replace(
                reply.text,
                (line_index, 0),
                (line_index, len(_PLACEHOLDER)),
                maintain_selection_offset=False,
            )
            self._render_status(None)
        else:
            editor.replace(
                original_line,
                (line_index, 0),
                (line_index, len(_PLACEHOLDER)),
                maintain_selection_offset=False,
            )
            self._render_status(None if reply.cancelled else reply.message)

        editor.focus()

    def action_cancel_request(self) -> None:
        if self._request is not None:
            self._request.cancel()
