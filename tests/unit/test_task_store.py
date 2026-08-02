"""Unit coverage for `core.task_store` (019-completed-tasks-partition) --
path derivation, the two splices, the three loaders' scopes, the move's
round trip and no-op contract, and the stat fingerprint. Everything here is
decidable against a `tmp_path`/`tmp_workspace`, no terminal involved
(plan.md gate VI)."""

from __future__ import annotations

import os
import stat
from datetime import date, datetime

from choom.core.errors import NotFoundError, UsageError
from choom.core.models import Workspace
from choom.core.task_store import (
    _with_completed,
    _without_completed,
    done_file_for,
    iter_done_files,
    load_done_tasks,
    load_task_store,
    move_record,
    store_fingerprint,
)
from choom.core.tasks import add_task, load_tasks
from tests.conftest import tasks_file, write_tasks

# --- C1: done_file_for -----------------------------------------------------


def test_done_file_for_is_a_pure_yyyy_mm_dd_done_path(tmp_workspace: Workspace) -> None:
    path = done_file_for(tmp_workspace, date(2026, 8, 2))
    assert path == tmp_workspace.root / "tasks" / "done" / "2026" / "08" / "2026-08-02-done.md"
    assert not path.exists()  # pure function -- creates nothing


# --- C2: iter_done_files -----------------------------------------------------


def test_iter_done_files_on_an_absent_root_is_empty(tmp_workspace: Workspace) -> None:
    assert iter_done_files(tmp_workspace) == []


