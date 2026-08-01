"""Integration tests for the periodic refresh timer (010-read-on-load, US2).

Principle VI forbids a test that depends on the wall clock: nothing here
sleeps or waits for a tick to fire on its own (research R9). Behaviour tests
invoke `ListScreen._refresh_tick()` directly; the one test that needs a real
`Timer` object asserts on its state (interval, paused/active) rather than
waiting for it to fire.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.command_bar import CommandBar
from choom.tui.list_screen import DocumentRow, ListScreen
from tests.helpers import (
    delete_file_out_of_process,
    in_scope_month,
    list_view,
    to_collection,
    type_command,
)


def _screen(app: ChoomApp) -> ListScreen:
    screen = app.screen
    assert isinstance(screen, ListScreen)
    return screen


# --- T020: an unchanged workspace never rebuilds -------------------------------


async def test_tick_on_an_unchanged_workspace_performs_no_rebuild(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Existing meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        rows_before = list(list_view(app).children)
        index_before = list_view(app).index

        for _ in range(3):
            await _screen(app)._refresh_tick()
            await pilot.pause()

        # Same row widgets, same object identity -- never rebuilt, not merely
        # rebuilt to look the same (FR-010, SC-006).
        assert list(list_view(app).children) == rows_before
        for before, after in zip(rows_before, list_view(app).children, strict=True):
            assert before is after
        assert list_view(app).index == index_before


# --- T021: a real change updates the list and preserves selection by id -------


async def test_tick_after_an_out_of_process_change_updates_the_list_and_keeps_selection(
    tmp_workspace: Workspace,
) -> None:
    now = in_scope_month(1)
    create_meeting(tmp_workspace, "Existing meeting", now=now)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        existing_row = list_view(app).highlighted_child
        assert isinstance(existing_row, DocumentRow)
        existing_id = existing_row.document.id

        # A full minute later, so it is unambiguously newer once `created` is
        # truncated to the second -- and therefore sorts above the existing
        # meeting (created descending).
        create_meeting(tmp_workspace, "Newer meeting", now=now + timedelta(minutes=1))

        await _screen(app)._refresh_tick()
        await pilot.pause()

        rows = list_view(app).children
        assert [r.document.title for r in rows if isinstance(r, DocumentRow)] == [  # type: ignore[union-attr]
            "Newer meeting",
            "Existing meeting",
        ]
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, DocumentRow)
        assert highlighted.document.id == existing_id


async def test_tick_after_the_selected_record_vanishes_lands_on_a_neighbour(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "First meeting")
    create_meeting(tmp_workspace, "Second meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        assert len(list_view(app).children) == 2
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, DocumentRow)
        gone_path = highlighted.document.path
        remaining_title = next(
            r.document.title
            for r in list_view(app).children
            if isinstance(r, DocumentRow) and r.document.path != gone_path
        )

        delete_file_out_of_process(gone_path)

        await _screen(app)._refresh_tick()
        await pilot.pause()

        rows = list_view(app).children
        assert len(rows) == 1
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, DocumentRow)
        assert highlighted.document.title == remaining_title


# --- T022: the tick is inert with the command bar open or a filter active -----


async def test_tick_does_nothing_while_the_command_bar_is_open(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Existing meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("/")
        await pilot.pause()
        assert app.screen.query_one(CommandBar).display is True

        calls: list[None] = []
        original = app.visible_documents

        def _counting() -> list:  # type: ignore[type-arg]
            calls.append(None)
            return original()

        app.visible_documents = _counting  # type: ignore[method-assign]

        await _screen(app)._refresh_tick()
        await pilot.pause()

        assert calls == []


async def test_tick_does_nothing_while_a_filter_is_active(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Existing meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await type_command(app, pilot, "filter Existing")
        assert app.filter_query == "Existing"
        assert app.screen.query_one(CommandBar).display is False

        calls: list[None] = []
        original = app.visible_documents

        def _counting() -> list:  # type: ignore[type-arg]
            calls.append(None)
            return original()

        app.visible_documents = _counting  # type: ignore[method-assign]

        await _screen(app)._refresh_tick()
        await pilot.pause()

        assert calls == []


# --- T023: the interval is registered and paused/resumed with the screen -----


async def test_interval_is_registered_and_pauses_while_a_screen_is_pushed_over(
    tmp_workspace: Workspace,
) -> None:
    from choom.tui.list_screen import REFRESH_SECONDS

    create_meeting(tmp_workspace, "Existing meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        screen = _screen(app)
        timer = screen._refresh_timer
        assert timer is not None
        assert timer._interval == pytest.approx(REFRESH_SECONDS)  # type: ignore[attr-defined]
        assert timer._active.is_set() is True  # type: ignore[attr-defined]

        await pilot.press("enter")  # push PreviewScreen over the list
        await pilot.pause()
        assert timer._active.is_set() is False  # type: ignore[attr-defined]

        await pilot.press("escape")  # back to the list
        await pilot.pause()
        assert timer._active.is_set() is True  # type: ignore[attr-defined]
