from __future__ import annotations

from datetime import datetime

import pytest

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note, open_daily_note
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListView, MeetingRow
from endpaper.tui.preview_screen import PreviewScreen
from tests.helpers import row_titles, to_collection, type_command

_CREATE = {"meetings": create_meeting, "notes": create_note}


@pytest.mark.parametrize("collection", ["meetings", "notes"])
async def test_documents_listed_date_descending(tmp_workspace: Workspace, collection: str) -> None:
    create = _CREATE[collection]
    create(tmp_workspace, "oldest", now=datetime(2026, 7, 20, 9, 0, 0))
    create(tmp_workspace, "middle", now=datetime(2026, 7, 25, 9, 0, 0))
    create(tmp_workspace, "newest", now=datetime(2026, 7, 28, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, collection)
        assert row_titles(app) == ["newest", "middle", "oldest"]


async def test_daily_and_typed_notes_appear_together_sorted_date_descending(
    tmp_workspace: Workspace,
) -> None:
    create_note(tmp_workspace, "oldest", now=datetime(2026, 7, 20, 9, 0, 0))
    open_daily_note(tmp_workspace, now=datetime(2026, 7, 25, 9, 0, 0))
    create_note(tmp_workspace, "newest", now=datetime(2026, 7, 28, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "notes")
        assert row_titles(app) == ["newest", "2026-07-25", "oldest"]


async def test_navigation_stops_at_ends_without_wrapping(tmp_workspace: Workspace) -> None:
    for i in range(3):
        create_meeting(tmp_workspace, f"meeting {i}", now=datetime(2026, 7, 20 + i, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        list_view = app.screen.query_one("#meeting-list", ListView)

        await pilot.press("j")
        await pilot.press("k", "k", "k", "k")
        await pilot.pause()
        assert list_view.index == 0

        await pilot.press("j", "j", "j", "j", "j")
        await pilot.pause()
        assert list_view.index == 2


async def test_list_reflects_meeting_created_while_in_preview(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "existing meeting", now=datetime(2026, 7, 20, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        await type_command(app, pilot, "meeting.standup Q3 planning")

        await pilot.press("escape")
        await pilot.pause()

        assert "Q3 planning" in row_titles(app)

        list_view = app.screen.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        assert isinstance(highlighted, MeetingRow)
        assert highlighted.meeting.title == "Q3 planning"


async def test_selection_preserved_across_preview_when_nothing_created(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "first", now=datetime(2026, 7, 20, 9, 0, 0))
    create_meeting(tmp_workspace, "second", now=datetime(2026, 7, 21, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        list_view = app.screen.query_one("#meeting-list", ListView)

        await pilot.press("j")
        await pilot.pause()
        selected_before = list_view.highlighted_child.meeting.title  # type: ignore[union-attr]

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        selected_after = list_view.highlighted_child.meeting.title  # type: ignore[union-attr]
        assert selected_after == selected_before


async def test_enter_opens_rendered_note_preview(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "vendor renewal", type="research")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "notes")

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.document is not None
        assert app.screen.document.title == "vendor renewal"


async def test_switching_between_collections_shows_current_content_including_new_notes(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert row_titles(app) == ["Q3 planning"]

        # Create a note while viewing meetings.
        await type_command(app, pilot, "note.research vendor landscape")
        await pilot.press("escape")
        await pilot.pause()

        await to_collection(app, pilot, "notes")
        assert row_titles(app) == ["vendor landscape"]

        await to_collection(app, pilot, "meetings")
        assert row_titles(app) == ["Q3 planning"]


async def test_single_meeting_row_is_visually_highlighted(tmp_workspace: Workspace) -> None:
    # Regression: refresh_rows used to clear() and append() without awaiting
    # either, so ListView.index was set against stale/incomplete `_nodes` and
    # the reactive's highlight watcher marked the wrong (or a since-removed)
    # widget. With exactly one row, there was no down/up workaround available.
    create_meeting(tmp_workspace, "only one", now=datetime(2026, 7, 20, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert list_view.highlighted_child is not None
        assert list_view.highlighted_child.highlighted is True


async def test_top_row_highlighted_after_refocusing_list_without_moving_cursor(
    tmp_workspace: Workspace,
) -> None:
    # Regression: after refresh_rows() ran (e.g. from switching collections),
    # the top row's `-highlight` styling was never actually applied even
    # though `list_view.index` correctly reported 0 -- only pressing an
    # explicit down-then-up forced a real re-highlight. Moving focus alone
    # (h then l) must not require that workaround.
    create_meeting(tmp_workspace, "one", now=datetime(2026, 7, 20, 9, 0, 0))
    create_meeting(tmp_workspace, "two", now=datetime(2026, 7, 21, 9, 0, 0))

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("left")
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        assert list_view.highlighted_child is not None
        assert list_view.highlighted_child.highlighted is True
