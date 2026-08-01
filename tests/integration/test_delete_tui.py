from __future__ import annotations

from choom.core.meetings import create_meeting, scan_meetings
from choom.core.models import Workspace
from choom.core.notes import create_note, scan_notes
from choom.core.tasks import add_task, load_tasks
from choom.tui.app import ChoomApp
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.list_screen import DocumentRow, ListScreen, TaskRow
from choom.tui.status_bar import StatusBar
from tests.helpers import delete_file_out_of_process, list_view, row_titles, to_collection


async def test_ctrl_d_raises_confirmation_naming_the_meeting(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("ctrl+d")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialog)
        rendered = "\n".join(str(w.render()) for w in app.screen.query("Label"))
        assert "Q3 planning" in rendered
        assert "(Esc) Keep It" in rendered
        assert "(Enter) Delete" in rendered


async def test_confirming_deletes_meeting_file_and_row(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    other = create_meeting(tmp_workspace, "budget review")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        # rows are newest-created-first; highlight the one we're about to delete
        highlighted = list_view(app).highlighted_child
        assert isinstance(highlighted, DocumentRow)
        target_title = highlighted.document.title

        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        remaining_titles = row_titles(app)
        assert target_title not in remaining_titles

        meetings, _warnings = scan_meetings(tmp_workspace)
        assert {m.title for m in meetings} == {meeting.title, other.title} - {target_title}


async def test_declining_leaves_everything_unchanged(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        before_index = list_view(app).index

        await pilot.press("ctrl+d")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        meetings, _warnings = scan_meetings(tmp_workspace)
        assert len(meetings) == 1
        assert list_view(app).index == before_index


async def test_deleting_note_removes_file(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "an idea")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "notes")

        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert not note.path.exists()
        notes, _warnings = scan_notes(tmp_workspace)
        assert notes == []


async def test_deleting_task_with_multiline_body_leaves_neighbours_intact(
    tmp_workspace: Workspace,
) -> None:
    from tests.conftest import tasks_file, write_tasks

    write_tasks(
        tmp_workspace,
        "- [ ] first <!-- id:task_a -->\n"
        "- [ ] middle <!-- id:task_b -->\n"
        "\n"
        "  line one of the body\n"
        "  line two of the body\n"
        "\n"
        "- [ ] last <!-- id:task_c -->\n",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        rows = [r for r in list_view(app).children if isinstance(r, TaskRow)]
        middle_index = next(i for i, r in enumerate(rows) if r.record.id == "task_b")
        list_view(app).index = middle_index
        await pilot.pause()

        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        tasks, _warnings = load_tasks(tmp_workspace)
        ids = {t.id for t in tasks}
        assert ids == {"task_a", "task_c"}
        text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
        assert "task_a" in text
        assert "task_c" in text
        assert "task_b" not in text
        assert "line one of the body" not in text


async def test_highlight_moves_to_next_record_after_delete(tmp_workspace: Workspace) -> None:
    task_one = add_task(tmp_workspace, "first task")
    add_task(tmp_workspace, "second task")
    add_task(tmp_workspace, "third task")
    assert task_one.id is not None

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # Tasks sort oldest-first, so "first task" is at index 0.
        list_view(app).index = 0
        await pilot.pause()
        highlighted_before = list_view(app).highlighted_child
        assert isinstance(highlighted_before, TaskRow)
        assert highlighted_before.record.text == "first task"

        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        highlighted_after = list_view(app).highlighted_child
        assert isinstance(highlighted_after, TaskRow)
        assert highlighted_after.record.text == "second task"


async def test_highlight_moves_to_previous_when_last_record_deleted(
    tmp_workspace: Workspace,
) -> None:
    add_task(tmp_workspace, "first task")
    add_task(tmp_workspace, "second task")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        list_view(app).index = 1  # the last row -- "second task"
        await pilot.pause()
        highlighted_before = list_view(app).highlighted_child
        assert isinstance(highlighted_before, TaskRow)
        assert highlighted_before.record.text == "second task"

        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        highlighted_after = list_view(app).highlighted_child
        assert isinstance(highlighted_after, TaskRow)
        assert highlighted_after.record.text == "first task"


async def test_deleting_the_only_record_shows_empty_state(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert row_titles(app) == []
        highlighted = list_view(app).highlighted_child
        assert not isinstance(highlighted, DocumentRow)
        assert "No meetings yet" in str(highlighted.children[0].render())  # type: ignore[union-attr]


async def test_ctrl_d_is_noop_with_no_records(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("ctrl+d")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)


async def test_ctrl_d_belongs_to_command_bar_when_open(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.press("/")
        await pilot.pause()

        await pilot.press("ctrl+d")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        meetings, _warnings = scan_meetings(tmp_workspace)
        assert len(meetings) == 1


async def test_stale_row_reports_and_refreshes_rather_than_crashing(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        # Simulate another process deleting the file between the confirmation
        # appearing and being confirmed.
        delete_file_out_of_process(meeting.path)

        await pilot.press("ctrl+d")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        status = app.screen.query_one(StatusBar)
        assert "no" in str(status.content).lower()
        assert row_titles(app) == []


async def test_footer_advertises_ctrl_d(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        assert "ctrl+d delete" in str(status.content)

        await pilot.press("tab")  # tasks -> notes
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        assert "ctrl+d delete" in str(status.content)
