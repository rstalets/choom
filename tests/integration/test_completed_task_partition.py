"""019-completed-tasks-partition: the round trip (US1/US2), the negative
guarantee that an existing vault is never swept (US5), the canonical-address
property that makes a completion invisible to link checking (US3), and the
two named regressions this feature both introduces and fixes: bug 1
(`ctrl+t` orphaning a completed record) and bug 2 (`reconcile_on_open`
reporting a completed mirror dead).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from textual.widgets import TextArea

from choom.core.links import check_links, heal_links
from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_task, reconcile_on_open
from choom.core.models import Workspace
from choom.core.task_store import done_file_for, load_task_store
from choom.core.tasks import add_task, get_task, load_tasks, set_task_state
from choom.core.workspace import find_workspace, init_workspace
from choom.tui.app import ChoomApp
from tests.conftest import tasks_file
from tests.helpers import open_edit

# --- US5: an existing workspace is not swept ---------------------------------


def _seed_pre_existing_workspace(tmp_workspace: Workspace, count: int = 300) -> str:
    """Every seeded line is completed, as if this workspace had used choom
    daily for a year before this feature ever shipped (US5)."""
    lines = [
        f"- [x] task number {i} <!-- id:task_{i:04x} created:2026-01-{(i % 28) + 1:02d} -->"
        for i in range(count)
    ]
    text = "\n".join(lines) + "\n"
    tasks_file(tmp_workspace).write_text(text, encoding="utf-8", newline="\n")
    return text


def test_a_workspace_with_300_completed_lines_is_byte_identical_after_every_read(
    tmp_workspace: Workspace,
) -> None:
    """SC-008/FR-037: none of launch, every read command, opening a
    document, or a link check may move a single one of these lines."""
    original = _seed_pre_existing_workspace(tmp_workspace)
    meeting = create_meeting(tmp_workspace, "unrelated meeting", type="standup")

    load_tasks(tmp_workspace)
    load_task_store(tmp_workspace)
    check_links(tmp_workspace)
    meeting.path.read_text(encoding="utf-8")

    assert tasks_file(tmp_workspace).read_text(encoding="utf-8") == original


def test_pre_existing_completed_tasks_appear_in_every_done_view_with_no_completion_date(
    tmp_workspace: Workspace,
) -> None:
    _seed_pre_existing_workspace(tmp_workspace, count=5)

    tasks, warnings = load_task_store(tmp_workspace)
    assert warnings == []
    assert len(tasks) == 5
    assert all(t.done for t in tasks)
    assert all(t.completed is None for t in tasks)


def test_only_a_real_transition_moves_a_pre_existing_completed_task(
    tmp_workspace: Workspace,
) -> None:
    _seed_pre_existing_workspace(tmp_workspace, count=3)
    before = tasks_file(tmp_workspace).read_text(encoding="utf-8")

    # Reading it does not move it...
    load_task_store(tmp_workspace)
    assert tasks_file(tmp_workspace).read_text(encoding="utf-8") == before

    # ...but reopening, then completing it again, does (US5 scenario 3).
    set_task_state(tmp_workspace, "task_0000", done=False)
    when = datetime(2026, 8, 2)
    result = set_task_state(tmp_workspace, "task_0000", done=True, now=when)
    assert result.source == done_file_for(tmp_workspace, when.date())
    assert "task_0000" not in tasks_file(tmp_workspace).read_text(encoding="utf-8")


# --- US1: completing moves the record (T028) ---------------------------------


def test_completing_lands_in_todays_file_with_the_stamp_and_leaves_no_trace(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "call Terry", type="followup", tags=("vendor",))
    assert task.id is not None
    path = tasks_file(tmp_workspace)
    path.write_text(
        path.read_text(encoding="utf-8") + "\n  the contract auto-renews on the 15th\n",
        encoding="utf-8",
    )

    when = datetime(2026, 8, 2, 9, 0)
    set_task_state(tmp_workspace, task.id, done=True, now=when)

    assert task.id not in tasks_file(tmp_workspace).read_text(encoding="utf-8")
    done_path = done_file_for(tmp_workspace, when.date())
    done_text = done_path.read_text(encoding="utf-8")
    assert f"completed:{when.date().isoformat()}" in done_text
    assert "the contract auto-renews on the 15th" in done_text

    shown = get_task(tmp_workspace, task.id)
    assert shown.body == "the contract auto-renews on the 15th"
    assert shown.type == "followup"
    assert shown.tags == ("vendor",)
    assert shown.done is True


# --- Blast radius (T029, SC-006) ----------------------------------------------


def test_completing_writes_no_file_outside_the_store_and_the_linked_document(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    other_meeting = create_meeting(tmp_workspace, "unrelated", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8"
    )

    before: dict[Path, float] = {}
    for candidate in tmp_workspace.root.rglob("*.md"):
        if candidate not in (tasks_file(tmp_workspace), meeting.path):
            before[candidate] = candidate.stat().st_mtime_ns

    set_task_state(tmp_workspace, task.id, done=True)

    for candidate, mtime in before.items():
        assert candidate.stat().st_mtime_ns == mtime, f"{candidate} was written unexpectedly"
    assert other_meeting.path.stat().st_mtime_ns == before[other_meeting.path]


# --- US2: unticking brings it back, with everything intact (T030) -----------


def test_complete_then_reopen_returns_tasks_md_to_its_original_content(
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
    original = tasks_file(tmp_workspace).read_text(encoding="utf-8")

    when = datetime(2026, 8, 2)
    set_task_state(tmp_workspace, task.id, done=True, now=when)
    set_task_state(tmp_workspace, task.id, done=False, now=when)

    after = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert after == original

    reopened = get_task(tmp_workspace, task.id)
    assert reopened.created == task.created
    assert reopened.type == task.type
    assert reopened.tags == task.tags
    assert reopened.links == task.links
    assert reopened.body == task.body
    assert reopened.id == task.id
    assert reopened.completed is None


def test_the_emptied_day_file_is_left_in_place_not_pruned(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    when = datetime(2026, 8, 2)

    set_task_state(tmp_workspace, task.id, done=True, now=when)
    day_path = done_file_for(tmp_workspace, when.date())
    assert day_path.exists()

    set_task_state(tmp_workspace, task.id, done=False, now=when)
    assert day_path.exists()
    assert day_path.read_text(encoding="utf-8") == ""


def test_reopen_then_complete_on_a_later_day_lands_in_the_later_days_file(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None

    set_task_state(tmp_workspace, task.id, done=True, now=datetime(2026, 1, 1))
    set_task_state(tmp_workspace, task.id, done=False, now=datetime(2026, 1, 2))
    result = set_task_state(tmp_workspace, task.id, done=True, now=datetime(2026, 3, 3))

    assert result.source == done_file_for(tmp_workspace, date(2026, 3, 3))
    assert done_file_for(tmp_workspace, date(2026, 1, 1)).read_text(encoding="utf-8") == ""


# --- US3: the canonical address means no staleness (T016, FR-026, SC-009) ---


def test_a_mirror_of_a_completed_task_in_a_hand_written_day_file_is_never_stale(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + line.replace("[ ]", "[x]") + "\n",
        encoding="utf-8",
    )

    day_path = done_file_for(tmp_workspace, date(2026, 8, 2))
    day_path.parent.mkdir(parents=True, exist_ok=True)
    day_path.write_text(
        f"- [x] call Terry <!-- id:{task.id} links:{meeting.id} "
        "created:2026-07-28 completed:2026-08-02 -->\n",
        encoding="utf-8",
    )

    reports = check_links(tmp_workspace)
    assert not any(r.status in ("stale", "dead") for r in reports)

    healed = heal_links(tmp_workspace)
    assert not any(r.status == "stale" for r in healed)
    # heal_links rewrote nothing -- the mirror's own bytes are untouched.
    assert meeting.path.read_text(encoding="utf-8").count(f"#{task.id}") == 1


# --- Bug 2 regression: reconcile-on-open ticks a completed mirror ------------


async def test_regression_reconcile_on_open_ticks_a_completed_mirror_with_no_warning(
    tmp_workspace: Workspace,
) -> None:
    """The bug this feature could have introduced but must not: once a
    completed record moved out of tasks.md, an unescalated reconcile would
    treat every completed mirror as dead. Named regression test (T018)."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8"
    )

    # The task is completed from the tasks list -- the document is not open
    # -- so the record moves into today's done-store file, and the mirror
    # left in the document is now stale relative to `tasks.md` alone.
    set_task_state(tmp_workspace, task.id, done=True, now=datetime(2026, 8, 2))

    text = meeting.path.read_text(encoding="utf-8")
    report = reconcile_on_open(tmp_workspace, text, source=meeting.path)

    assert report.warnings == ()
    assert "[x]" in report.text
    assert not any(r.outcome == "dead" for r in report.resolutions)


