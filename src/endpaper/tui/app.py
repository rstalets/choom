from __future__ import annotations

from datetime import datetime

from textual.app import App
from textual.binding import Binding

from endpaper.core.documents import match_document
from endpaper.core.errors import EndpaperError, UsageError
from endpaper.core.meetings import create_meeting, scan_meetings
from endpaper.core.models import DailyNote, Document, ScanWarning, Task, TaskFilter, Workspace
from endpaper.core.notes import create_note, open_daily_note, scan_notes
from endpaper.core.tasks import add_task, filter_tasks, load_tasks, match_task, set_task_state


class EndpaperApp(App[None]):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, workspace: Workspace) -> None:
        super().__init__()
        self.workspace = workspace
        self.documents: dict[str, list[Document]] = {"meetings": [], "notes": []}
        self.warnings: dict[str, list[ScanWarning]] = {"meetings": [], "notes": [], "tasks": []}
        self.active: str = "meetings"
        self.visible_documents: list[Document] = []
        self.last_create_error: str | None = None
        self.tasks: list[Task] = []
        self.visible_tasks: list[Task] = []
        self.show_done: bool = False
        self.last_task_error: str | None = None
        self._task_filter_query: str = ""

    def on_mount(self) -> None:
        self.documents["meetings"], self.warnings["meetings"] = scan_meetings(self.workspace)
        self.documents["notes"], self.warnings["notes"] = scan_notes(self.workspace)
        self.tasks, self.warnings["tasks"] = load_tasks(self.workspace)
        self.visible_documents = list(self.documents[self.active])
        self._refresh_visible_tasks()

        from endpaper.tui.list_screen import ListScreen

        self.push_screen(ListScreen())

    # --- feature 001 compatibility aliases: back when there was only one
    # collection, these were plain attributes. Kept as properties so the
    # existing meeting-only tests keep working unedited.
    @property
    def meetings(self) -> list[Document]:
        return self.documents["meetings"]

    @property
    def visible_meetings(self) -> list[Document]:
        return self.visible_documents

    def apply_filter(self, query: str) -> None:
        if self.active == "tasks":
            self._task_filter_query = query
            self._refresh_visible_tasks()
            return
        active_documents = self.documents[self.active]
        if query:
            self.visible_documents = [d for d in active_documents if match_document(d, query)]
        else:
            self.visible_documents = list(active_documents)

    def switch_collection(self, name: str) -> None:
        self.active = name
        if name == "tasks":
            self._refresh_visible_tasks()
        else:
            self.visible_documents = list(self.documents[self.active])

    def _refresh_visible_tasks(self) -> None:
        task_filter = TaskFilter(include_done=self.show_done)
        filtered = filter_tasks(self.tasks, task_filter)
        if self._task_filter_query:
            filtered = [t for t in filtered if match_task(t, self._task_filter_query)]
        self.visible_tasks = filtered

    def create_meeting_and_track(self, description: str, type: str) -> Document | None:
        try:
            meeting = create_meeting(self.workspace, description, type=type)
        except UsageError as exc:
            self.last_create_error = str(exc)
            return None
        self.last_create_error = None
        self.documents["meetings"].insert(0, meeting)
        # Land back on the collection just created into, so escaping the preview
        # shows it -- a create is always followed by "let me see that".
        self.active = "meetings"
        self.visible_documents = list(self.documents["meetings"])
        return meeting

    def create_note_and_track(self, description: str, type: str) -> Document | None:
        try:
            note = create_note(self.workspace, description, type=type)
        except UsageError as exc:
            self.last_create_error = str(exc)
            return None
        self.last_create_error = None
        self.documents["notes"].insert(0, note)
        self.active = "notes"
        self.visible_documents = list(self.documents["notes"])
        return note

    def open_daily_note_and_track(self, *, now: datetime | None = None) -> DailyNote:
        daily = open_daily_note(self.workspace, now=now)
        if daily.created and daily.document is not None:
            self.documents["notes"].insert(0, daily.document)
        self.active = "notes"
        self.visible_documents = list(self.documents["notes"])
        return daily

    def add_task_and_track(self, description: str, type: str) -> Task | None:
        try:
            task = add_task(self.workspace, description, type=type)
        except UsageError as exc:
            self.last_create_error = str(exc)
            return None
        self.last_create_error = None
        self.tasks.append(task)
        self.active = "tasks"
        self._task_filter_query = ""
        self._refresh_visible_tasks()
        return task

    def toggle_task_and_track(self, task_id: str) -> None:
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
        self._refresh_visible_tasks()

    def toggle_show_done(self) -> None:
        self.show_done = not self.show_done
        self._refresh_visible_tasks()
