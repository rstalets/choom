from __future__ import annotations

from textual.widgets import TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.edit_screen import EditScreen
from choom.tui.preview_screen import PreviewScreen
from tests.helpers import open_edit


async def test_esc_with_changes_raises_dialog_with_nothing_written(
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

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialog)
        assert path.read_bytes() == before_bytes


async def test_dialog_is_a_slim_bar_with_two_named_keys(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialog)
        rendered = "\n".join(str(w.render()) for w in app.screen.query("Label"))
        assert "(Esc) Continue Editing" in rendered
        assert "(Enter) Exit Without Saving" in rendered
        # No bare OK/Yes/No/Cancel (SC-006), and no focusable child to move a
        # highlight between (FR-022) -- the only widgets are Labels.
        assert not app.screen.query("Button")


async def test_esc_cancels_and_returns_with_buffer_and_cursor_intact(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"
        editor.cursor_location = (0, 2)
        expected_text = editor.text

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == expected_text
        assert editor.cursor_location == (0, 2)


async def test_enter_proceeds_and_leaves_file_byte_identical(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before_bytes = meeting.path.read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert meeting.path.read_bytes() == before_bytes


async def test_unrelated_key_is_swallowed_and_dialog_stays_up(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        # A key that would mean something on the screen underneath (e.g. "e"
        # for edit, "j" for cursor-down) must not fall through.
        await pilot.press("j")
        await pilot.press("e")
        await pilot.press("x")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialog)


async def test_no_changes_means_no_dialog(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)


async def test_no_dialog_after_ctrl_o_save(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\nnew content\n"

        await pilot.press("ctrl+o")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)


async def test_no_dialog_after_retyping_original_text_by_hand(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        original = editor.text

        editor.text = original + "temporary"
        assert edit_screen.is_dirty is True
        editor.text = original
        assert edit_screen.is_dirty is False

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
