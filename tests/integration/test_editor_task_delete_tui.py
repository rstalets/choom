"""US1-US5 (017-editor-task-delete): `ctrl+t` removes the task line under the
cursor from the open document and from tasks.md, after one confirmation.

Setup is deliberately mixed: most tests build the buffer directly
(`editor.text = ...`) because only the gesture itself is under test here --
the same pattern `test_edit_save_tui.py` already uses. The two undo tests
(US1/US2's "captured this session" case, and the undo-after-delete case) go
through the real `/task` capture and the real `ctrl+t` keystrokes instead,
because those tests are specifically about what survives in the undo stack,
which a direct `editor.text` assignment would destroy before the test even
starts (research R2).
"""

from __future__ import annotations

import pytest
from textual.widgets import TextArea

from choom.core.deletion import delete_by_id
from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_task
from choom.core.models import Workspace
from choom.core.tasks import add_task, load_tasks
from choom.tui.app import ChoomApp
from choom.tui.confirm_dialog import ConfirmDialog
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import ListScreen
from choom.tui.status_bar import StatusBar
from tests.conftest import tasks_file, write_tasks
from tests.helpers import editor_pane, open_edit, submit_editor_line, to_collection


def _status_text(app: object) -> str:
    return str(app.screen.query_one(StatusBar).content)  # type: ignore[attr-defined]


def _dialog_text(app: object) -> str:
    return "\n".join(str(w.render()) for w in app.screen.query("Label"))  # type: ignore[attr-defined]


async def _open_inline(app: ChoomApp, pilot: object, *, collection: str = "meetings") -> object:
    """The inline route (research R1, contract C1): `e` directly from the
    list, never entering the preview screen first."""
    await to_collection(app, pilot, collection)
    await pilot.press("e")
    await pilot.pause()
    return editor_pane(app)


# --- FR-004 / C3: inert while busy ----------------------------------------------


async def test_ctrl_t_does_nothing_while_an_ai_request_is_in_flight(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    before = tasks_file(tmp_workspace).read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = line + "\n"

        pane = editor_pane(app)
        pane._request = object()  # type: ignore[assignment]  # simulate an in-flight /ai request
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmDialog)
        assert tasks_file(tmp_workspace).read_bytes() == before
        assert task.id is not None


async def test_ctrl_t_does_nothing_while_the_link_picker_is_open(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning alpha")
    create_meeting(tmp_workspace, "Q3 planning beta")
    meeting = create_meeting(tmp_workspace, "capture site", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    before = tasks_file(tmp_workspace).read_bytes()

    from choom.tui.link_picker import LinkPicker

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 40)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\n" + line + "\n"
        task_row = editor.document.line_count - 2

        line_index = await submit_editor_line(pilot, editor, "/link q3 planning")

        picker = app.screen.query_one(LinkPicker)
        assert picker.display is True
        pane = editor_pane(app)
        assert pane._link_picker_line == line_index

        editor.cursor_location = (task_row, 0)
        await pilot.press("ctrl+t")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmDialog)
        assert picker.display is True
        assert tasks_file(tmp_workspace).read_bytes() == before
        assert task.id is not None


# --- US1/US2: the happy path (T013) ---------------------------------------------


