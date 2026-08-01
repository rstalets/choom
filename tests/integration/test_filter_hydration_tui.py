"""Integration tests for command-bar filter hydration (010-read-on-load, US3).

The `/` keypress starts a worker-thread read of the whole collection; the
first filter term waits for it rather than matching a partial set (research
R6, contract C5). These tests exercise that behaviour through the real
command bar rather than calling `app.set_filter()` directly, since the
hydration snapshot lives on `ListScreen`, not on the app.
"""

from __future__ import annotations

from datetime import timedelta

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from tests.helpers import (
    create_document_out_of_process,
    in_scope_month,
    row_titles,
    to_collection,
    type_command,
    type_literally,
)


async def test_a_non_filter_verb_typed_then_backspaced_does_not_lose_the_hydration(
    tmp_workspace: Workspace,
) -> None:
    """FR-018, US3 scenario 3: the read started when the bar opened is held
    for the whole session, not restarted or cancelled by an intervening
    non-filter verb. Proven by matching a document from a month other than
    the current one -- only a whole-collection hydration reaches it."""
    now = in_scope_month(1)
    create_meeting(tmp_workspace, "Existing meeting", now=now)
    create_meeting(tmp_workspace, "Archived quarterly review", now=now - timedelta(days=95))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("/")
        await pilot.pause()

        await type_literally(pilot, "task")
        await pilot.pause()
        for _ in range(len("task")):
            await pilot.press("backspace")
        await pilot.pause()

        await type_literally(pilot, "filter archived")
        await pilot.pause()

        assert row_titles(app) == ["Archived quarterly review"]


async def test_closing_the_bar_without_typing_a_filter_leaves_the_view_unchanged(
    tmp_workspace: Workspace,
) -> None:
    """US3 scenario 4."""
    create_meeting(tmp_workspace, "Existing meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        titles_before = row_titles(app)

        await pilot.press("/")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert app.filter_query == ""
        assert row_titles(app) == titles_before


async def test_clearing_an_applied_filter_restores_the_month_scope_with_current_content(
    tmp_workspace: Workspace,
) -> None:
    """US3 scenario 5, FR-019: clearing a filter restores the pre-filter month
    scope, and that restored view reads current on-disk content -- not
    whatever the filter session's hydration held."""
    create_meeting(tmp_workspace, "Existing meeting")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        await type_command(app, pilot, "filter Existing")
        assert app.filter_query == "Existing"
        assert row_titles(app) == ["Existing meeting"]

        # Lands while the filter is showing -- a filtered view is a
        # point-in-time answer (US2/US3 scope); it is not expected to appear
        # until the filter clears and the month scope reads fresh again.
        create_document_out_of_process(tmp_workspace, "meetings", "Second meeting")

        await pilot.press("/")
        await pilot.pause()
        await pilot.press("escape")  # clears the term and closes (CommandBar.action_cancel)
        await pilot.pause()

        assert app.filter_query == ""
        assert sorted(row_titles(app)) == ["Existing meeting", "Second meeting"]
