from __future__ import annotations

from textual.widgets import TextArea

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.discard_dialog import DiscardDialog
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.preview_screen import PreviewScreen
from tests.helpers import open_edit


async def test_esc_with_changes_raises_dialog_with_nothing_written(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        path = edit_screen.target.display_path
        before_bytes = path.read_bytes()

        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, DiscardDialog)
        assert path.read_bytes() == before_bytes


async def test_cancel_returns_with_buffer_and_cursor_intact(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        edit_screen = await open_edit(app, pilot)
        editor = edit_screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"
        editor.cursor_location = (0, 2)
        expected_text = editor.text

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DiscardDialog)

        await pilot.press("tab")  # move focus to Cancel (Discard, Cancel order)
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == expected_text
        assert editor.cursor_location == (0, 2)


async def test_discard_leaves_file_byte_identical(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before_bytes = meeting.path.read_bytes()

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "unsaved change"

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DiscardDialog)

        dialog = app.screen
        dialog.dismiss(True)
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert meeting.path.read_bytes() == before_bytes


async def test_no_changes_means_no_dialog(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)


async def test_no_dialog_after_ctrl_o_save(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
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

    app = EndpaperApp(tmp_workspace)
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
