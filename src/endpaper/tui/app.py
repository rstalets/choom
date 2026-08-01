from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from textual.app import App
from textual.binding import Binding

from endpaper.core.assistants import resolve_assistant
from endpaper.core.config import LEGAL_ASSISTANT_VALUES, get_assistant, set_assistant
from endpaper.core.documents import (
    _read_document,
    list_months,
    match_document,
    scan_month,
    scan_unfiled,
)
from endpaper.core.errors import EndpaperError, UsageError
from endpaper.core.meetings import MEETINGS, create_meeting
from endpaper.core.mirrors import propagate_to_documents
from endpaper.core.models import (
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
from endpaper.core.notes import NOTES, create_note, open_daily_note
from endpaper.core.tasks import add_task, filter_tasks, load_tasks, match_task, set_task_state

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


class EndpaperApp(App[None]):
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

        self.month_cache: dict[tuple[str, YearMonth], list[Document]] = {}
        self.month_warnings: dict[tuple[str, YearMonth], list[ScanWarning]] = {}
        self.unfiled_cache: dict[str, list[Document]] = {}
        self.unfiled_warnings: dict[str, list[ScanWarning]] = {}
        self.fully_loaded: set[str] = set()

        self.filter_query: str = ""
        self.pre_filter_scope: YearMonth | None = None
        self.filter_loading: bool = False

        self.last_create_error: str | None = None
        self.last_task_error: str | None = None

        self.tasks: list[Task] = []
        self.task_warnings: list[ScanWarning] = []

        for name in DOCUMENT_COLLECTIONS:
            self._reset_scope(name)

    def on_mount(self) -> None:
        self.tasks, self.task_warnings = load_tasks(self.workspace)

        from endpaper.tui.list_screen import ListScreen

        self.push_screen(ListScreen())

    # --- scope (month / unfiled / category) -----------------------------------

    def _reset_scope(self, collection: str) -> None:
        current = _current_month()
        self.month_scope[collection] = current
        self.scope_selection[collection] = current

    def list_scope(self, collection: str) -> MonthListing:
        return list_months(self.workspace, DOCUMENT_COLLECTIONS[collection])

    def select_scope(self, collection: str, selection: ScopeSelection) -> None:
        self.scope_selection[collection] = selection
        if isinstance(selection, YearMonth):
            self.month_scope[collection] = selection

    def _ensure_month_loaded(self, collection: str, month: YearMonth) -> None:
        key = (collection, month)
        if key in self.month_cache:
            return
        documents, warnings = scan_month(self.workspace, DOCUMENT_COLLECTIONS[collection], month)
        self.month_cache[key] = documents
        self.month_warnings[key] = warnings

    def _ensure_unfiled_loaded(self, collection: str) -> None:
        if collection in self.unfiled_cache:
            return
        documents, warnings = scan_unfiled(self.workspace, DOCUMENT_COLLECTIONS[collection])
        self.unfiled_cache[collection] = documents
        self.unfiled_warnings[collection] = warnings

    def visible_documents(self) -> list[Document]:
        collection = self.active
        if collection == "tasks":
            return []
        if self.filter_query:
            return self._filtered_documents(collection)
        selection = self.scope_selection.get(collection, self.month_scope[collection])
        if selection == "unfiled":
            self._ensure_unfiled_loaded(collection)
            return list(self.unfiled_cache[collection])
        month = selection if isinstance(selection, YearMonth) else self.month_scope[collection]
        self._ensure_month_loaded(collection, month)
        return list(self.month_cache[(collection, month)])

    def _filtered_documents(self, collection: str) -> list[Document]:
        """A filter reads every month of the collection (at most once per session,
        via the cache) rather than only the displayed one (FR-032, FR-035)."""
        for month in self.list_scope(collection).months:
            self._ensure_month_loaded(collection, month)
        self._ensure_unfiled_loaded(collection)
        self.fully_loaded.add(collection)

        pool: list[Document] = []
        for month in self.list_scope(collection).months:
            pool.extend(self.month_cache[(collection, month)])
        pool.extend(self.unfiled_cache[collection])

        matches = [d for d in pool if match_document(d, self.filter_query)]
        matches.sort(key=lambda d: str(d.path))
        matches.sort(key=lambda d: d.created, reverse=True)
        return matches

    def visible_warnings(self) -> list[ScanWarning]:
        collection = self.active
        if collection == "tasks":
            return list(self.task_warnings)
        if self.filter_query:
            return []
        selection = self.scope_selection.get(collection, self.month_scope[collection])
        if selection == "unfiled":
            return list(self.unfiled_warnings.get(collection, []))
        month = selection if isinstance(selection, YearMonth) else self.month_scope[collection]
        return list(self.month_warnings.get((collection, month), []))

    def visible_tasks(self) -> list[Task]:
        task_filter = TaskFilter(only_done=self.task_category == "done")
        tasks = filter_tasks(self.tasks, task_filter)
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

    # --- refresh after a save ---------------------------------------------------

    def reload_tasks(self) -> None:
        """Re-read tasks.md after a task-body save.

        A body write can shift the line of every task after it, and `load_tasks`
        is the only code that knows how to recompute the spans a splice just
        moved -- patching one task in place is not cheaper than re-parsing the
        one file (research R7). `ListScreen.on_screen_resume` re-selects by id
        once this returns.
        """
        self.tasks, self.task_warnings = load_tasks(self.workspace)

    def refresh_document(self, path: Path) -> None:
        """Re-parse only the one file that changed, in place -- never rescans the
        workspace (Principle IV)."""
        new_document = _read_document(path)
        for collection in DOCUMENT_COLLECTIONS:
            if collection == "notes":
                under = self.workspace.notes_dir
            else:
                under = self.workspace.meetings_dir
            try:
                path.relative_to(under)
            except ValueError:
                continue
            self._refresh_document_in(collection, path, new_document)
            return

    def _refresh_document_in(
        self, collection: str, path: Path, new_document: Document | None
    ) -> None:
        month = _month_of(path)
        if month is None:
            documents = self.unfiled_cache.get(collection)
            if documents is None:
                return
            index = next((i for i, d in enumerate(documents) if d.path == path), None)
            if index is None:
                if new_document is not None:
                    documents.insert(0, new_document)
                return
            if new_document is not None:
                documents[index] = new_document
            else:
                del documents[index]
            return

        key = (collection, month)
        documents = self.month_cache.get(key)
        if documents is None:
            return
        index = next((i for i, d in enumerate(documents) if d.path == path), None)
        if index is None:
            if new_document is not None:
                documents.insert(0, new_document)
            return
        if new_document is not None:
            documents[index] = new_document
        else:
            del documents[index]

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
        key = (collection, month)
        self.month_cache.setdefault(key, [])
        self.month_cache[key].insert(0, document)
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
        self.tasks.append(task)
        if self.active == "tasks":
            self.task_category = "todo"
            self.filter_query = ""
        return task

    # --- /config command bar verb ------------------------------------------

    def handle_config_command(self, argument: str) -> str | None:
        """Handle `/config <setting> [<value>]` from the command bar (research
        R11). Returns a status-bar message, or None on a silent successful
        write -- reading or a bad value always reports something, matching
        the CLI peer's behaviour (FR-025-029)."""
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
        return None

    def toggle_task_and_track(self, task_id: str) -> None:
        """Flip one task's state and, once that write has succeeded, push it
        into every document the task links to (FR-021, FR-032). `tasks.md` is
        written first and is never reversed by a document failure; a document
        open with unsaved changes is skipped and picked up at the user's next
        save instead (FR-033) -- the screen stack is what knows which those
        are, so this supplies `skip` rather than core discovering it."""
        current = next((t for t in self.tasks if t.id == task_id), None)
        try:
            updated = set_task_state(
                self.workspace, task_id, done=not (current.done if current else False)
            )
        except EndpaperError as exc:
            self.last_task_error = str(exc)
            return
        self.last_task_error = None
        self.tasks = [updated if t.id == task_id else t for t in self.tasks]

        from endpaper.tui.edit_screen import EditScreen

        skip = tuple(
            screen.target.display_path
            for screen in self.screen_stack
            if isinstance(screen, EditScreen) and screen.is_dirty
        )
        _written, warnings = propagate_to_documents(self.workspace, updated, skip=skip)
        if warnings:
            self.last_task_error = "; ".join(w.message for w in warnings)
