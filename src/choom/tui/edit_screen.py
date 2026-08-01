from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import Screen
from textual.widgets import TextArea

from choom.core.assistants import (
    AssistantRequest,
    compose_prompt,
    resolve_assistant,
    start_request,
)
from choom.core.config import get_assistant
from choom.core.documents import _read_document
from choom.core.editing import load_for_edit, save_buffer
from choom.core.editor_commands import parse_line
from choom.core.errors import NotFoundError, UsageError, WorkspaceError
from choom.core.links import find_link_targets, format_link
from choom.core.mirrors import (
    capture_reply_tasks,
    capture_task,
    find_mirrors,
    reconcile_on_open,
    reconcile_on_save,
    write_document,
)
from choom.core.models import (
    AssistantReply,
    ParsedCommand,
    ReplyCapture,
    ResolvedAssistant,
    SaveResult,
    Task,
)
from choom.core.tasks import parse_tasks, set_task_body
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.status_bar import (
    EDIT_HELP,
    StatusBar,
    in_flight_status,
    link_ambiguous_status,
    link_no_match_status,
    pick_breadcrumb,
)

_PLACEHOLDER = "⋯"


@dataclass(frozen=True, slots=True)
class EditTarget:
    """What `EditScreen` edits: the buffer's starting text, how to save it, the
    path shown to the user and handed to `/ai`, the line offset that positions
    an `/ai` prompt within that file, whether the target has frontmatter to
    stamp (research R5), and whether it has a document identity a `/task`
    capture -- typed or from a reply -- can link from (research R3). A file
    and a task's body are its two implementations -- `EditScreen` itself
    knows neither one, only this shape."""

    text: str
    display_path: Path
    save: Callable[[str], SaveResult]
    ai_line_offset: int
    stamps_frontmatter: bool
    captures_tasks: bool


def open_editor(app: App[None], path: Path) -> bool:
    """Push the editor for `path` -- the one route into `EditScreen` for a whole
    file, used by list `e`, preview `e`, and every create path (research R10).
    Returns False and reports the reason in the caller's status bar if the file
    cannot be read, leaving the caller's screen in place rather than raising.

    Reconciles every mirror in the file against tasks.md before the buffer is
    handed to `EditScreen` (research R6, FR-026), so the buffer and the file
    agree from the first keystroke. A reconcile failure is best-effort and never
    turns a successful open into a `False` -- 009's own contract on top of the
    one this function already carried.
    """
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

    workspace = app.workspace  # type: ignore[attr-defined]
    report = reconcile_on_open(workspace, file.text, source=path)
    text = report.text
    if text is not file.text:
        write_document(path, text, file)

    def _save(text: str) -> SaveResult:
        workspace = app.workspace  # type: ignore[attr-defined]
        return save_buffer(file.path, text, file, workspace=workspace)

    target = EditTarget(
        text=text,
        display_path=path,
        save=_save,
        ai_line_offset=0,
        stamps_frontmatter=True,
        captures_tasks=True,
    )
    app.push_screen(EditScreen(target))
    return True


def _task_ai_line_offset(app: App[None], task_id: str) -> int:
    """0-based index, within the *current* tasks.md, of the task's body span --
    used so an `/ai` prompt composed from inside the body points at the right
    line of the file (research R5). Best-effort: falls back to 0 if the task
    cannot be located, which only understates a positional reference inside an
    `/ai` prompt and never affects the save path itself."""
    workspace = app.workspace  # type: ignore[attr-defined]
    try:
        text = workspace.tasks_file.read_text(encoding="utf-8")
    except OSError:
        return 0
    parsed = parse_tasks(text)
    for index, task in enumerate(parsed.tasks):
        if task.id == task_id:
            return parsed.bodies[index].start
    return 0


def open_task_editor(app: App[None], task: Task) -> None:
    """Push the editor scoped to `task`'s body (research R5). Never fails to
    open: the buffer is the dedented body text already held in memory, so
    there is no file read on the way in -- only the save can fail, and that is
    reported in the status bar without discarding what the user typed
    (FR-023).

    Reconciles any mirror inside the body against tasks.md first, on the same
    terms as `open_editor` (FR-026): the task is authoritative, since the user
    has not acted on this body yet."""
    assert task.id is not None
    task_id = task.id
    workspace = app.workspace  # type: ignore[attr-defined]

    body = task.body
    report = reconcile_on_open(workspace, body, source=workspace.tasks_file)
    if report.text is not body:
        try:
            set_task_body(workspace, task_id, report.text)
        except (NotFoundError, UsageError, WorkspaceError):
            pass
        else:
            body = report.text

    def _save(text: str) -> SaveResult:
        try:
            set_task_body(workspace, task_id, text)
        except (NotFoundError, UsageError, WorkspaceError) as exc:
            return SaveResult(ok=False, saved_text="", stamped=False, message=str(exc))
        return SaveResult(ok=True, saved_text=text, stamped=False, message="")

    target = EditTarget(
        text=body,
        display_path=workspace.tasks_file,
        save=_save,
        ai_line_offset=_task_ai_line_offset(app, task_id),
        stamps_frontmatter=False,
        captures_tasks=False,
    )
    app.push_screen(EditScreen(target))


