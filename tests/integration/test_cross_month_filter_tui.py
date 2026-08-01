from __future__ import annotations

from datetime import datetime

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.list_screen import ListView
from choom.tui.scope_pane import SuspendedRow
from tests.helpers import row_titles, to_collection, type_command


async def test_filter_matches_documents_from_other_months_newest_first(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    older = now.replace(year=now.year - 1) if now.month != 2 or now.day < 29 else now
    create_meeting(tmp_workspace, "vendor renewal", now=older)
    create_meeting(tmp_workspace, "vendor followup", now=now)
    create_meeting(tmp_workspace, "standup", type="standup", now=now)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "filter vendor")

        assert row_titles(app) == ["vendor followup", "vendor renewal"]


async def test_scope_pane_shows_suspended_while_filter_is_active(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "vendor renewal")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "filter vendor")

        scope_list = app.screen.query_one("#scope-list", ListView)
        assert any(isinstance(row, SuspendedRow) for row in scope_list.children)


async def test_opening_a_cross_month_match_and_returning_keeps_the_results(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    older = now.replace(year=now.year - 1) if now.month != 2 or now.day < 29 else now
    create_meeting(tmp_workspace, "vendor renewal", now=older)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "filter vendor")

        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len(list_view.children) == 1

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.filter_query == "vendor"
        assert row_titles(app) == ["vendor renewal"]