def test_iter_done_files_lists_newest_day_first(tmp_workspace: Workspace) -> None:
    for day in (date(2026, 1, 5), date(2026, 8, 2), date(2026, 3, 14)):
        path = done_file_for(tmp_workspace, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("- [x] whatever <!-- id:task_x -->\n", encoding="utf-8")

    files = iter_done_files(tmp_workspace)
    assert [p.name for p in files] == [
        "2026-08-02-done.md",
        "2026-03-14-done.md",
        "2026-01-05-done.md",
    ]


def test_iter_done_files_skips_an_unreadable_directory(tmp_workspace: Workspace) -> None:
    good = done_file_for(tmp_workspace, date(2026, 1, 1))
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text("- [x] fine <!-- id:task_ok -->\n", encoding="utf-8")

    blocked_dir = tmp_workspace.done_dir / "2025" / "12"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    (blocked_dir / "2025-12-31-done.md").write_text("- [x] hidden\n", encoding="utf-8")
    original_mode = blocked_dir.stat().st_mode
    os.chmod(blocked_dir, stat.S_IRUSR)
    try:
        files = iter_done_files(tmp_workspace)
        assert good in files
    finally:
        os.chmod(blocked_dir, original_mode)


# --- The two splices (research R2, F4) --------------------------------------


def test_with_completed_appends_after_the_last_field_preserving_spacing() -> None:
    content = "- [ ] call Terry <!-- id:task_a1b2 created:2026-07-28 -->"
    spliced = _with_completed(content, date(2026, 8, 2))
    assert spliced == (
        "- [ ] call Terry <!-- id:task_a1b2 created:2026-07-28 completed:2026-08-02 -->"
    )


def test_with_completed_preserves_unusual_internal_spacing() -> None:
    content = "- [ ] x <!--  id:task_a1b2   created:2026-07-28  -->"
    spliced = _with_completed(content, date(2026, 8, 2))
    # everything up to the inserted field is untouched, including the
    # user's own double spaces; only the trailing run before "-->" is
    # normalized to the one space the insertion needs.
    assert spliced.startswith("- [ ] x <!--  id:task_a1b2   created:2026-07-28")
    assert "completed:2026-08-02" in spliced
    assert spliced.endswith("-->")


def test_completed_insert_then_remove_round_trips_to_the_original_bytes() -> None:
    content = "- [ ] call Terry <!-- id:task_a1b2 created:2026-07-28 -->"
    round_tripped = _without_completed(_with_completed(content, date(2026, 8, 2)))
    assert round_tripped == content


def test_without_completed_drops_the_field_and_its_leading_space() -> None:
    content = "- [x] call Terry <!-- id:task_a1b2 created:2026-07-28 completed:2026-08-02 -->"
    spliced = _without_completed(content)
    assert spliced == "- [x] call Terry <!-- id:task_a1b2 created:2026-07-28 -->"
    assert "completed:" not in spliced


# --- C3/C4: the three loaders' scopes ----------------------------------------


def test_load_done_tasks_reads_every_day_file_and_stamps_source(
    tmp_workspace: Workspace,
) -> None:
    day_a = done_file_for(tmp_workspace, date(2026, 1, 1))
    day_a.parent.mkdir(parents=True, exist_ok=True)
    day_a.write_text("- [x] one <!-- id:task_aaaa completed:2026-01-01 -->\n", encoding="utf-8")

    day_b = done_file_for(tmp_workspace, date(2026, 2, 2))
    day_b.parent.mkdir(parents=True, exist_ok=True)
    day_b.write_text("- [x] two <!-- id:task_bbbb completed:2026-02-02 -->\n", encoding="utf-8")

    tasks, warnings = load_done_tasks(tmp_workspace)
    assert warnings == []
    by_id = {t.id: t for t in tasks}
    assert by_id["task_aaaa"].source == day_a
    assert by_id["task_bbbb"].source == day_b
    assert by_id["task_aaaa"].completed == date(2026, 1, 1)


def test_load_done_tasks_warns_on_one_unreadable_file_without_stopping_the_rest(
    tmp_workspace: Workspace,
) -> None:
    good = done_file_for(tmp_workspace, date(2026, 1, 1))
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_text("- [x] fine <!-- id:task_ok -->\n", encoding="utf-8")

    bad = done_file_for(tmp_workspace, date(2026, 2, 2))
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("- [x] blocked <!-- id:task_blocked -->\n", encoding="utf-8")
    original_mode = bad.stat().st_mode
    os.chmod(bad, 0o000)
    try:
        tasks, warnings = load_done_tasks(tmp_workspace)
        assert any(t.id == "task_ok" for t in tasks)
        assert not any(t.id == "task_blocked" for t in tasks)
        assert len(warnings) == 1
        assert "task_unreadable_file" == warnings[0].reason
    finally:
        os.chmod(bad, original_mode)


def test_load_done_tasks_backfills_a_bare_checkbox_best_effort(
    tmp_workspace: Workspace,
) -> None:
    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [x] paid the invoice\n", encoding="utf-8")

    tasks, warnings = load_done_tasks(tmp_workspace)
    assert warnings == []
    assert len(tasks) == 1
    assert tasks[0].id is not None

    text_after = day.read_text(encoding="utf-8")
    assert "id:" in text_after


def test_load_task_store_is_tasks_md_then_the_done_store(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] open one <!-- id:task_open -->\n")
    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [x] done one <!-- id:task_done -->\n", encoding="utf-8")

    tasks, warnings = load_task_store(tmp_workspace)
    assert warnings == []
    assert [t.id for t in tasks] == ["task_open", "task_done"]


def test_an_open_record_hand_written_into_a_day_file_lists_as_open_and_is_not_relocated(
    tmp_workspace: Workspace,
) -> None:
    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [ ] hand-edited open <!-- id:task_odd -->\n", encoding="utf-8")

    tasks, _warnings = load_done_tasks(tmp_workspace)
    assert tasks[0].done is False

    # No read here moves it -- location is never authoritative (FR-005).
    assert day.read_text(encoding="utf-8") == "- [ ] hand-edited open <!-- id:task_odd -->\n"
    assert not tasks_file(tmp_workspace).exists() or "task_odd" not in tasks_file(
        tmp_workspace
    ).read_text(encoding="utf-8")


# --- C5: move_record ---------------------------------------------------------


def test_move_record_round_trip_preserves_type_tags_links_and_body(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(
        tmp_workspace,
        "call Terry",
        type="followup",
        tags=("vendor",),
        links=("meeting_20260728_a1b2c3d4",),
    )
    assert task.id is not None
    path = tasks_file(tmp_workspace)
    path.write_text(
        path.read_text(encoding="utf-8") + "\n  the contract auto-renews on the 15th\n",
        encoding="utf-8",
    )

    now = datetime(2026, 8, 2, 9, 0)
    completed = move_record(tmp_workspace, task.id, done=True, now=now)
    assert completed.done is True
    assert completed.completed == date(2026, 8, 2)
    assert completed.source == done_file_for(tmp_workspace, date(2026, 8, 2))
    assert completed.type == "followup"
    assert completed.tags == ("vendor",)
    assert completed.links == ("meeting_20260728_a1b2c3d4",)
    assert completed.body == "the contract auto-renews on the 15th"
    assert task.id not in tasks_file(tmp_workspace).read_text(encoding="utf-8")

    reopened = move_record(tmp_workspace, task.id, done=False, now=now)
    assert reopened.done is False
    assert reopened.completed is None
    assert reopened.source == tasks_file(tmp_workspace)
    assert reopened.type == "followup"
    assert reopened.tags == ("vendor",)
    assert reopened.links == ("meeting_20260728_a1b2c3d4",)
    assert reopened.body == "the contract auto-renews on the 15th"
    assert reopened.id == task.id  # identity preserved -- never a new id


def test_move_record_no_op_writes_nothing_in_either_direction(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "buy milk")
    assert task.id is not None
    before = tasks_file(tmp_workspace).read_bytes()

    result = move_record(tmp_workspace, task.id, done=False)
    assert result.done is False
    assert tasks_file(tmp_workspace).read_bytes() == before


def test_move_record_leaves_a_pre_existing_completed_task_in_tasks_md_on_a_noop(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [x] already done <!-- id:task_old -->\n")
    before = tasks_file(tmp_workspace).read_bytes()

    result = move_record(tmp_workspace, "task_old", done=True)
    assert result.source == tasks_file(tmp_workspace)
    assert tasks_file(tmp_workspace).read_bytes() == before


def test_move_record_leaves_a_hand_edited_open_record_in_a_day_file_on_a_noop(
    tmp_workspace: Workspace,
) -> None:
    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [ ] hand-edited open <!-- id:task_odd -->\n", encoding="utf-8")
    before = day.read_bytes()

    result = move_record(tmp_workspace, "task_odd", done=False)
    assert result.source == day
    assert day.read_bytes() == before


def test_move_record_not_found_raises(tmp_workspace: Workspace) -> None:
    try:
        move_record(tmp_workspace, "task_zzzz", done=True)
    except NotFoundError:
        pass
    else:
        raise AssertionError("expected NotFoundError")


def test_move_record_ambiguous_across_files_names_both(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] one <!-- id:task_dupe -->\n")
    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [x] two <!-- id:task_dupe -->\n", encoding="utf-8")

    try:
        move_record(tmp_workspace, "task_dupe", done=True)
    except UsageError as exc:
        assert "tasks.md:1" in str(exc)
        assert "2026-01-01-done.md:1" in str(exc)
    else:
        raise AssertionError("expected UsageError")


def test_reopen_and_complete_again_on_a_later_day_lands_in_the_later_days_file(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    move_record(tmp_workspace, task.id, done=True, now=datetime(2026, 1, 1))
    move_record(tmp_workspace, task.id, done=False, now=datetime(2026, 1, 2))
    result = move_record(tmp_workspace, task.id, done=True, now=datetime(2026, 3, 3))

    assert result.source == done_file_for(tmp_workspace, date(2026, 3, 3))
    assert not done_file_for(tmp_workspace, date(2026, 1, 1)).read_text(encoding="utf-8")


def test_reopening_a_record_leaves_the_now_empty_day_file_in_place(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    when = datetime(2026, 1, 1)
    move_record(tmp_workspace, task.id, done=True, now=when)
    day_path = done_file_for(tmp_workspace, when.date())
    assert day_path.exists()

    move_record(tmp_workspace, task.id, done=False, now=when)
    assert day_path.exists()
    assert day_path.read_text(encoding="utf-8") == ""


# --- C6: store_fingerprint ----------------------------------------------------


def test_store_fingerprint_changes_when_a_file_is_added_removed_or_grown(
    tmp_workspace: Workspace,
) -> None:
    empty = store_fingerprint(tmp_workspace)
    assert empty == ()

    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [x] one <!-- id:task_a -->\n", encoding="utf-8")
    added = store_fingerprint(tmp_workspace)
    assert added != empty

    day.write_text(
        day.read_text(encoding="utf-8") + "- [x] two <!-- id:task_b -->\n", encoding="utf-8"
    )
    grown = store_fingerprint(tmp_workspace)
    assert grown != added

    day.unlink()
    removed = store_fingerprint(tmp_workspace)
    assert removed == empty


def test_store_fingerprint_never_opens_a_file(tmp_workspace: Workspace) -> None:
    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [x] one <!-- id:task_a -->\n", encoding="utf-8")
    os.chmod(day, 0o000)
    try:
        # A file with no read permission can still be *stat*'d; the
        # fingerprint must not fail or need to open it.
        fingerprint = store_fingerprint(tmp_workspace)
        assert len(fingerprint) == 1
    finally:
        os.chmod(day, 0o644)


def test_load_tasks_is_unaffected_by_a_populated_done_store(tmp_workspace: Workspace) -> None:
    """FR-018/SC-003's other half: load_tasks (unlike load_task_store) never
    looks at the done store at all."""
    write_tasks(tmp_workspace, "- [ ] open <!-- id:task_open -->\n")
    day = done_file_for(tmp_workspace, date(2026, 1, 1))
    day.parent.mkdir(parents=True, exist_ok=True)
    day.write_text("- [x] done <!-- id:task_done -->\n", encoding="utf-8")

    tasks, _warnings = load_tasks(tmp_workspace)
    assert [t.id for t in tasks] == ["task_open"]
