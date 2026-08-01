from __future__ import annotations

from textual.widgets import TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.tasks import add_task
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import DocumentRow, ListScreen
from tests.helpers import list_view, to_collection


async def test_e_from_list_opens_the_raw_markdown(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        assert app.screen.target.display_path == meeting.path
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text.startswith("---\n")
        assert "Q3 planning" in editor.text


async def test_save_and_exit_returns_to_list_with_the_row_updated(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text.replace("Q3 planning", "Q3 planning (revised)")

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, DocumentRow)
        assert highlighted.document.title == "Q3 planning (revised)"


async def test_e_opens_the_task_editor_on_a_highlighted_task(tmp_workspace: Workspace) -> None:
    from choom.core.tasks import add_task

    add_task(tmp_workspace, "buy milk")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == ""


async def test_e_is_a_noop_on_the_tasks_empty_state(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)


async def test_e_is_a_noop_on_the_empty_state(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)


async def test_e_from_list_and_e_from_preview_produce_identical_edit_screens(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    from_list = ChoomApp(tmp_workspace)
    async with from_list.run_test(size=(80, 24)) as pilot:
        await to_collection(from_list, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()
        list_screen = from_list.screen
        assert type(list_screen) is EditScreen
        list_text = list_screen.query_one("#editor", TextArea).text

    from_preview = ChoomApp(tmp_workspace)
    async with from_preview.run_test(size=(80, 24)) as pilot:
        await to_collection(from_preview, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        preview_screen = from_preview.screen
        assert type(preview_screen) is EditScreen
        preview_text = preview_screen.query_one("#editor", TextArea).text

    # Both routes go through the same `open_editor()` (research R10), so they
    # necessarily construct the same screen class with the same bindings --
    # what remains to verify is that the buffer contents agree too.
    assert list_text == preview_text


# --- US7: cursor placement on entering edit mode --------------------------------


async def test_cursor_lands_one_blank_line_below_existing_content(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        row, col = editor.cursor_location
        assert col == 0
        lines = editor.text.split("\n")
        assert row == len(lines) - 1
        assert lines[row] == ""

        # Typing lands exactly where the cursor already is -- appending a
        # thought costs no cursor-movement keystrokes (SC-009).
        await pilot.press("h", "i")
        await pilot.pause()
        assert editor.text.split("\n")[row] == "hi"


async def test_cursor_lands_on_the_first_line_of_an_empty_task_body(
    tmp_workspace: Workspace,
) -> None:
    add_task(tmp_workspace, "buy milk")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == ""
        assert editor.cursor_location == (0, 0)


async def test_entering_and_leaving_a_document_without_typing_raises_no_confirmation(
    tmp_workspace: Workspace,
) -> None:
    # Positioning the cursor is not an edit (FR-042): the padded buffer is
    # the screen's own unedited state (research R10), so leaving without
    # typing anything pops straight back rather than raising ConfirmDialog,
    # and the file on disk is untouched.
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before = meeting.path.read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)
        assert app.screen.is_dirty is False

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)

    assert meeting.path.read_bytes() == before


async def test_entering_and_leaving_a_task_body_without_typing_raises_no_confirmation(
    tmp_workspace: Workspace,
) -> None:
    add_task(tmp_workspace, "buy milk")
    before = tmp_workspace.tasks_file.read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)
        assert app.screen.is_dirty is False

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)

    assert tmp_workspace.tasks_file.read_bytes() == before
