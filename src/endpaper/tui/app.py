from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from endpaper.core.errors import UsageError
from endpaper.core.meetings import create_meeting, match_meeting, scan_meetings
from endpaper.core.models import Meeting, ScanWarning, Workspace


class EndpaperApp(App[None]):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, workspace: Workspace) -> None:
        super().__init__()
        self.workspace = workspace
        self.meetings: list[Meeting] = []
        self.warnings: list[ScanWarning] = []
        self.visible_meetings: list[Meeting] = []

    def on_mount(self) -> None:
        self.meetings, self.warnings = scan_meetings(self.workspace)
        self.visible_meetings = list(self.meetings)

        from endpaper.tui.list_screen import ListScreen

        self.push_screen(ListScreen())

    def apply_filter(self, query: str) -> None:
        if query:
            self.visible_meetings = [m for m in self.meetings if match_meeting(m, query)]
        else:
            self.visible_meetings = list(self.meetings)

    def create_meeting_and_track(self, description: str, type: str) -> Meeting | None:
        try:
            meeting = create_meeting(self.workspace, description, type=type)
        except UsageError:
            return None
        self.meetings.insert(0, meeting)
        self.visible_meetings = list(self.meetings)
        return meeting
