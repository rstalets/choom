from __future__ import annotations

from pathlib import Path

from endpaper.core.mirrors import reconcile_on_save
from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task, get_task

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
    from endpaper.core.tasks import set_task_state

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
    from endpaper.core.tasks import set_task_state

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
