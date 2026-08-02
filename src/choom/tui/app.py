from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from textual.app import App
from textual.binding import Binding

from choom.core.assistants import resolve_assistant
from choom.core.config import (
    LEGAL_ASSISTANT_VALUES,
    get_assistant,
    set_assistant,
    set_launch_offer_made,
)
from choom.core.discovery import (
    install_discovery_file,
    remove_discovery_files,
    should_offer_discovery,
)
from choom.core.documents import (
    list_months,
    match_document,
    scan_documents,
    scan_month,
    scan_unfiled,
)
from choom.core.errors import ChoomError, UsageError, WorkspaceError
from choom.core.meetings import MEETINGS, create_meeting
from choom.core.mirrors import propagate_to_documents
from choom.core.models import (
    AssistantProfile,
    Collection,
    DailyNote,
    Document,
    MonthListing,
    ScanWarning,
    Task,
    TaskFilter,
    Workspace,
    YearMonth,
)
from choom.core.notes import NOTES, create_note, open_daily_note
from choom.core.tasks import (
    add_task,
    filter_tasks,
    get_task,
    load_tasks,
    match_task,
    set_task_state,
)

if TYPE_CHECKING:
    from choom.tui.list_screen import ListScreen

DOCUMENT_COLLECTIONS: dict[str, Collection] = {"meetings": MEETINGS, "notes": NOTES}
ScopeSelection = YearMonth | Literal["unfiled"]


def _current_month() -> YearMonth:
    today = date.today()
    return YearMonth(today.year, today.month)


def _month_of(path: Path) -> YearMonth | None:
    """The YearMonth implied by a document's path, or None if it is unfiled."""
    try:
        month = int(path.parent.name)
        year = int(path.parent.parent.name)
    except ValueError:
        return None
    if not (1 <= month <= 12):
        return None
    return YearMonth(year, month)