def _reply_capture_note(capture: ReplyCapture) -> tuple[str | None, bool]:
    """The status note and its `warn` flag for a reply's capture result
    (contracts/reply-capture.md §4). No eligible line at all is exactly
    today's plain footer -- `(None, False)`. All captured is news, not a
    warning. Any failure, partial or total, carries `⚠` and names the first
    reason; the count in front of it, when there is one, carries the rest."""
    if not capture.tasks and not capture.warnings:
        return None, False
    if not capture.warnings:
        count = len(capture.tasks)
        noun = "task" if count == 1 else "tasks"
        return f"{count} {noun} captured", False
    if not capture.tasks:
        return capture.warnings[0].message, True
    return (
        f"{len(capture.tasks)} tasks captured; {len(capture.warnings)} could not be: "
        f"{capture.warnings[0].message}",
        True,
    )


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


def _pad_for_cursor(text: str) -> tuple[str, int]:
    """The padded buffer and 0-indexed cursor row for entering edit mode
    (US7, research R10): the cursor lands on an empty line exactly one blank
    line below the last non-empty line, with existing trailing blank lines
    collapsed rather than stacked on top of (FR-039, FR-040). Content with no
    non-empty line at all -- including a genuinely empty string -- is
    returned unchanged with the cursor at the first line: there is nothing
    to separate a cursor from, and FR-041 forbids inserting anything above it.

    Pure string arithmetic, and the buffer's own unedited state (research
    R10): a caller that sets `original_text` to the padded result gets
    FR-042 -- entering and leaving without typing raises no confirmation and
    writes nothing -- without a special case, since padding alone is then
    never a change. Never raises.
    """
    lines = text.split("\n")
    last_content = -1
    for index, line in enumerate(lines):
        if line.strip() != "":
            last_content = index

    if last_content == -1:
        return "", 0

    kept = lines[: last_content + 1]
    # Two empties, not one: the first is the blank line that separates the
    # cursor from the content, the second is the line the cursor sits on.
    # Padding with a single empty puts the cursor directly under the last
    # content line with nothing between, which is the state FR-039 rules out.
    padded = "\n".join([*kept, "", ""])
    return padded, len(kept) + 1


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

    def __init__(self, target: EditTarget) -> None:
        super().__init__()
        self.target = target
        self._padded_text, self._cursor_row = _pad_for_cursor(target.text)
        # The buffer's unedited state is the padded text, not target.text --
        # positioning the cursor is not itself an edit (FR-042). Any trailing
        # blank line that ends up on disk arises only from what the user
        # actually types or from a save that persists this unedited padding
        # (research R10, accepted consequence).
        self.original_text = self._padded_text
        self._request: AssistantRequest | None = None
        self._breadcrumb: str | None = None
        # What each mirror in `target.text` read at open (or last reconciled) --
        # "since they last agreed", held for the life of this screen and never
        # persisted (research R4). Seeded from the already-reconciled text the
        # screen was constructed with, so a correction applied at open is never
        # mistaken at save time for an edit the user made (US5/US6).
        self._mirror_baseline: dict[str, bool] = {
            m.task_id: m.done for m in find_mirrors(target.text, source=target.display_path)
        }

    @property
    def is_dirty(self) -> bool:
        return self.query_one("#editor", TextArea).text != self.original_text

    def compose(self) -> ComposeResult:
        yield EditorTextArea(self._padded_text, show_line_numbers=True, id="editor")
        with Vertical(id="bottom-bar"):
            yield StatusBar(EDIT_HELP, id="status-bar")

    def on_mount(self) -> None:
        editor = self.query_one("#editor", TextArea)
        editor.cursor_location = (self._cursor_row, 0)
        editor.focus()

    def on_resize(self, event: events.Resize) -> None:
        if self._request is not None:
            self._render_in_flight_status()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "cancel_request":
            return self._request is not None
        return True

    def _render_status(self, note: str | None = None, *, warn: bool = True) -> None:
        status = self.query_one(StatusBar)
        if note is None:
            status.update(EDIT_HELP)
            return
        prefix = "⚠ " if warn else ""
        status.update(f"{prefix}{note}   {EDIT_HELP}")

    def _render_in_flight_status(self) -> None:
        if self._breadcrumb is None:
            return
        status = self.query_one(StatusBar)
        status.update(in_flight_status(self._breadcrumb, status.size.width))

    def _save(self) -> bool:
        editor = self.query_one("#editor", TextArea)
        text = editor.text

        workspace = self.app.workspace  # type: ignore[attr-defined]
        mirror_report = reconcile_on_save(
            workspace,
            text,
            source=self.target.display_path,
            baseline=self._mirror_baseline,
        )
        if mirror_report.text is not text:
            # A correction flowed from tasks.md into this buffer -- the user
            # sees it land before the save that is about to stamp `updated`.
            cursor = editor.cursor_location
            editor.text = mirror_report.text
            editor.cursor_location = cursor
            text = mirror_report.text

        result = self.target.save(text)
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
        self._mirror_baseline = {
            m.task_id: m.done
            for m in find_mirrors(result.saved_text, source=self.target.display_path)
        }

        messages = [w.message for w in result.warnings]
        messages.extend(w.message for w in mirror_report.warnings)
        if self.target.stamps_frontmatter and not result.stamped:
            self._render_status("frontmatter's updated: field could not be found; saved as typed")
        elif messages:
            self._render_status("; ".join(messages))
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

        dialog = ConfirmDialog(
            "You have unsaved changes. Are you sure you want to exit?",
            cancel_label="Continue Editing",
            confirm_label="Exit Without Saving",
        )
        self.app.push_screen(dialog, _handle_dismiss)

    # --- /ai in-editor command --------------------------------------------------

    @on(EditorTextArea.EditorCommandSubmitted)
    def _on_editor_command_submitted(self, message: EditorTextArea.EditorCommandSubmitted) -> None:
        if message.parsed.command.name == "ai":
            self._start_ai_request(message.parsed, message.line_index)
        elif message.parsed.command.name == "link":
            self._insert_link(message.parsed, message.line_index)
        elif message.parsed.command.name == "task":
            self._capture_task(message.parsed, message.line_index)

    def _capture_task(self, parsed: ParsedCommand, line_index: int) -> None:
        """`/task <description>` and `/task.<type> <description>` (contracts/tui.md):
        validate, save the document in its pre-command state, capture through
        `core.mirrors.capture_task`, then replace the typed line with the mirror
        as one undo step and land the cursor at its end. No screen push, no
        collection change, no scroll change (FR-006)."""
        if not parsed.argument:
            self._render_status(f"/{parsed.command.name} needs a description")
            return

        if not self.target.captures_tasks:
            # A task's own body has no document identity of its own to link
            # from -- only `open_editor` targets are documents.
            self._render_status("/task is only available while editing a document")
            return

        if not self._save():
            return  # save error already reported; capture does not proceed

        document = _read_document(self.target.display_path)
        if document is None:
            self._render_status("/task could not identify this document")
            return

        workspace = self.app.workspace  # type: ignore[attr-defined]
        try:
            task, line = capture_task(
                workspace,
                parsed.argument,
                type=parsed.suffix,
                source=self.target.display_path,
                source_id=document.id,
            )
        except (UsageError, WorkspaceError) as exc:
            self._render_status(str(exc))
            return

        editor = self.query_one("#editor", EditorTextArea)
        original_line = editor.get_line(line_index).plain
        editor.replace(
            line,
            (line_index, 0),
            (line_index, len(original_line)),
            maintain_selection_offset=False,
        )
        editor.cursor_location = (line_index, len(line))
        assert task.id is not None
        self._mirror_baseline[task.id] = False
        self._render_status(None)

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
        link_text = format_link(self.target.display_path, target, target.title)
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

        prompt = compose_prompt(
            parsed.argument, self.target.display_path, self.target.ai_line_offset + line_index + 1
        )
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
            text = reply.text
            note: str | None = None
            warn = False

            if self.target.captures_tasks:
                workspace = self.app.workspace  # type: ignore[attr-defined]
                document = _read_document(self.target.display_path)
                if document is not None:
                    capture = capture_reply_tasks(
                        workspace,
                        text,
                        source=self.target.display_path,
                        source_id=document.id,
                    )
                    text = capture.text
                    for task in capture.tasks:
                        assert task.id is not None
                        self._mirror_baseline[task.id] = False
                    note, warn = _reply_capture_note(capture)

            editor.replace(
                text,
                (line_index, 0),
                (line_index, len(_PLACEHOLDER)),
                maintain_selection_offset=False,
            )
            self._render_status(note, warn=warn)
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
