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
from choom.core.editor_commands import parse_line, parse_reply_lines
from choom.core.errors import NotFoundError, UsageError, WorkspaceError
from choom.core.links import format_link, link_candidates, resolve_id
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
    LinkCandidate,
    LinkTarget,
    ParsedCommand,
    ReplyCapture,
    ResolvedAssistant,
    SaveResult,
    Task,
)
from choom.core.tasks import parse_tasks, set_task_body
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.link_picker import LinkPicker
from choom.tui.status_bar import (
    EDIT_HELP,
    LINK_PICKER_HELP,
    StatusBar,
    in_flight_status,
    link_ambiguous_status,
    link_no_match_status,
    pick_breadcrumb,
)

_PLACEHOLDER = "⋯"

#: The picker needs a screen at least this tall to be a usable list rather than
#: the modal experience in all but name (research R7, FR-017): an eight-row
#: picker plus the status line leaves the editor a genuinely usable buffer
#: above it. Below this, `/link` falls back to `link_ambiguous_status()`.
MIN_PICKER_SCREEN_HEIGHT = 12


@dataclass(frozen=True, slots=True)
class EditTarget:
    """What `EditorPane` edits: the buffer's starting text, how to save it, the
    path shown to the user and handed to `/ai`, the line offset that positions
    an `/ai` prompt within that file, whether the target has frontmatter to
    stamp (research R5), and whether it has a document identity a `/task`
    capture -- typed or from a reply -- can link from (research R3). A file
    and a task's body are its two implementations -- `EditorPane` itself
    knows neither one, only this shape."""

    text: str
    display_path: Path
    save: Callable[[str], SaveResult]
    ai_line_offset: int
    stamps_frontmatter: bool
    captures_tasks: bool


def open_editor(app: App[None], path: Path) -> bool:
    """Open the editor for `path` -- the one route into an edit session for a
    whole file, used by list `e`, preview `e`, and every create path (research
    R10). Routes to an inline pane in `#preview-pane` when `ListScreen` is the
    active screen, full-screen otherwise (research R1, contract C1). Returns
    False and reports the reason in the caller's status bar if the file
    cannot be read, leaving the caller's screen in place rather than raising.

    Reconciles every mirror in the file against tasks.md before the buffer is
    handed to the editor (research R6, FR-026), so the buffer and the file
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
    _open(app, target)
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
    """Open the editor scoped to `task`'s body (research R5), routing the same
    way `open_editor` does (research R1, contract C1). Never fails to open:
    the buffer is the dedented body text already held in memory, so there is
    no file read on the way in -- only the save can fail, and that is
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
    _open(app, target)


def _open(app: App[None], target: EditTarget) -> None:
    """Route an edit session by the active screen (research R1, contract C1):
    inline in `#preview-pane` when `ListScreen` is active, full-screen
    otherwise. The only place `open_editor`/`open_task_editor` diverge --
    deferred import to avoid a cycle, since `ListScreen` imports from this
    module at its own top level."""
    from choom.tui.list_screen import ListScreen

    if isinstance(app.screen, ListScreen):
        app.screen.open_inline_editor(target)
        return
    app.push_screen(EditScreen(target))


def open_editors(app: App[None]) -> list[EditorPane]:
    """Every mounted `EditorPane` across the screen stack (research R9) --
    inline or full-screen, whichever is open. After R1 an editor's dirty state
    lives on the pane, not the screen, so `ChoomApp.action_quit` (bug #64) and
    `ChoomApp.toggle_task_and_track` both consume this rather than scanning for
    an `EditScreen` -- missing either one is a silent data-loss bug."""
    panes: list[EditorPane] = []
    for screen in app.screen_stack:
        panes.extend(screen.query(EditorPane))
    return panes