class ChoomApp(App[None]):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, workspace: Workspace) -> None:
        super().__init__()
        self.workspace = workspace
        self.active: str = "tasks"

        # Notes/Meetings: which month (or "unfiled") the scope pane shows.
        self.month_scope: dict[str, YearMonth] = {}
        self.scope_selection: dict[str, ScopeSelection] = {}

        # Tasks: which category the scope pane shows.
        self.task_category: str = "todo"

        self.filter_query: str = ""
        self.pre_filter_scope: YearMonth | None = None

        self.last_create_error: str | None = None
        self.last_task_error: str | None = None

        # Warnings from the most recent `visible_documents()`/`visible_tasks()`
        # read -- render output, not a source of truth (research R3, data-model
        # §3.3). Read by `visible_warnings()`; never consulted for anything else.
        self._last_warnings: list[ScanWarning] = []

        #: The one `ListScreen` this session ever pushes (research R6) -- kept so the
        #: launch offer's dismiss callback, which fires from here rather than from the
        #: screen itself, has somewhere to hand its outcome via `set_pending_status`.
        self._list_screen: ListScreen | None = None

        for name in DOCUMENT_COLLECTIONS:
            self._reset_scope(name)

    def on_mount(self) -> None:
        from choom.tui.list_screen import ListScreen

        self._list_screen = ListScreen()
        self.push_screen(self._list_screen)
        # Deferred past the first refresh (FR-034): the list must be up and painted
        # behind the question before it appears (research R6).
        self.call_after_refresh(self._maybe_offer_discovery)

    def _maybe_offer_discovery(self) -> None:
        """Raise the once-only launch offer if `should_offer_discovery` says to
        (US2). Runs once, from `on_mount`, never from `ListScreen` itself -- that
        screen is re-entered on every resume, and raising it there would need its own
        suppression logic to avoid re-asking within one run (research R6)."""
        from choom.tui.confirm_dialog import ConfirmDialog

        configured = get_assistant(self.workspace)
        resolved = resolve_assistant(configured)
        profile = should_offer_discovery(self.workspace, resolved)
        if profile is None:
            return

        dialog = ConfirmDialog(
            f"Let {profile.display_name} know this workspace is at {self.workspace.root}?",
            cancel_label="Not Now",
            confirm_label="Tell It",
        )

        def _handle_dismiss(confirmed: bool | None) -> None:
            self._resolve_launch_offer(profile, confirmed=bool(confirmed))

        self.push_screen(dialog, _handle_dismiss)

    def _resolve_launch_offer(self, profile: AssistantProfile, *, confirmed: bool) -> None:
        """`Enter` installs the file exactly as the set command does and records the
        assistant as the workspace's setting (FR-025); `Esc` installs nothing and
        writes nothing into the user's profile (FR-026). Either way,
        `launch_offer_made` is recorded so the question is never asked again
        (FR-027) -- including when the install itself fails, so a permanently
        unwritable profile directory does not raise the same question at every
        launch (research R7)."""
        message: str | None = None
        if confirmed:
            set_assistant(self.workspace, profile.name)
            try:
                path = install_discovery_file(self.workspace, profile)
            except WorkspaceError as exc:
                message = f"could not tell {profile.display_name}: {exc}"
            else:
                message = (
                    f"told {profile.display_name} about this workspace"
                    if path is not None
                    else f"assistant set to {profile.name}; no discovery file for {profile.name}"
                )

        try:
            set_launch_offer_made(self.workspace, True)
        except WorkspaceError:
            pass

        if self._list_screen is not None:
            self._list_screen.set_pending_status(message)

    async def action_quit(self) -> None:
        """`ctrl+q` (bug #64): quit immediately when nothing would be lost, exactly
        as before -- but if a dirty editor is on the stack, inline or full-screen,
        raise the same confirmation `EditorPane.action_close` raises rather than
        silently discarding the edit (constitution Principle V, amended 2.0.0)."""
        from choom.tui.confirm_dialog import ConfirmDialog
        from choom.tui.edit_screen import open_editors

        if isinstance(self.screen, ConfirmDialog):
            return  # already confirming a quit or a close; don't stack a second dialog

        dirty = any(pane.is_dirty for pane in open_editors(self))
        if not dirty:
            self.exit()
            return

        def _handle_dismiss(discard: bool | None) -> None:
            if discard:
                self.exit()

        dialog = ConfirmDialog(
            "You have unsaved changes. Are you sure you want to exit?",
            cancel_label="Continue Editing",
            confirm_label="Exit Without Saving",
        )
        self.push_screen(dialog, _handle_dismiss)

    # --- scope (month / unfiled / category) -----------------------------------

    def _reset_scope(self, collection: str) -> None:
        current = _current_month()
        self.month_scope[collection] = current
        self.scope_selection[collection] = current

    def list_scope(self, collection: str) -> MonthListing:
        return list_months(self.workspace, DOCUMENT_COLLECTIONS[collection])

    def collection_descriptor(self, collection: str) -> Collection:
        """The scan-path descriptor for `collection` -- exposed so `ListScreen`
        can hydrate a filter pool on a worker thread (research R6) without
        reaching into this module's private `DOCUMENT_COLLECTIONS` mapping."""
        return DOCUMENT_COLLECTIONS[collection]

    def select_scope(self, collection: str, selection: ScopeSelection) -> None:
        self.scope_selection[collection] = selection
        if isinstance(selection, YearMonth):
            self.month_scope[collection] = selection

    def visible_documents(self) -> list[Document]:
        """The documents the active collection's current scope displays, read
        fresh from disk on every call (010-read-on-load, contract C1/C3). A
        list load stays scoped to what it displays -- one month, or the
        unfiled set -- never the whole collection; only a filter reads every
        month (research R2)."""
        collection = self.active
        if collection == "tasks":
            return []
        if self.filter_query:
            return self._filtered_documents(collection)
        selection = self.scope_selection.get(collection, self.month_scope[collection])
        if selection == "unfiled":
            documents, self._last_warnings = scan_unfiled(
                self.workspace, DOCUMENT_COLLECTIONS[collection]
            )
            return documents
        month = selection if isinstance(selection, YearMonth) else self.month_scope[collection]
        documents, self._last_warnings = scan_month(
            self.workspace, DOCUMENT_COLLECTIONS[collection], month
        )
        return documents

    def _filtered_documents(self, collection: str) -> list[Document]:
        """A filter reads every month of the collection plus unfiled (FR-015,
        FR-017) -- the one read that is not scoped to a single month. This is
        the fallback path: `ListScreen` normally supplies an already-hydrated
        pool to `match_documents` directly, from the worker started when the
        command bar opened (research R6), bypassing this scan entirely for
        every keystroke after the first. This method still exists for any
        caller without a hydration session -- direct app use, and the first
        render before a worker has finished.

        One `scan_documents` walk, not a `scan_month` per month plus
        `scan_unfiled`: reading the whole collection is a thing `core` already
        knows how to do, and it is what the CLI's `scan_meetings`/`scan_notes`
        call for the same question (Principle I, Principle II). Assembling the
        same set here from month-scoped pieces re-implemented core in the
        adapter and cost more -- the loop re-walks the tree once to enumerate
        months, once per month, and once again for unfiled."""
        pool, warnings = scan_documents(self.workspace, DOCUMENT_COLLECTIONS[collection])
        self._last_warnings = warnings
        return self.match_documents(pool)

    def match_documents(self, pool: list[Document]) -> list[Document]:
        """Match `pool` against the active filter term and sort it exactly as
        `_filtered_documents` sorts a fresh scan -- shared so a caller holding
        an already-hydrated pool (`ListScreen`'s command-bar session) gets
        identical ordering without re-implementing it."""
        matches = [d for d in pool if match_document(d, self.filter_query)]
        matches.sort(key=lambda d: str(d.path))
        matches.sort(key=lambda d: d.created, reverse=True)
        return matches

    def visible_warnings(self) -> list[ScanWarning]:
        """The warnings produced by the read that populated the rows currently
        on screen -- not a fresh scan of its own (research R3). Only
        meaningful right after `visible_documents()`/`visible_tasks()` ran;
        `ListScreen` is the one caller, via `refresh_rows`."""
        return list(self._last_warnings)

    def visible_tasks(self) -> list[Task]:
        """Every task the active category (and filter, if any) shows, read
        fresh from `tasks.md` on every call (010-read-on-load, contract C1)."""
        tasks, self._last_warnings = load_tasks(self.workspace)
        task_filter = TaskFilter(only_done=self.task_category == "done")
        tasks = filter_tasks(tasks, task_filter)
        if self.filter_query:
            tasks = [t for t in tasks if match_task(t, self.filter_query)]
        return tasks

    def set_filter(self, query: str) -> None:
        """Apply (or clear) the cross-month filter (FR-029-034). Notes/Meetings
        capture the pre-filter month so clearing restores it; Tasks has no month
        scope to restore."""
        collection = self.active
        was_active = bool(self.filter_query)
        now_active = bool(query)
        if collection != "tasks":
            if now_active and not was_active:
                self.pre_filter_scope = self.month_scope[collection]
            elif not now_active and was_active:
                restore = self.pre_filter_scope or self.month_scope[collection]
                self.scope_selection[collection] = restore
                self.pre_filter_scope = None
        self.filter_query = query

    # --- collection switching --------------------------------------------------

    def switch_collection(self, name: str) -> None:
        self.active = name
        self.filter_query = ""
        self.pre_filter_scope = None
        if name == "tasks":
            self.task_category = "todo"
        else:
            self._reset_scope(name)

    # --- create flows ------------------------------------------------------

    def create_meeting_and_track(self, description: str, type: str) -> Document | None:
        try:
            meeting = create_meeting(self.workspace, description, type=type)
        except UsageError as exc:
            self.last_create_error = str(exc)
            return None
        self.last_create_error = None
        self._track_created("meetings", meeting)
        return meeting

    def create_note_and_track(self, description: str, type: str) -> Document | None:
        try:
            note = create_note(self.workspace, description, type=type)
        except UsageError as exc:
            self.last_create_error = str(exc)
            return None
        self.last_create_error = None
        self._track_created("notes", note)
        return note

    def open_daily_note_and_track(self, *, now: datetime | None = None) -> DailyNote:
        daily = open_daily_note(self.workspace, now=now)
        if daily.created and daily.document is not None:
            self._track_created("notes", daily.document)
        else:
            self.active = "notes"
            self.filter_query = ""
            month = _month_of(daily.path) or _current_month()
            self.select_scope("notes", month)
        return daily

    def _track_created(self, collection: str, document: Document) -> None:
        month = _month_of(document.path) or _current_month()
        self.active = collection
        self.filter_query = ""
        self.select_scope(collection, month)

    def add_task_and_track(self, description: str, type: str) -> Task | None:
        """Adding a task is a quick capture, not a navigation: it never changes
        the active collection. When Tasks is already active, land on To-Do with
        the new task highlighted (spec US3 scenario 6); from any other
        collection, the task is filed in the background and the current view
        is left exactly as it was."""
        try:
            task = add_task(self.workspace, description, type=type)
        except UsageError as exc:
            self.last_create_error = str(exc)
            return None
        self.last_create_error = None
        if self.active == "tasks":
            self.task_category = "todo"
            self.filter_query = ""
        return task

    # --- /config command bar verb ------------------------------------------

    def handle_config_command(self, argument: str) -> str | None:
        """Handle `/config <setting> [<value>]` from the command bar (research
        R11). Returns a status-bar message; a set always reports the discovery-file
        outcome (FR-015), matching the CLI peer's stderr line in substance -- the two
        interfaces report the same result in their own idiom."""
        setting_name, _, value = argument.partition(" ")
        if setting_name != "assistant":
            return f"unknown setting: {setting_name!r}"

        if not value:
            configured = get_assistant(self.workspace)
            resolved = resolve_assistant(configured)
            resolved_name = resolved.profile.name if resolved.profile is not None else "none"
            accepted = ", ".join(LEGAL_ASSISTANT_VALUES)
            return (
                f"assistant: {configured or 'unset'} (resolved: {resolved_name}); "
                f"accepted: {accepted}"
            )

        if value not in LEGAL_ASSISTANT_VALUES:
            accepted = ", ".join(LEGAL_ASSISTANT_VALUES)
            return f"assistant must be one of {accepted}; got {value!r}"

        set_assistant(self.workspace, value)
        # An explicit set outranks an earlier declined launch offer (FR-028); see
        # the CLI's _report_discovery_outcome for why this is best-effort.
        try:
            set_launch_offer_made(self.workspace, False)
        except WorkspaceError:
            pass
        return self._describe_discovery_outcome(value)

    def _describe_discovery_outcome(self, value: str) -> str:
        """The discovery-file side effect of a successful `/config assistant <value>`,
        worded for the status bar (FR-014, FR-015) -- the TUI's peer to the CLI's
        `_report_discovery_outcome`. `none` removes every choom-owned file (FR-009);
        any other legal value installs the file for that assistant."""
        if value == "none":
            removed, warnings = remove_discovery_files()
            if warnings:
                return "; ".join(warnings)
            return (
                "assistant set to none; discovery file removed"
                if removed
                else "assistant set to none"
            )

        profile = resolve_assistant(value).profile
        assert profile is not None  # value is "claude" or "copilot" here
        try:
            path = install_discovery_file(self.workspace, profile)
        except WorkspaceError as exc:
            return f"assistant set to {value}; discovery file not installed: {exc}"
        if path is None:
            return f"assistant set to {value}; no discovery file for {value}"
        return f"assistant set to {value}; discovery file installed at {path}"

    def toggle_task_and_track(self, task_id: str) -> None:
        """Flip one task's state and, once that write has succeeded, push it
        into every document the task links to (FR-021, FR-032). `tasks.md` is
        written first and is never reversed by a document failure; a document
        open with unsaved changes is skipped and picked up at the user's next
        save instead (FR-033) -- the screen stack is what knows which those
        are, so this supplies `skip` rather than core discovering it.

        Reads the task's current state fresh rather than from any retained
        copy (010-read-on-load, research R8) -- there is nothing to keep in
        sync with disk, so nothing here can go stale."""
        try:
            current = get_task(self.workspace, task_id)
            updated = set_task_state(self.workspace, task_id, done=not current.done)
        except ChoomError as exc:
            self.last_task_error = str(exc)
            return
        self.last_task_error = None

        from choom.tui.edit_screen import open_editors

        skip = tuple(pane.target.display_path for pane in open_editors(self) if pane.is_dirty)
        _written, warnings = propagate_to_documents(self.workspace, updated, skip=skip)
        if warnings:
            self.last_task_error = "; ".join(w.message for w in warnings)
