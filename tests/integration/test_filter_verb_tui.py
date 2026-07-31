from __future__ import annotations

from datetime import datetime

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace, YearMonth
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import DocumentRow, ListView


async def _to_meetings(pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.pause()
    await pilot.press("tab", "tab")  # tasks -> notes -> meetings
    await pilot.pause()


async def _type(pilot, text: str) -> None:  # type: ignore[no-untyped-def]
    for ch in text:
        await pilot.press("space" if ch == " " else ch)


async def test_filter_narrows_live(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "vendor renewal", tags=("procurement",))
    create_meeting(tmp_workspace, "standup", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "filter vendor")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor renewal"]


async def test_filter_alias_f_narrows_identically(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "vendor renewal", tags=("procurement",))
    create_meeting(tmp_workspace, "standup", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "f vendor")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor renewal"]


async def test_empty_term_clears_and_restores_the_displayed_month(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    create_meeting(tmp_workspace, "vendor renewal", now=now)
    create_meeting(tmp_workspace, "standup", type="standup", now=now)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        month = YearMonth(now.year, now.month)
        assert app.scope_selection["meetings"] == month

        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "filter vendor")
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len(list_view.children) == 1

        for _ in range(len("vendor")):
            await pilot.press("backspace")  # back to "filter " -- verb complete, no term
        await pilot.pause()

        assert app.filter_query == ""
        assert app.scope_selection["meetings"] == month
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["standup", "vendor renewal"] or titles == ["vendor renewal", "standup"]


async def test_escape_clears_the_filter_and_restores_the_month(tmp_workspace: Workspace) -> None:
    now = datetime.now()
    create_meeting(tmp_workspace, "vendor renewal", now=now)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        month = YearMonth(now.year, now.month)

        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "filter nomatch")
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert not any(isinstance(r, DocumentRow) for r in list_view.children)

        await pilot.press("escape")
        await pilot.pause()

        assert app.filter_query == ""
        assert app.scope_selection["meetings"] == month
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor renewal"]
