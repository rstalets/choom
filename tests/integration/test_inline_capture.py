from __future__ import annotations

from textual.widgets import TextArea

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.tasks import load_tasks
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen
from tests.helpers import open_edit, submit_editor_line


async def test_capture_creates_a_task_and_leaves_a_mirror(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        scroll_before = editor.scroll_offset

        line_index = await submit_editor_line(
            pilot,
            editor,
            "/task.followup call Terry about the renewal #procurement",
        )

        tasks, _warnings = load_tasks(tmp_workspace)
        assert len(tasks) == 1
        task = tasks[0]
        assert task.text == "call Terry about the renewal"
        assert task.type == "followup"
        assert task.tags == ("procurement",)
        assert len(task.links) == 1

        line = editor.get_line(line_index).plain
        assert line.startswith("- [ ] [call Terry about the renewal](")
        assert f"#{task.id}" in line

        # The editor never moved -- no screen push, no scroll change.
        assert isinstance(app.screen, EditScreen)
        assert app.screen is screen
        assert editor.scroll_offset == scroll_before

        # The cursor sits at the end of the inserted line.
        assert editor.cursor_location == (line_index, len(line))


async def test_capture_records_the_source_document_as_a_link(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/task chase the SOW")

        tasks, _warnings = load_tasks(tmp_workspace)
        assert tasks[0].links == (meeting.id,)


# --- US2: promoting an existing line -------------------------------------------


async def test_promoting_a_line_uses_its_own_words_as_the_description(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(
            pilot, editor, "/task.followup chase the security review with Priya"
        )

        tasks, _warnings = load_tasks(tmp_workspace)
        assert len(tasks) == 1
        assert tasks[0].text == "chase the security review with Priya"
        assert tasks[0].type == "followup"

        line = editor.get_line(line_index).plain
        assert line.startswith("- [ ] [chase the security review with Priya](")


async def test_promoted_line_with_a_tag_extracts_it_like_a_fresh_description(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/task.followup chase the SOW #procurement")

        tasks, _warnings = load_tasks(tmp_workspace)
        assert tasks[0].text == "chase the SOW"
        assert tasks[0].tags == ("procurement",)


async def test_a_bare_task_dot_followup_with_no_description_reports_and_writes_nothing(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        line_index = await submit_editor_line(pilot, editor, "/task.followup")

        from endpaper.tui.status_bar import StatusBar

        status = screen.query_one(StatusBar)
        assert "needs a description" in str(status.content)
        assert editor.get_line(line_index).plain == "/task.followup"

        tasks, _warnings = load_tasks(tmp_workspace)
        assert tasks == []


async def test_prose_mentioning_task_creates_nothing(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(
            pilot, editor, "Did you know you can type /task here?"
        )

        assert editor.get_line(line_index).plain == "Did you know you can type /task here?"
        tasks, _warnings = load_tasks(tmp_workspace)
        assert tasks == []


async def test_undo_removes_the_mirror_but_keeps_the_task(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/task chase the SOW")
        assert "chase the SOW" not in editor.text or "[" in editor.text  # sanity: became a link

        editor.undo()
        await pilot.pause()

        assert "/task chase the SOW" in editor.text
        tasks, _warnings = load_tasks(tmp_workspace)
        assert len(tasks) == 1
        assert tasks[0].text == "chase the SOW"