async def test_dialog_names_the_task_and_confirming_deletes_from_both_places(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    keep_task, keep_line = capture_task(
        tmp_workspace, "keep this one", source=meeting.path, source_id=meeting.id
    )
    doomed_task, doomed_line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert keep_task.id is not None and doomed_task.id is not None

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = keep_line + "\n" + doomed_line + "\n"
        editor.cursor_location = (1, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmDialog)
        rendered = _dialog_text(app)
        assert "call Terry" in rendered
        assert "cannot be undone" in rendered
        assert "(Esc) Keep It" in rendered
        assert "(Enter) Delete" in rendered

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert doomed_task.text not in editor.text
        assert keep_line in editor.text

        assert f'deleted "{doomed_task.text}"' in _status_text(app)

        tasks, _warnings = load_tasks(tmp_workspace)
        remaining_ids = {t.id for t in tasks}
        assert keep_task.id in remaining_ids
        assert doomed_task.id not in remaining_ids

        text_on_disk = meeting.path.read_text(encoding="utf-8")
        assert doomed_task.text not in text_on_disk
        assert keep_line.rstrip("\n") in text_on_disk


async def test_deleted_task_is_absent_from_the_tasks_collection_after_render(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = line + "\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")  # editor -> preview
        await pilot.pause()
        await pilot.press("escape")  # preview -> list
        await pilot.pause()

        from tests.helpers import task_rows

        await to_collection(app, pilot, "tasks")
        assert task.id not in {r.record.id for r in task_rows(app)}


async def test_extra_text_on_the_line_is_named_in_the_dialog(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    stripped = line.rstrip("\n")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = f"{stripped} before Friday, ask Dana\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()

        assert "goes too" in _dialog_text(app)


async def test_task_captured_this_session_deletes_identically_to_one_seeded_earlier(
    tmp_workspace: Workspace,
) -> None:
    """US2: no additional behaviour needed -- the same code path deletes a
    task captured seconds ago and one that existed before the editor opened."""
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/task folow up with Dana")
        tasks, _warnings = load_tasks(tmp_workspace)
        assert len(tasks) == 1
        task = tasks[0]

        editor.cursor_location = (line_index, 0)
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        await pilot.press("enter")
        await pilot.pause()

        tasks_after, _warnings = load_tasks(tmp_workspace)
        assert tasks_after == []
        editor = app.screen.query_one("#editor", TextArea)
        assert task.text not in editor.text


# --- FR-014 / SC-005: cancel is a total no-op (T014) -----------------------------


async def test_cancel_writes_nothing_even_with_unrelated_unsaved_edits(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    doc_before = meeting.path.read_bytes()
    tasks_before = tasks_file(tmp_workspace).read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = editor.text + "an unrelated half-sentence\n" + line + "\n"
        row = editor.document.line_count - 2
        editor.cursor_location = (row, 0)
        assert editor_pane(app).is_dirty is True

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        assert meeting.path.read_bytes() == doc_before
        assert tasks_file(tmp_workspace).read_bytes() == tasks_before
        assert editor_pane(app).is_dirty is True
        assert task.id is not None


# --- research R2: undo after a confirmed deletion (T015) -------------------------


async def test_undo_restores_the_line_but_the_task_stays_deleted(
    tmp_workspace: Workspace,
) -> None:
    """Uses a task-body editor, per T015's note: `stamps_frontmatter=False`
    there, so `_save`'s own pre-existing `editor.text = result.saved_text`
    reassignment (edit_screen.py:445-453, out of scope for this feature)
    never fires and never clears history on its own."""
    add_task(tmp_workspace, "buy milk")  # gives the body-less task a sibling
    body_task = add_task(tmp_workspace, "write the body")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "tasks")
        from tests.helpers import task_rows

        rows = task_rows(app)
        index = next(i for i, r in enumerate(rows) if r.record.id == body_task.id)
        from tests.helpers import list_view

        list_view(app).index = index
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        pane = editor_pane(app)
        editor = pane.query_one("#editor", TextArea)

        # An edit made *before* the deletion -- proof the deletion did not
        # clear history back past it.
        editor.insert("first paragraph\n\n")
        await pilot.pause()

        inner_task, inner_line = capture_task(
            tmp_workspace, "call Terry", source=tmp_workspace.tasks_file, source_id=body_task.id
        )
        editor.insert(inner_line + "\n")
        row = editor.document.line_count - 2
        editor.cursor_location = (row, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        editor = pane.query_one("#editor", TextArea)
        assert inner_task.text not in editor.text

        editor.undo()  # undoes the ctrl+t splice
        await pilot.pause()
        assert inner_task.text in editor.text

        tasks, _warnings = load_tasks(tmp_workspace)
        assert inner_task.id not in {t.id for t in tasks}

        editor.undo()  # undoes inserting the mirror line
        await pilot.pause()
        assert inner_task.text not in editor.text
        assert "first paragraph" in editor.text

        # The earlier edit is still undoable -- history from before the
        # deletion survived it, back to the very first keystroke.
        editor.undo()  # undoes the pre-existing "first paragraph" edit
        await pilot.pause()
        assert "first paragraph" not in editor.text


# --- US3: inert off a task line (T016) -------------------------------------------


@pytest.mark.parametrize(
    ("text", "line"),
    [
        ("just some prose\n", 0),
        ("# a heading\n", 0),
        ("\n", 0),
        ("- [ ] buy milk\n", 0),
        ("- [ ] `[call Terry](../../../tasks.md#task_a1b2)`\n", 0),
        ("```\n- [ ] [call Terry](../../../tasks.md#task_a1b2)\n```\n", 1),
    ],
)
async def test_no_dialog_and_no_write_off_a_task_line(
    tmp_workspace: Workspace, text: str, line: int
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    doc_before_edit = None

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = text
        editor.cursor_location = (line, 0)
        doc_before_edit = meeting.path.read_bytes()
        tasks_before = tasks_file(tmp_workspace).read_bytes()

        await pilot.press("ctrl+t")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmDialog)
        assert "no task on this line" in _status_text(app)
        assert "⚠" not in _status_text(app)

        # ctrl+t off a task line does not save -- the buffer, not the file
        # on disk, is what changed via `editor.text =` above.
        assert meeting.path.read_bytes() == doc_before_edit
        assert tasks_file(tmp_workspace).read_bytes() == tasks_before


# --- US4: the task is already gone (T017) -----------------------------------------


async def test_line_only_dialog_and_deletion_leaves_tasks_md_untouched(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    delete_by_id(tmp_workspace, task.id)
    tasks_before = tasks_file(tmp_workspace).read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = line + "\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()

        rendered = _dialog_text(app)
        assert "no longer in your task list" in rendered
        assert "only this line goes" in rendered

        await pilot.press("enter")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        assert task.text not in editor.text
        assert tasks_file(tmp_workspace).read_bytes() == tasks_before


# --- US5: an unreadable task list refuses (T018) -----------------------------------


async def test_unreadable_task_list_refuses_and_names_the_line(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    write_tasks(tmp_workspace, "- [ ] broken <!-- id:task_broken\n")
    doc_before = None

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = "- [ ] [call Terry](../../../tasks.md#task_gone)\n"
        editor.cursor_location = (0, 0)
        doc_before = meeting.path.read_bytes()
        tasks_before = tasks_file(tmp_workspace).read_bytes()

        await pilot.press("ctrl+t")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmDialog)
        status = _status_text(app)
        assert "tasks.md:1" in status
        assert "⚠" in status
        assert meeting.path.read_bytes() == doc_before
        assert tasks_file(tmp_workspace).read_bytes() == tasks_before


async def test_a_resolvable_id_still_deletes_when_the_file_has_an_unreadable_line(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    write_tasks(tmp_workspace, text + "- [ ] broken <!-- id:task_broken\n")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = line + "\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        await pilot.press("enter")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        assert task.text not in editor.text
        remaining = tasks_file(tmp_workspace).read_text(encoding="utf-8")
        assert "task_broken" in remaining
        assert (task.id or "") not in remaining


# --- FR-023 / FR-024: ambiguous id, self-referential body (T019) ------------------


async def test_ambiguous_id_refuses_and_names_both_lines(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    write_tasks(
        tmp_workspace,
        "- [ ] call Terry <!-- id:task_dupe -->\n- [ ] call Terry again <!-- id:task_dupe -->\n",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = "- [ ] [call Terry](../../../tasks.md#task_dupe)\n"
        editor.cursor_location = (0, 0)
        before = tasks_file(tmp_workspace).read_bytes()

        await pilot.press("ctrl+t")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmDialog)
        status = _status_text(app)
        assert "1" in status and "2" in status
        assert tasks_file(tmp_workspace).read_bytes() == before
        assert meeting.path.exists()


async def test_deleting_the_task_whose_own_body_is_open_refuses(
    tmp_workspace: Workspace,
) -> None:
    from choom.core.mirrors import mirror_line

    task = add_task(tmp_workspace, "write the body")
    assert task.id is not None
    # A mirror line for *this same task* -- the shape FR-024 refuses on.
    # Built and placed directly into the buffer, never through
    # `set_task_body`: a checklist-shaped body line with no metadata comment
    # is itself the "needs an id" shape `load_tasks` backfills on its very
    # next read, which would silently turn this into a second, unrelated
    # task before the gesture under test ever runs.
    self_line = mirror_line(
        task, source=tmp_workspace.tasks_file, tasks_file=tmp_workspace.tasks_file
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        from tests.helpers import list_view

        await pilot.pause()
        list_view(app).index = 0
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        pane = editor_pane(app)
        editor = pane.query_one("#editor", TextArea)
        editor.text = self_line + "\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmDialog)
        assert "editing" in _status_text(app)
        tasks, _warnings = load_tasks(tmp_workspace)
        assert task.id in {t.id for t in tasks}


async def test_deleting_a_different_task_from_inside_a_task_body_succeeds(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "write the body")
    other = add_task(tmp_workspace, "call Terry")
    assert task.id is not None and other.id is not None
    line = f"- [ ] [call Terry](../../../tasks.md#{other.id})\n"

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        from tests.helpers import list_view

        await pilot.pause()
        list_view(app).index = 0
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        pane = editor_pane(app)
        editor = pane.query_one("#editor", TextArea)
        editor.text = line
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        tasks, _warnings = load_tasks(tmp_workspace)
        remaining_ids = {t.id for t in tasks}
        assert task.id in remaining_ids
        assert other.id not in remaining_ids


# --- FR-025: the same task mirrored twice in one document (T020) ------------------


async def test_second_mirror_of_the_same_task_is_reported_dead_after_deletion(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = line + "\nsome prose\n" + line + "\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        # exactly one occurrence of the line survives -- the cursor's, not the copy
        assert editor.text.count(f"#{task.id}") == 1
        assert "does not resolve" in _status_text(app) or "⚠" in _status_text(app)


# --- FR-031: the document write fails after the record is removed (T021) ---------


async def test_document_save_failure_after_the_record_is_removed_loses_nothing(
    tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = "keep this paragraph\n\n" + line + "\n"
        editor.cursor_location = (2, 0)

        from choom.core.errors import WorkspaceError

        def _boom(*args: object, **kwargs: object) -> None:
            # write_text_atomic itself catches OSError and raises WorkspaceError;
            # replacing it outright must raise the same type its caller expects.
            raise WorkspaceError("induced failure")

        # Only the *document* write must fail here (FR-031) -- the tasks.md
        # write (step 1) must still succeed, or the whole gesture stops
        # before touching the buffer at all (research R8). `editing.py` and
        # `tasks.py` each import `write_text_atomic` into their own module
        # namespace, so patching it on `editing` alone leaves `tasks.delete_task`
        # untouched.
        import choom.core.editing as editing_module

        monkeypatch.setattr(editing_module, "write_text_atomic", _boom)

        await pilot.press("ctrl+t")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        assert "keep this paragraph" in editor.text
        assert task.text not in editor.text
        assert editor_pane(app).is_dirty is True

        tasks, _warnings = load_tasks(tmp_workspace)
        assert task.id not in {t.id for t in tasks}


# --- FR-001: both hosts (T023) -----------------------------------------------------


@pytest.mark.parametrize("host", ["inline", "full_screen"])
async def test_the_gesture_is_identical_inline_and_full_screen(
    tmp_workspace: Workspace, host: str
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        if host == "inline":
            pane = await _open_inline(app, pilot)
        else:
            await open_edit(app, pilot)
            pane = editor_pane(app)

        editor = pane.query_one("#editor", TextArea)
        editor.text = line + "\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        await pilot.press("enter")
        await pilot.pause()

        pane = editor_pane(app)
        editor = pane.query_one("#editor", TextArea)
        assert task.text not in editor.text
        tasks, _warnings = load_tasks(tmp_workspace)
        assert tasks == []


# --- CRLF end to end (T022) --------------------------------------------------------


async def test_crlf_document_with_no_trailing_newline_survives_the_gesture(
    tmp_workspace: Workspace,
) -> None:
    from tests.conftest import write_raw

    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    original = meeting.path.read_text(encoding="utf-8")
    body = original + line  # no trailing newline
    write_raw(meeting.path, body, newline="\r\n")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await open_edit(app, pilot)
        pane = editor_pane(app)
        editor = pane.query_one("#editor", TextArea)
        row = next(
            i
            for i in range(editor.document.line_count)
            if f"#{task.id}" in editor.get_line(i).plain
        )
        editor.cursor_location = (row, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        await pilot.press("enter")
        await pilot.pause()

        raw = meeting.path.read_bytes()
        assert b"\r\n" in raw
        assert not raw.rstrip(b"\r\n").endswith(b"\r") and not raw.endswith(b"\n\n")
        assert task.text.encode() not in raw
