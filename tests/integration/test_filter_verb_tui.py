from __future__ import annotations

from datetime import datetime

import pytest

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace, YearMonth
from endpaper.core.notes import create_note
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import DocumentRow, ListView
from tests.helpers import row_titles, to_collection, type_command, type_literally

_CREATE = {"meetings": create_meeting, "notes": create_note}


@pytest.mark.parametrize("collection", ["meetings", "notes"])
async def test_filter_narrows_live(tmp_workspace: Workspace, collection: str) -> None:
    """One end-to-end path for "narrows as you type", parametrized across
    collections. Kept on `type_literally` deliberately -- this is the test that
    would catch a regression in `type_command`'s single-assignment shortcut.
    """
    create = _CREATE[collection]
    create(tmp_workspace, "vendor renewal", tags=("procurement",))
    create(tmp_workspace, "standup", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, collection)
        await pilot.press("/")
        await pilot.pause()
        await type_literally(pilot, "filter vendor")
        await pilot.pause()

        assert row_titles(app) == ["vendor renewal"]


async def test_filter_alias_f_narrows_identically(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "vendor renewal", tags=("procurement",))
    create_meeting(tmp_workspace, "standup", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "f vendor")

        assert row_titles(app) == ["vendor renewal"]


async def test_empty_term_clears_and_restores_the_displayed_month(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    create_meeting(tmp_workspace, "vendor renewal", now=now)
    create_meeting(tmp_workspace, "standup", type="standup", now=now)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        month = YearMonth(now.year, now.month)
        assert app.scope_selection["meetings"] == month

        await pilot.press("/")
        await pilot.pause()
        await type_literally(pilot, "filter vendor")
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert len(list_view.children) == 1

        for _ in range(len("vendor")):
            await pilot.press("backspace")  # back to "filter " -- verb complete, no term
        await pilot.pause()

        assert app.filter_query == ""
        assert app.scope_selection["meetings"] == month
        titles = row_titles(app)
        assert titles == ["standup", "vendor renewal"] or titles == ["vendor renewal", "standup"]


async def test_escape_clears_the_filter_and_restores_the_month(tmp_workspace: Workspace) -> None:
    now = datetime.now()
    create_meeting(tmp_workspace, "vendor renewal", now=now)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        month = YearMonth(now.year, now.month)

        await type_command(app, pilot, "filter nomatch", submit=False)
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert not any(isinstance(r, DocumentRow) for r in list_view.children)

        await pilot.press("escape")
        await pilot.pause()

        assert app.filter_query == ""
        assert app.scope_selection["meetings"] == month
        assert row_titles(app) == ["vendor renewal"]