def _reply_capture_note(capture: ReplyCapture) -> tuple[str | None, bool]:
    """The status note and its `warn` flag for a reply's capture result
    (contracts/reply-capture.md §4). No eligible line at all is exactly
    today's plain footer -- `(None, False)`. All captured is news, not a
    warning. Any failure, partial or total, carries `⚠` and names the first
    reason; the count in front of it, when there is one, carries the rest."""
    if not capture.tasks and not capture.warnings:
        return None, False
    captured = f"{len(capture.tasks)} {'task' if len(capture.tasks) == 1 else 'tasks'} captured"
    if not capture.warnings:
        return captured, False
    if not capture.tasks:
        return capture.warnings[0].message, True
    return (
        f"{captured}; {len(capture.warnings)} could not be: {capture.warnings[0].message}",
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


class EditorPane(Vertical):
    """Everything an edit session needs: the `EditorTextArea`, the save/discard
    path, the mirror baseline, and the `/ai` request machinery (research R1).
    Mounted by `EditScreen` (full-screen) or by `ListScreen` inline in
    `#preview-pane` -- one implementation, two hosts, so "identical capability
    inline and full-screen" (FR-019) holds by construction rather than by
    vigilance.

    Closing is host-specific, so this widget never pops a screen or unmounts
    itself -- it posts `Closed` and lets whichever host mounted it decide.
    """

    # TextArea itself binds ctrl+s/ctrl+x (cut); `priority=True` means these are
    # checked from the app down to the focused widget, before TextArea's own
    # bindings, so they aren't shadowed by the focused editor (e.g. TextArea's
    # built-in ctrl+x -> cut). research R3.
    BINDINGS = [
        Binding("ctrl+o", "save", "Save", show=True, priority=True),
        Binding("ctrl+s", "save", "Save", show=False, priority=True),
        Binding("ctrl+x", "save_and_close", "Save & close", show=True, priority=True),
        Binding("escape", "close", "Discard", show=True),
        # The one justified deviation from Principle V's ctrl+c/ctrl+q reservation
        # (plan Complexity Tracking): active only while a request is in flight, and
        # the cancel hint is on screen for the whole wait via in_flight_status().
        Binding("ctrl+c", "cancel_request", "Cancel", show=False, priority=True),
        # Neither key is bound by TextArea (`tab_behavior="focus"` deliberately
        # lets both through) -- without a no-op here, tab would switch the
        # collection (inline) or move focus off the editor (research R2,
        # FR-006/FR-007).
        Binding("tab", "noop", show=False),
        Binding("shift+tab", "noop", show=False),
    ]

    class Closed(Message):
        """Posted instead of popping a screen or unmounting -- the host
        decides how the pane disappears (research R1)."""

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
        # "since they last agreed", held for the life of this pane and never
        # persisted (research R4). Seeded from the already-reconciled text the
        # pane was constructed with, so a correction applied at open is never
        # mistaken at save time for an edit the user made (US5/US6).
        self._mirror_baseline: dict[str, bool] = {
            m.task_id: m.done for m in find_mirrors(target.text, source=target.display_path)
        }
        #: The line a pending `/link` picker choice would replace, or None
        #: when no choice is pending -- the one field every guard around the
        #: picker tests (data-model.md "Selection list").
        self._link_picker_line: int | None = None

    @property
    def is_dirty(self) -> bool:
        return self.query_one("#editor", TextArea).text != self.original_text

    def compose(self) -> ComposeResult:
        yield EditorTextArea(self._padded_text, show_line_numbers=True, id="editor")

    def on_mount(self) -> None:
        editor = self.query_one("#editor", TextArea)
        editor.cursor_location = (self._cursor_row, 0)
        editor.focus()

    def on_resize(self, event: events.Resize) -> None:
        if self._request is not None:
            self._render_in_flight_status()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self._link_picker_line is not None and action in (
            "save",
            "save_and_close",
            "close",
            "cancel_request",
        ):
            # research R2: these bindings are `priority=True`, checked from the
            # app down regardless of focus, so they would otherwise fire
            # underneath the picker while a choice is pending. `escape` is not
            # priority and so would never reach here anyway (LinkPicker's own
            # binding claims it first), but the gate covers it too rather than
            # leaning on that as an implicit guarantee.
            return False
        if action == "cancel_request":
            return self._request is not None
        return True

    def action_noop(self) -> None:
        """Absorbs `tab`/`shift+tab` (research R2) -- bubbles no further, so
        neither key reaches a host screen's own binding."""

    def _render_status(self, note: str | None = None, *, warn: bool = True) -> None:
        status = self.screen.query_one(StatusBar)
        help_text = LINK_PICKER_HELP if self._link_picker_line is not None else EDIT_HELP
        if note is None:
            status.update(help_text)
            return
        prefix = "⚠ " if warn else ""
        status.update(f"{prefix}{note}   {help_text}")

    def _render_in_flight_status(self) -> None:
        if self._breadcrumb is None:
            return
        status = self.screen.query_one(StatusBar)
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
            self.post_message(self.Closed())

    def action_close(self) -> None:
        if not self.is_dirty:
            self.post_message(self.Closed())
            return

        def _handle_dismiss(discard: bool | None) -> None:
            if discard:
                self.post_message(self.Closed())
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
        candidates = link_candidates(workspace, parsed.argument)

        if not candidates:
            self._render_status(link_no_match_status(parsed.argument))
            return
        if len(candidates) == 1:
            self._replace_link_line(line_index, candidates[0].target)
            self._render_status(None)
            return

        if self.screen.size.height < MIN_PICKER_SCREEN_HEIGHT:
            # research R7, FR-017: too little room for a usable list -- the
            # honest fallback that predates the picker, not a degraded one.
            self._render_status(link_ambiguous_status([c.target.title for c in candidates]))
            return

        self._open_link_picker(line_index, candidates)

    def _replace_link_line(self, line_index: int, target: LinkTarget) -> None:
        """Replace `line_index` with a markdown link to `target`, using the
        same call the single-match fast path and the picker's `enter` both
        make, so the two can never format a link differently."""
        editor = self.query_one("#editor", EditorTextArea)
        original_line = editor.get_line(line_index).plain
        link_text = format_link(self.target.display_path, target, target.title)
        editor.replace(
            link_text,
            (line_index, 0),
            (line_index, len(original_line)),
            maintain_selection_offset=False,
        )

    def _open_link_picker(self, line_index: int, candidates: tuple[LinkCandidate, ...]) -> None:
        """Raise the picker for an ambiguous `/link` (research R1, R2,
        FR-001): candidates set, first row highlighted, focus moved to the
        list, footer swapped to `LINK_PICKER_HELP`. `EditorPane` reaches the
        picker through `self.screen`, the same idiom `_render_status` already
        uses for `StatusBar` -- one code path serves both hosts (FR-004)."""
        picker = self.screen.query_one(LinkPicker)
        self._link_picker_line = line_index
        picker.open(candidates)
        picker.focus()
        self._render_status(None)

    def _close_link_picker(self) -> None:
        """Hide the picker, drop the remembered line, and return focus to the
        editor -- the common tail of every transition out of `open` (data-
        model.md "Selection list")."""
        self.screen.query_one(LinkPicker).close()
        self._link_picker_line = None
        self.query_one("#editor", TextArea).focus()

    def handle_link_chosen(self, candidate: LinkCandidate) -> None:
        """`LinkPicker.Chosen` (contract C5, research R8): re-resolve the
        candidate's id -- the workspace is a folder another program can
        change between listing and choosing -- and insert from the freshly
        resolved target when it still resolves. If it does not, report and
        leave the line as typed rather than write a link to nothing (FR-015).
        Called by whichever host screen caught the bubbled message."""
        line_index = self._link_picker_line
        assert line_index is not None, "Chosen fired with no picker open"
        workspace = self.app.workspace  # type: ignore[attr-defined]
        target, _warnings = resolve_id(workspace, candidate.target.id)
        self._close_link_picker()
        if target is None:
            self._render_status(f"{candidate.target.title!r} no longer exists; nothing inserted")
            return
        self._replace_link_line(line_index, target)
        self._render_status(None)

    def handle_link_cancelled(self, message: str | None) -> None:
        """`LinkPicker.Cancelled` (FR-008, research R9): close and leave the
        typed line exactly as it was. `message` carries the fallback status
        text when a resize closed the picker (contract C6); `None` for an
        ordinary `esc`, which restores the plain edit footer with no note."""
        self._close_link_picker()
        self._render_status(message)

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
            parsed.argument,
            self.target.display_path,
            self.target.ai_line_offset + line_index + 1,
            task_capture=self.target.captures_tasks,
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
                try:
                    document = _read_document(self.target.display_path)
                except OSError:
                    # Deleted or renamed while the assistant was working. `/task`
                    # reads the document it saved microseconds earlier; a reply is
                    # seconds or minutes later, so this window is real here.
                    document = None
                if document is None:
                    # No id to link a capture from -- the reply still lands in full,
                    # and a reply that wanted tasks says why it has none rather than
                    # leaving the user to notice (FR-017, FR-018).
                    if any(line.task is not None for line in parse_reply_lines(text)):
                        note, warn = (
                            "could not identify this document; task lines left as written",
                            True,
                        )
                else:
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


class EditScreen(Screen[None]):
    """A full-screen host for `EditorPane` -- used whenever an editor opens
    from a screen other than `ListScreen` (research R1, contract C1's last
    row). Composes the pane plus its own `StatusBar` and pops itself when the
    pane posts `Closed`; everything else is the pane's."""

    def __init__(self, target: EditTarget) -> None:
        super().__init__()
        self.pane = EditorPane(target)

    def compose(self) -> ComposeResult:
        yield self.pane
        with Vertical(id="bottom-bar"):
            yield LinkPicker(id="link-picker")
            yield StatusBar(EDIT_HELP, id="status-bar")

    @on(EditorPane.Closed)
    def _on_editor_pane_closed(self, message: EditorPane.Closed) -> None:
        self.app.pop_screen()

    # `LinkPicker` is composed into this screen's `#bottom-bar`, a sibling of
    # `self.pane` rather than its descendant, so its messages bubble here --
    # to the screen -- not to the pane. This mirrors `EditorPane.Closed` above
    # in reverse: there the pane is the ancestor-facing widget and the screen
    # reacts; here the screen is what the picker's messages actually reach,
    # and it delegates to the pane, which holds the state to act on them.

    @on(LinkPicker.Chosen)
    def _on_link_chosen(self, message: LinkPicker.Chosen) -> None:
        self.pane.handle_link_chosen(message.candidate)

    @on(LinkPicker.Cancelled)
    def _on_link_cancelled(self, message: LinkPicker.Cancelled) -> None:
        self.pane.handle_link_cancelled(message.message)
