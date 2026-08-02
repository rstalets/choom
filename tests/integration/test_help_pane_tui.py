from __future__ import annotations

from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.commands import VERB_TABLE
from choom.tui.help_screen import HelpScreen
from choom.tui.list_screen import ListScreen
from tests.helpers import list_view, to_collection


async def _open_help(pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.pause()
    await pilot.press("/")
    await pilot.pause()
    await pilot.press("h", "e", "l", "p")
    await pilot.press("enter")
    await pilot.pause()


async def test_help_pane_lists_every_verb_with_a_description(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_help(pilot)
        assert isinstance(app.screen, HelpScreen)

        body = str(app.screen.query_one("#help-body").content)  # type: ignore[attr-defined]
        for verb in VERB_TABLE:
            assert f"/{verb.name}" in body
            assert verb.description in body


async def test_help_pane_lists_the_in_editor_task_command(tmp_workspace: Workspace) -> None:
    # FR-010: /task's discoverability comes entirely from being registered in
    # EDITOR_COMMANDS -- no help text is written by hand in a second place.
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_help(pilot)
        body = str(app.screen.query_one("#help-body").content)  # type: ignore[attr-defined]
        assert "/task <description>" in body
        assert "this line becomes a link to it" in body


async def test_help_pane_names_e_for_a_tasks_details(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_help(pilot)
        body = str(app.screen.query_one("#help-body").content)  # type: ignore[attr-defined]
        assert "task's details" in body


async def test_help_pane_leaves_the_list_visible_underneath(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_help(pilot)
        # The list screen is never popped -- it's still in the stack, just
        # dimmed behind the modal (FR-041, research R4).
        assert isinstance(app.screen_stack[-2], ListScreen)


async def test_escape_dismisses_and_leaves_state_unchanged(tmp_workspace: Workspace) -> None:
    from choom.core.meetings import create_meeting

    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        highlighted_before = list_view(app).highlighted_child.document.id  # type: ignore[union-attr]
        active_before = app.active

        await pilot.press("/")
        await pilot.pause()
        await pilot.press("h", "e", "l", "p")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        assert app.active == active_before
        assert list_view(app).highlighted_child.document.id == highlighted_before  # type: ignore[union-attr]


# --- T028 (020-vertical-tui-mode, US5, FR-046): /config's help entry names
# both settings and both of view's accepted values -----------------------


async def test_help_pane_names_view_and_both_accepted_values(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_help(pilot)
        body = str(app.screen.query_one("#help-body").content)  # type: ignore[attr-defined]
        assert "view" in body
        assert "horizontal" in body
        assert "vertical" in body
