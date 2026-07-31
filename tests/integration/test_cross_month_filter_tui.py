from __future__ import annotations

from datetime import datetime

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import DocumentRow, ListView
from endpaper.tui.scope_pane import SuspendedRow


async def _to_meetings(pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.pause()
    await pilot.press("tab", "tab")  # tasks -> notes -> meetings
    await pilot.pause()


async def _type(pilot, text: str) -> None:  # type: ignore[no-untyped-def]
    for ch in text:
        await pilot.press("space" if ch == " " else ch)


async def test_filter_matches_documents_from_other_months_newest_first(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    older = now.replace(year=now.year - 1) if now.month != 2 or now.day < 29 else now
    create_meeting(tmp_workspace, "vendor renewal", now=older)
    create_meeting(tmp_workspace, "vendor followup", now=now)
    create_meeting(tmp_workspace, "standup", type="standup", now=now)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "filter vendor")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor followup", "vendor renewal"]


async def test_scope_pane_shows_suspended_while_filter_is_active(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "vendor renewal")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "filter vendor")
        await pilot.pause()

        scope_list = app.screen.query_one("#scope-list", ListView)
        assert any(isinstance(row, SuspendedRow) for row in scope_list.children)


async def test_opening_a_cross_month_match_and_returning_keeps_the_results(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    older = now.replace(year=now.year - 1) if now.month != 2 or now.day < 29 else now
    create_meeting(tmp_workspace, "vendor renewal", now=older)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "filter vendor")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len(list_view.children) == 1

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.filter_query == "vendor"
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["vendor renewal"]
