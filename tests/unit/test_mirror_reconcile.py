from __future__ import annotations

from pathlib import Path

import pytest

from choom.core import mirrors as mirrors_module
from choom.core.mirrors import reconcile_on_open, reconcile_on_save
from choom.core.models import Workspace
from choom.core.tasks import add_task, get_task, set_task_state

_SOURCE = Path("/ws/meetings/2026/07/2026-07-28-q3-planning.md")


def _mirror_text(task_id: str, *, done: bool) -> str:
    state = "x" if done else " "
    return f"- [{state}] [call Terry](../../../tasks.md#{task_id})\n"


def test_unchanged_writes_nothing(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    before = tmp_workspace.tasks_file.read_text(encoding="utf-8")

    text = _mirror_text(task.id, done=False)
    report = reconcile_on_save(tmp_workspace, text, source=_SOURCE, baseline={task.id: False})

    assert report.text is text
    assert report.resolutions[0].outcome == "unchanged"
    assert not report.warnings
    assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == before


def test_mirror_ticked_writes_tasks_md(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None

    text = _mirror_text(task.id, done=True)
    report = reconcile_on_save(tmp_workspace, text, source=_SOURCE, baseline={task.id: False})

    assert report.resolutions[0].outcome == "task_written"
    assert not report.warnings
    assert get_task(tmp_workspace, task.id).done is True
    # The document text itself is untouched -- the mirror already reads as ticked.
    assert report.text is text


def test_task_completed_elsewhere_corrects_the_mirror(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    set_task_state(tmp_workspace, task.id, done=True)

    text = _mirror_text(task.id, done=False)
    report = reconcile_on_save(tmp_workspace, text, source=_SOURCE, baseline={task.id: False})

    assert report.resolutions[0].outcome == "mirror_corrected"
    assert report.text != text
    assert "[x]" in report.text
    assert not report.warnings


def test_both_changed_writes_and_warns(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    set_task_state(tmp_workspace, task.id, done=True)  # task changed elsewhere

    text = _mirror_text(task.id, done=True)  # mirror also ticked, independently
    report = reconcile_on_save(tmp_workspace, text, source=_SOURCE, baseline={task.id: False})

    assert report.resolutions[0].outcome == "conflict"
    assert len(report.warnings) == 1
    assert report.warnings[0].reason == "mirror_conflict"
    assert get_task(tmp_workspace, task.id).done is True


def test_mirror_absent_from_baseline_counts_as_the_users_edit(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None

    text = _mirror_text(task.id, done=True)
    report = reconcile_on_save(tmp_workspace, text, source=_SOURCE, baseline={})

    assert report.resolutions[0].outcome == "task_written"
    assert get_task(tmp_workspace, task.id).done is True


def test_two_disagreeing_mirrors_leaves_tasks_md_untouched_and_warns(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None

    text = _mirror_text(task.id, done=True) + _mirror_text(task.id, done=False)
    report = reconcile_on_save(tmp_workspace, text, source=_SOURCE, baseline={task.id: False})

    assert report.resolutions[0].outcome == "ambiguous"
    assert len(report.warnings) == 1
    assert report.warnings[0].reason == "mirror_ambiguous"
    assert get_task(tmp_workspace, task.id).done is False
    assert report.text is text


def test_a_dead_mirror_is_left_byte_identical_and_warned_about(tmp_workspace: Workspace) -> None:
    text = _mirror_text("task_doesnotexist", done=True)
    report = reconcile_on_save(
        tmp_workspace, text, source=_SOURCE, baseline={"task_doesnotexist": False}
    )

    assert report.resolutions[0].outcome == "dead"
    assert report.text is text
    assert len(report.warnings) == 1
    assert report.warnings[0].reason == "link_dead"


def test_no_mirrors_returns_the_identical_object_and_reads_nothing(
    tmp_workspace: Workspace,
) -> None:
    text = "just some prose\n"
    report = reconcile_on_save(tmp_workspace, text, source=_SOURCE, baseline={})
    assert report.text is text
    assert report.resolutions == ()
    assert report.warnings == ()


# --- C8 escalation: SC-004, preserving spec 008's SC-008 --------------------


def test_reconcile_on_open_never_touches_the_done_store_when_every_mirror_resolves(
    tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A document whose mirrors all name open tasks costs exactly one file
    read -- the done store is never consulted (019-completed-tasks-
    partition, research R5, contracts/core-api.md C8)."""
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_done_tasks must not be called when tasks.md resolves everything")

    monkeypatch.setattr(mirrors_module, "load_done_tasks", _boom)

    text = _mirror_text(task.id, done=False)
    report = reconcile_on_open(tmp_workspace, text, source=_SOURCE)
    assert report.resolutions[0].outcome == "unchanged"


def test_reconcile_on_open_escalates_exactly_once_for_a_completed_mirror(
    tmp_workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bug 2's fix, pinned at the unit level: once a mirror's id is not in
    tasks.md, the done store is read -- and read only once, however many
    unresolved mirrors the document holds."""
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    set_task_state(tmp_workspace, task.id, done=True)

    calls = {"n": 0}
    real_load_done_tasks = mirrors_module.load_done_tasks

    def _counting(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return real_load_done_tasks(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(mirrors_module, "load_done_tasks", _counting)

    text = _mirror_text(task.id, done=False) + _mirror_text(task.id, done=False)
    report = reconcile_on_open(tmp_workspace, text, source=_SOURCE)

    assert calls["n"] == 1
    assert "[x]" in report.text
    assert report.warnings == ()
