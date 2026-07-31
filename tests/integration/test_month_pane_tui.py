from __future__ import annotations

from datetime import datetime

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace, YearMonth
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import DocumentRow, ListView
from endpaper.tui.scope_pane import MonthRow
from endpaper.tui.status_bar import StatusBar


def _one_month_before(dt: datetime) -> datetime:
    if dt.month == 1:
        return dt.replace(year=dt.year - 1, month=12, day=1)
    return dt.replace(month=dt.month - 1, day=1)


async def _to_meetings(pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.pause()
    await pilot.press("tab", "tab")  # tasks -> notes -> meetings
    await pilot.pause()


async def test_current_month_is_highlighted_on_selection(tmp_workspace: Workspace) -> None:
    now = datetime.now()
    create_meeting(tmp_workspace, "this month", now=now)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        scope_list = app.screen.query_one("#scope-list", ListView)
        highlighted = scope_list.highlighted_child
        assert isinstance(highlighted, MonthRow)
        assert highlighted.month == YearMonth(now.year, now.month)


async def test_moving_the_month_highlight_refills_list_and_preview_without_moving_focus(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    last_month = _one_month_before(now)
    create_meeting(tmp_workspace, "this month meeting", now=now)
    create_meeting(tmp_workspace, "last month meeting", now=last_month)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["this month meeting"]

        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # move to the next (older) month row
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        titles = [row.document.title for row in list_view.children if isinstance(row, DocumentRow)]
        assert titles == ["last month meeting"]

        scope_list = app.screen.query_one("#scope-list", ListView)
        assert scope_list.has_focus


async def test_empty_current_month_shows_a_month_scoped_empty_state(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    last_month = _one_month_before(now)
    create_meeting(tmp_workspace, "last month meeting", now=last_month)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        list_view = app.screen.query_one("#meeting-list", ListView)
        labels = [str(item.children[0].content) for item in list_view.children]  # type: ignore[attr-defined]
        month = YearMonth(now.year, now.month)
        assert labels == [
            f"No meetings in {month}. Press / then 'meeting <description>' to create one."
        ]


async def test_warning_count_is_per_month(tmp_workspace: Workspace) -> None:
    now = datetime.now()
    last_month = _one_month_before(now)
    bad_dir = tmp_workspace.meetings_dir / f"{last_month:%Y}" / f"{last_month:%m}"
    bad_dir.mkdir(parents=True)
    (bad_dir / "broken.md").write_text("no frontmatter here", encoding="utf-8")
    create_meeting(tmp_workspace, "this month meeting", now=now)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        status = app.screen.query_one(StatusBar)
        assert "warning" not in str(status.content)

        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")
        await pilot.pause()

        status = app.screen.query_one(StatusBar)
        assert "1 warning" in str(status.content)


async def test_returning_to_a_collection_resets_to_the_current_month(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.now()
    last_month = _one_month_before(now)
    create_meeting(tmp_workspace, "this month meeting", now=now)
    create_meeting(tmp_workspace, "last month meeting", now=last_month)

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")
        await pilot.pause()
        assert app.scope_selection["meetings"] == YearMonth(last_month.year, last_month.month)

        await pilot.press("l")
        await pilot.pause()
        await pilot.press("tab", "tab")  # meetings -> tasks -> notes
        await pilot.pause()
        await pilot.press("tab")  # notes -> meetings
        await pilot.pause()

        assert app.active == "meetings"
        assert app.scope_selection["meetings"] == YearMonth(now.year, now.month)
