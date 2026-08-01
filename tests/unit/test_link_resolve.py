from __future__ import annotations

from endpaper.core.links import Link, relative_destination, resolve_id, resolve_link
from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.core.tasks import add_task


def test_id_resolves_regardless_of_wrong_path(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    link = Link(
        source=tmp_workspace.notes_dir / "x.md",
        line=1,
        text="Q3",
        path="totally/wrong/path.md",
        target_id=meeting.id,
        start=0,
        end=0,
    )
    target, status = resolve_link(tmp_workspace, link)
    assert target is not None
    assert target.id == meeting.id
    assert status == "stale"


def test_id_resolves_and_path_correct_is_resolved(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    source = tmp_workspace.notes_dir / "2026" / "07" / "x.md"
    correct = relative_destination(source, meeting.path)
    link = Link(
        source=source, line=1, text="Q3", path=correct, target_id=meeting.id, start=0, end=0
    )
    target, status = resolve_link(tmp_workspace, link)
    assert target is not None
    assert status == "resolved"


def test_id_absent_path_present_resolves_is_stale(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    source = tmp_workspace.notes_dir / "2026" / "07" / "x.md"
    correct = relative_destination(source, meeting.path)
    link = Link(source=source, line=1, text="Q3", path=correct, target_id=None, start=0, end=0)
    target, status = resolve_link(tmp_workspace, link)
    assert target is not None
    assert target.id == meeting.id
    assert status == "stale"


def test_id_does_not_resolve_is_dead_even_if_path_is_valid(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    source = tmp_workspace.notes_dir / "2026" / "07" / "x.md"
    valid_path = relative_destination(source, meeting.path)
    link = Link(
        source=source,
        line=1,
        text="Q3",
        path=valid_path,
        target_id="meeting_00000000_deadbeef",
        start=0,
        end=0,
    )
    target, status = resolve_link(tmp_workspace, link)
    assert target is None
    assert status == "dead"


def test_neither_id_nor_path_resolves_is_dead(tmp_workspace: Workspace) -> None:
    link = Link(
        source=tmp_workspace.notes_dir / "x.md",
        line=1,
        text="nope",
        path="nowhere/at/all.md",
        target_id=None,
        start=0,
        end=0,
    )
    target, status = resolve_link(tmp_workspace, link)
    assert target is None
    assert status == "dead"


def test_old_prefix_id_resolves_unchanged(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    text = meeting.path.read_text(encoding="utf-8")
    old_id = "m_" + meeting.id.removeprefix("meeting_")
    meeting.path.write_text(text.replace(f"id: {meeting.id}", f"id: {old_id}"), encoding="utf-8")

    target, warnings = resolve_id(tmp_workspace, old_id)
    assert target is not None
    assert target.id == old_id
    assert not any(w.reason == "link_ambiguous" for w in warnings)


def test_duplicate_ids_resolve_deterministically_with_a_warning(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "first")
    # Beside the real file, not a hardcoded YYYY/MM -- `create_meeting` files by
    # today's date, so a literal month is only correct until the month turns.
    duplicate_path = meeting.path.with_name("z-duplicate.md")
    text = meeting.path.read_text(encoding="utf-8")
    duplicate_path.write_text(text, encoding="utf-8")

    target1, warnings1 = resolve_id(tmp_workspace, meeting.id)
    target2, warnings2 = resolve_id(tmp_workspace, meeting.id)

    assert target1 is not None and target2 is not None
    assert target1.path == target2.path  # deterministic
    assert any(w.reason == "link_ambiguous" for w in warnings1)
    assert any(w.reason == "link_ambiguous" for w in warnings2)


def test_dead_id_returns_none_not_an_exception(tmp_workspace: Workspace) -> None:
    target, warnings = resolve_id(tmp_workspace, "meeting_00000000_deadbeef")
    assert target is None
    assert warnings == ()


def test_task_id_resolves_to_tasks_file(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    target, _warnings = resolve_id(tmp_workspace, task.id)
    assert target is not None
    assert target.kind == "task"
    assert target.path == tmp_workspace.tasks_file
    assert target.line == task.line


def test_note_id_resolves(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "vendor landscape")
    target, _warnings = resolve_id(tmp_workspace, note.id)
    assert target is not None
    assert target.kind == "note"


def test_task_link_never_becomes_resolved_with_a_path(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    link = Link(
        source=tmp_workspace.tasks_file,
        line=4,
        text="call Terry",
        path=None,
        target_id=meeting.id,
        start=0,
        end=0,
        in_tasks_field=True,
    )
    target, status = resolve_link(tmp_workspace, link)
    assert target is not None
    assert status == "resolved"


def test_task_link_to_a_dead_id_is_dead(tmp_workspace: Workspace) -> None:
    link = Link(
        source=tmp_workspace.tasks_file,
        line=4,
        text="call Terry",
        path=None,
        target_id="meeting_00000000_deadbeef",
        start=0,
        end=0,
        in_tasks_field=True,
    )
    target, status = resolve_link(tmp_workspace, link)
    assert target is None
    assert status == "dead"
