from __future__ import annotations

from datetime import datetime

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListView, MeetingRow


async def test_meetings_listed_date_descending(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "oldest", now=datetime(2026, 7, 20, 9, 0, 0))
    create_meeting(tmp_workspace, "middle", now=datetime(2026, 7, 25, 9, 0, 0))
    create_meeting(tmp_workspace, "newest", now=datetime(2026, 7, 28, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.meeting.title for row in list_view.children if isinstance(row, MeetingRow)]
        assert titles == ["newest", "middle", "oldest"]


async def test_filter_narrows_visible_rows_live(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "vendor renewal", tags=("procurement",))
    create_meeting(tmp_workspace, "standup", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        for ch in "vendor":
            await pilot.press(ch)
        await pilot.pause()

        assert len(app.visible_meetings) == 1
        assert app.visible_meetings[0].title == "vendor renewal"


async def test_navigation_stops_at_ends_without_wrapping(tmp_workspace: Workspace) -> None:
    for i in range(3):
        create_meeting(tmp_workspace, f"meeting {i}", now=datetime(2026, 7, 20 + i, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)

        await pilot.press("j")
        await pilot.press("k", "k", "k", "k")
        await pilot.pause()
        assert list_view.index == 0

        await pilot.press("j", "j", "j", "j", "j")
        await pilot.pause()
        assert list_view.index == 2
