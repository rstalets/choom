from __future__ import annotations

from textual.widgets import TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import ListScreen
from tests.helpers import editor_pane, open_edit, to_collection


async def test_ctrl_q_with_changes_raises_dialog_with_nothing_written(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        path = edit_screen.target.display_path
        before_bytes = path.read_bytes()

        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("ctrl+q")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialog)
        assert app.is_running
        assert path.read_bytes() == before_bytes


async def test_ctrl_q_enter_confirms_and_exits_without_saving(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before_bytes = meeting.path.read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("ctrl+q")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("enter")
        await pilot.pause()

        assert not app.is_running
        assert meeting.path.read_bytes() == before_bytes


async def test_ctrl_q_escape_cancels_and_returns_to_editor_with_buffer_intact(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"
        expected_text = editor.text

        await pilot.press("ctrl+q")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("escape")
        await pilot.pause()

        assert app.is_running
        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == expected_text


async def test_ctrl_q_with_changes_over_inline_editor_raises_dialog(
    tmp_workspace: Workspace,
) -> None:
    """`ctrl+q` finds a dirty inline editor the same way it finds a dirty
    full-screen one (research R9, `open_editors`, T010/T032): the confirmation
    is raised, nothing is written, and the pane is still there to return to."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before_bytes = meeting.path.read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        pane = editor_pane(app)
        editor = pane.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("ctrl+q")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialog)
        assert app.is_running
        assert meeting.path.read_bytes() == before_bytes

        await pilot.press("escape")
        await pilot.pause()

        assert app.is_running
        assert isinstance(app.screen, ListScreen)
        assert editor_pane(app) is pane


async def test_ctrl_q_with_no_changes_exits_immediately_with_no_dialog(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)

        await pilot.press("ctrl+q")
        await pilot.pause()

        assert not app.is_running


async def test_ctrl_q_on_list_screen_exits_immediately(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("ctrl+q")
        await pilot.pause()

        assert not app.is_running


async def test_second_ctrl_q_does_not_stack_a_second_dialog(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("ctrl+q")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        first_dialog = app.screen

        await pilot.press("ctrl+q")
        await pilot.pause()

        assert app.screen is first_dialog