async def test_regression_reconcile_on_open_via_the_real_tui_open(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8"
    )

    set_task_state(tmp_workspace, task.id, done=True, now=datetime(2026, 8, 2))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        assert "- [x] [call Terry]" in editor.text


# --- Bug 1 regression: ctrl+t removes both halves of a completed task ------


async def test_regression_ctrl_t_removes_both_the_document_line_and_the_done_record(
    tmp_workspace: Workspace,
) -> None:
    """The serious bug this feature could have introduced: before the fix,
    `plan_mirror_deletion` only ever opened tasks.md, so a completed record
    resolved to nothing, took the `line_only` branch, and `ctrl+t` deleted
    the user's document line while the record survived, orphaned, in the
    done store. Named regression test (T020)."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None

    # Complete it from the tasks list -- the record moves into today's
    # done-store file, but the document's mirror (about to be typed into
    # the editor buffer below) still names the same id.
    set_task_state(tmp_workspace, task.id, done=True, now=datetime(2026, 8, 2))
    day_path = done_file_for(tmp_workspace, date(2026, 8, 2))
    assert task.id in day_path.read_text(encoding="utf-8")

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

        assert task.id not in editor.text
        assert task.id not in day_path.read_text(encoding="utf-8")


async def test_a_mirror_whose_id_is_in_neither_half_of_the_store_is_still_line_only(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    task, line = capture_task(
        tmp_workspace, "call Terry", source=meeting.path, source_id=meeting.id
    )
    assert task.id is not None
    line_for_gone = line.replace(task.id, "task_gone")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        editor.text = line_for_gone + "\n"
        editor.cursor_location = (0, 0)

        await pilot.press("ctrl+t")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert "task_gone" not in editor.text


# --- U5/US3 combined: choom launched, listed, and a document opened --------


def test_task_list_is_unaffected_by_a_completed_task_moved_to_the_store(
    tmp_path: Path,
) -> None:
    workspace = init_workspace(tmp_path).workspace
    add_task(workspace, "open one")
    done_task = add_task(workspace, "done one")
    assert done_task.id is not None
    set_task_state(workspace, done_task.id, done=True, now=datetime(2026, 8, 2))

    open_tasks, _warnings = load_tasks(workspace)
    assert [t.text for t in open_tasks] == ["open one"]

    store_tasks, _warnings = load_task_store(workspace)
    assert {t.text for t in store_tasks} == {"open one", "done one"}

    reloaded = find_workspace(tmp_path)
    assert reloaded.root == workspace.root


# --- T037: the fingerprint's 30 s staleness bound self-heals a missed edit -


async def test_a_missed_done_store_edit_self_heals_after_the_30s_bound(
    tmp_workspace: Workspace,
) -> None:
    """The stat fingerprint's own docstring warns that a miss is permanent,
    not transient: a size-preserving edit landing inside one filesystem
    timestamp quantum recomputes to the same `(mtime_ns, size)` forever. The
    30 s bound (T037, plan.md Complexity Tracking) is what turns that into a
    known, self-healing window instead. The clock is injected -- no test may
    read the wall clock (Principle VI)."""
    task = add_task(tmp_workspace, "call Terry")
    assert task.id is not None
    when = datetime(2026, 8, 2)
    set_task_state(tmp_workspace, task.id, done=True, now=when)
    day_path = done_file_for(tmp_workspace, when.date())

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()

        from choom.tui.list_screen import ListScreen

        screen = app.screen
        assert isinstance(screen, ListScreen)

        clock_time = [1_000.0]
        screen._clock = lambda: clock_time[0]  # type: ignore[assignment]

        # Establish the fingerprint for the first time.
        await screen._refresh_tick()
        await pilot.pause()

        # A size-preserving edit -- toggling [x] back to [ ] -- with the
        # file's own (mtime_ns, size) forced identical to what was just
        # sampled, simulating the filesystem-quantization collision the
        # fingerprint's docstring describes.
        stat_before = day_path.stat()
        edited = day_path.read_text(encoding="utf-8").replace("[x]", "[ ]", 1)
        day_path.write_text(edited, encoding="utf-8")
        import os

        os.utime(day_path, ns=(stat_before.st_atime_ns, stat_before.st_mtime_ns))

        # Within the bound: the fingerprint still matches, so the miss persists.
        clock_time[0] += 5.0
        await screen._refresh_tick()
        await pilot.pause()
        from tests.helpers import task_rows

        assert task_rows(app)[0].record.done is True  # still stale

        # Past the 30 s bound: the forced full re-parse picks it up -- the
        # record is open now, so it drops out of the Done view entirely.
        clock_time[0] += 30.0
        await screen._refresh_tick()
        await pilot.pause()
        assert task_rows(app) == []
