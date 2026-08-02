"""SC-007: both partial-failure orderings of `move_record`
(019-completed-tasks-partition, research R3). This is the evidence for the
write-ordering decision -- if someone later inverts the writes, this file
goes red."""

from __future__ import annotations

import os
import stat
from datetime import date, datetime

import pytest

from choom.core import task_store as task_store_module
from choom.core.atomic_write import write_text_atomic as _real_write_text_atomic
from choom.core.errors import UsageError, WorkspaceError
from choom.core.models import Workspace
from choom.core.task_store import done_file_for, move_record
from choom.core.tasks import add_task
from tests.conftest import tasks_file


def test_destination_unwritable_source_untouched_task_still_open(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    before = tasks_file(tmp_workspace).read_bytes()

    # The destination's directory tree (tasks/done/2026/08/) does not exist
    # yet, and creating it needs write access to the workspace root --
    # locking that down makes the *first* write (the destination) fail
    # before tasks.md is ever touched.
    original_mode = tmp_workspace.root.stat().st_mode
    os.chmod(tmp_workspace.root, stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(WorkspaceError):
            move_record(tmp_workspace, task.id, done=True, now=datetime(2026, 8, 2))
    finally:
        os.chmod(tmp_workspace.root, original_mode)

    assert tasks_file(tmp_workspace).read_bytes() == before
    assert not done_file_for(tmp_workspace, date(2026, 8, 2)).exists()


def test_source_unwritable_after_destination_succeeds_record_exists_in_both(
    tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reverse ordering: the destination write (the done-store file)
    succeeds, and only *then* does the source write (tasks.md) fail --
    exactly the failure the destination-first ordering is designed to
    convert into "duplicate", never "dropped"."""
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None

    calls = {"n": 0}

    def _write_then_lock_root(path, text):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        result = _real_write_text_atomic(path, text)
        if calls["n"] == 1:
            # The destination write (the done-store file) just succeeded.
            # Lock the workspace root -- tasks.md's own parent directory,
            # which write_text_atomic's same-directory temp file needs --
            # so the *second* write is the one that fails.
            os.chmod(tmp_workspace.root, stat.S_IRUSR | stat.S_IXUSR)
        return result

    monkeypatch.setattr(task_store_module, "write_text_atomic", _write_then_lock_root)

    try:
        with pytest.raises(WorkspaceError) as excinfo:
            move_record(tmp_workspace, task.id, done=True, now=datetime(2026, 8, 2))
    finally:
        os.chmod(tmp_workspace.root, stat.S_IRUSR | stat.S_IXUSR | stat.S_IWUSR)

    assert calls["n"] == 2
    message = str(excinfo.value)
    assert "both" in message

    # The record now exists in both places -- no line was lost.
    done_path = done_file_for(tmp_workspace, date(2026, 8, 2))
    assert done_path.exists()
    assert task.id in done_path.read_text(encoding="utf-8")
    assert task.id in tasks_file(tmp_workspace).read_text(encoding="utf-8")

    # And every subsequent operation refuses rather than acting on an
    # ambiguous id (FR-014) -- this is the whole recovery story.
    with pytest.raises(UsageError):
        move_record(tmp_workspace, task.id, done=True)
