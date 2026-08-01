"""US4: a deleted task's mirrors stay in the user's words.

Story 4 needs no new code (research R3) -- the `dead` outcome `reconcile_on_open`/
`reconcile_on_save` already produce for a mirror whose task cannot be found is
exactly what a deleted task looks like. These tests prove that holds: the
mirroring document is never touched by the delete itself, and the existing
dead-link reporting fires the next time it is opened or saved.
"""

from __future__ import annotations

from choom.core.deletion import delete_by_id
from choom.core.editing import load_for_edit, save_buffer
from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_task, find_mirrors, reconcile_on_open, reconcile_on_save
from choom.core.models import Workspace
from choom.core.notes import create_note


def _seed_mirror(tmp_workspace: Workspace) -> tuple[str, str]:
    """A meeting with a captured task and its mirror line already appended to
    the meeting's body -- the shape `capture_task` leaves for a caller to
    splice into the buffer, replicated here without a running editor."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    text = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(text + line + "\n", encoding="utf-8")
    return task.id, line


def test_mirroring_document_is_byte_identical_after_the_task_is_deleted(
    tmp_workspace: Workspace,
) -> None:
    task_id, _line = _seed_mirror(tmp_workspace)
    meeting_path = next(tmp_workspace.meetings_dir.rglob("*.md"))
    before_bytes = meeting_path.read_bytes()

    delete_by_id(tmp_workspace, task_id)

    assert meeting_path.read_bytes() == before_bytes


def test_opening_the_document_surfaces_a_dead_link_warning(tmp_workspace: Workspace) -> None:
    task_id, _line = _seed_mirror(tmp_workspace)
    meeting_path = next(tmp_workspace.meetings_dir.rglob("*.md"))

    delete_by_id(tmp_workspace, task_id)

    text = meeting_path.read_text(encoding="utf-8")
    report = reconcile_on_open(tmp_workspace, text, source=meeting_path)

    assert report.text is text  # identity -- nothing was corrected or rewritten
    assert any(w.reason == "link_dead" for w in report.warnings)
    assert any(r.task_id == task_id and r.outcome == "dead" for r in report.resolutions)


def test_ticking_the_orphaned_checkbox_still_saves_with_the_dead_link_reported(
    tmp_workspace: Workspace,
) -> None:
    task_id, _line = _seed_mirror(tmp_workspace)
    meeting_path = next(tmp_workspace.meetings_dir.rglob("*.md"))

    delete_by_id(tmp_workspace, task_id)

    text = meeting_path.read_text(encoding="utf-8")
    mirrors = find_mirrors(text, source=meeting_path)
    assert len(mirrors) == 1
    mirror = mirrors[0]
    assert mirror.done is False

    # The user ticks the box by hand -- a one-character splice, the same
    # mechanism a real editor keystroke produces.
    ticked_text = text[: mirror.state_offset] + "x" + text[mirror.state_offset + 1 :]

    save_report = reconcile_on_save(
        tmp_workspace, ticked_text, source=meeting_path, baseline={task_id: False}
    )
    assert save_report.text == ticked_text  # the user's tick survives -- untouched
    assert any(w.reason == "link_dead" for w in save_report.warnings)
    assert any(r.task_id == task_id and r.outcome == "dead" for r in save_report.resolutions)

    file = load_for_edit(meeting_path)
    result = save_buffer(meeting_path, ticked_text, file, workspace=tmp_workspace)
    assert result.ok is True
    saved = meeting_path.read_text(encoding="utf-8")
    assert "- [x] [call Terry]" in saved


def test_several_documents_mirroring_the_same_task_are_all_left_unmodified(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    note = create_note(tmp_workspace, "scratch")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None

    meeting_text = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(meeting_text + line + "\n", encoding="utf-8")
    note_text = note.path.read_text(encoding="utf-8")
    note.path.write_text(note_text + line + "\n", encoding="utf-8")

    meeting_before = meeting.path.read_bytes()
    note_before = note.path.read_bytes()

    delete_by_id(tmp_workspace, task.id)

    assert meeting.path.read_bytes() == meeting_before
    assert note.path.read_bytes() == note_before
