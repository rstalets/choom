from __future__ import annotations

from datetime import datetime

from textual.app import App
from textual.binding import Binding

from endpaper.core.documents import match_document
from endpaper.core.errors import UsageError
from endpaper.core.meetings import create_meeting, scan_meetings
from endpaper.core.models import DailyNote, Document, ScanWarning, Workspace
from endpaper.core.notes import create_note, open_daily_note, scan_notes


class EndpaperApp(App[None]):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, workspace: Workspace) -> None:
        super().__init__()
        self.workspace = workspace
        self.documents: dict[str, list[Document]] = {"meetings": [], "notes": []}
        self.warnings: dict[str, list[ScanWarning]] = {"meetings": [], "notes": []}
        self.active: str = "meetings"
        self.visible_documents: list[Document] = []
        self.last_create_error: str | None = None

    def on_mount(self) -> None:
        self.documents["meetings"], self.warnings["meetings"] = scan_meetings(self.workspace)
        self.documents["notes"], self.warnings["notes"] = scan_notes(self.workspace)
        self.visible_documents = list(self.documents[self.active])

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
        active_documents = self.documents[self.active]
        if query:
            self.visible_documents = [d for d in active_documents if match_document(d, query)]
        else:
            self.visible_documents = list(active_documents)

    def switch_collection(self, name: str) -> None:
        self.active = name
        self.visible_documents = list(self.documents[self.active])

    def create_meeting_and_track(self, description: str, type: str) -> Document | None:
        try:
            meeting = create_meeting(self.workspace, description, type=type)
        except UsageError as exc:
            self.last_create_error = str(exc)
            return None
        self.last_create_error = None
        self.documents["meetings"].insert(0, meeting)
        if self.active == "meetings":
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
        if self.active == "notes":
            self.visible_documents = list(self.documents["notes"])
        return note

    def open_daily_note_and_track(self, *, now: datetime | None = None) -> DailyNote:
        daily = open_daily_note(self.workspace, now=now)
        if daily.created and daily.document is not None:
            self.documents["notes"].insert(0, daily.document)
            if self.active == "notes":
                self.visible_documents = list(self.documents["notes"])
        return daily
