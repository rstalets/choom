from __future__ import annotations

import pytest

from choom.core.deletion import delete_by_id
from choom.core.errors import NotFoundError, UsageError
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.notes import create_note
from choom.core.tasks import add_task, load_tasks
from tests.conftest import write_tasks


def test_unresolvable_id_raises_not_found_error(tmp_workspace: Workspace) -> None:
    with pytest.raises(NotFoundError):
        delete_by_id(tmp_workspace, "meeting_zzzz")


def test_ambiguous_id_raises_usage_error_naming_every_path(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] first <!-- id:task_dupe -->\n- [ ] second <!-- id:task_dupe -->\n",
    )

    with pytest.raises(UsageError, match="task_dupe"):
        delete_by_id(tmp_workspace, "task_dupe")

    # Nothing was deleted.
    tasks, _warnings = load_tasks(tmp_workspace)
    assert len(tasks) == 2


def test_expect_mismatch_raises_not_found_error(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "an idea")

    with pytest.raises(NotFoundError, match="meeting"):
        delete_by_id(tmp_workspace, note.id, expect="meeting")

    assert note.path.is_file()


def test_meeting_routed_to_document_deletion(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")

    deleted = delete_by_id(tmp_workspace, meeting.id)

    assert deleted.kind == "meeting"
    assert deleted.id == meeting.id
    assert deleted.title == meeting.title
    assert deleted.path == meeting.path
    assert not meeting.path.exists()


def test_note_routed_to_document_deletion(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "an idea")

    deleted = delete_by_id(tmp_workspace, note.id)

    assert deleted.kind == "note"
    assert not note.path.exists()


def test_task_routed_to_task_deletion(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "buy milk")
    assert task.id is not None

    deleted = delete_by_id(tmp_workspace, task.id)

    assert deleted.kind == "task"
    assert deleted.id == task.id
    assert deleted.title == "buy milk"
    assert deleted.path == tmp_workspace.tasks_file
    tasks, _warnings = load_tasks(tmp_workspace)
    assert tasks == []


def test_expect_matching_kind_succeeds(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")

    deleted = delete_by_id(tmp_workspace, meeting.id, expect="meeting")

    assert deleted.kind == "meeting"
    assert not meeting.path.exists()
