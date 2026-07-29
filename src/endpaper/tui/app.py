from __future__ import annotations

from datetime import datetime
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from endpaper.core.documents import _read_document, match_document
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
        self._filter_query: str = ""

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
        self._filter_query = query
        active_documents = self.documents[self.active]
        if query:
            self.visible_documents = [d for d in active_documents if match_document(d, query)]
        else:
            self.visible_documents = list(active_documents)

    def refresh_document(self, path: Path) -> None:
        """Re-parse only the one file that changed, in place, preserving list order.
        Never rescans the workspace (FR-021, FR-022)."""
        new_document = _read_document(path)
        for collection in ("meetings", "notes"):
            docs = self.documents[collection]
            index = next((i for i, d in enumerate(docs) if d.path == path), None)
            if index is None:
                continue
            if new_document is not None:
                docs[index] = new_document
            else:
                del docs[index]
            if collection == self.active:
                self._sync_visible(path, new_document)
            return

    def _sync_visible(self, path: Path, new_document: Document | None) -> None:
        index = next((i for i, d in enumerate(self.visible_documents) if d.path == path), None)
        if index is None:
            return
        still_matches = new_document is not None and (
            not self._filter_query or match_document(new_document, self._filter_query)
        )
        if still_matches:
            assert new_document is not None
            self.visible_documents[index] = new_document
        else:
            del self.visible_documents[index]

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
