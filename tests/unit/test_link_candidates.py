from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from choom.core.links import find_link_targets, link_candidates
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.notes import create_note
from choom.core.tasks import add_task

_TODAY = date.today()


def _at(days_ago: int) -> datetime:
    """A `now` for `create_meeting`/`create_note`/`add_task`, offset from today
    rather than a literal date (Principle VI -- no test depends on the wall
    clock)."""
    day = _TODAY - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day, 9, 0, 0)


def test_newest_first_ordering(tmp_workspace: Workspace) -> None:
    older = create_meeting(tmp_workspace, "Q3 planning alpha", now=_at(5))
    newer = create_note(tmp_workspace, "Q3 planning beta", now=_at(1))

    candidates = link_candidates(tmp_workspace, "q3 planning")

    assert [c.target.id for c in candidates] == [newer.id, older.id]


def test_case_insensitive_title_tie_break(tmp_workspace: Workspace) -> None:
    when = _at(2)
    beta = create_meeting(tmp_workspace, "q3 Planning beta", now=when)
    alpha = create_note(tmp_workspace, "Q3 planning Alpha", now=when)

    candidates = link_candidates(tmp_workspace, "q3 planning")

    # Same date -- ties broken by title, case-insensitive, ascending.
    assert [c.target.id for c in candidates] == [alpha.id, beta.id]


def test_undated_records_sort_last_and_keep_the_title_tie_break(
    tmp_workspace: Workspace,
) -> None:
    dated = create_meeting(tmp_workspace, "q3 planning dated", now=_at(3))
    undated_b = add_task(tmp_workspace, "q3 planning task b", now=_at(2))
    undated_a = add_task(tmp_workspace, "q3 planning task a", now=_at(1))
    # Strip just the `created:` field from each task's metadata comment,
    # keeping the id -- the real shape of a hand-typed checkbox someone later
    # added an id to, but never a date, and the case `date is None` exists for.
    tasks_text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    stripped = re.sub(r" created:\d{4}-\d{2}-\d{2}", "", tasks_text)
    tmp_workspace.tasks_file.write_text(stripped, encoding="utf-8")

    candidates = link_candidates(tmp_workspace, "q3 planning")

    assert candidates[0].target.id == dated.id
    assert candidates[0].date is not None
    remaining = candidates[1:]
    assert all(c.date is None for c in remaining)
    # Undated ties still sort by title -- "task a" before "task b".
    assert [c.target.title for c in remaining] == ["q3 planning task a", "q3 planning task b"]
    assert {undated_a.text, undated_b.text} == {"q3 planning task a", "q3 planning task b"}


def test_collection_matches_kind_for_every_record_type(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "sync standup", now=_at(1))
    note = create_note(tmp_workspace, "sync notes", now=_at(1))
    task = add_task(tmp_workspace, "sync follow-up", now=_at(1))
    assert task.id is not None

    candidates = link_candidates(tmp_workspace, "sync")
    by_id = {c.target.id: c for c in candidates}

    assert by_id[meeting.id].collection == "meeting"
    assert by_id[meeting.id].target.kind == "meeting"
    assert by_id[note.id].collection == "note"
    assert by_id[note.id].target.kind == "note"
    assert by_id[task.id].collection == "task"
    assert by_id[task.id].target.kind == "task"


def test_find_link_targets_is_the_same_records_in_the_same_order(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning alpha", now=_at(5))
    create_note(tmp_workspace, "Q3 planning beta", now=_at(1))
    task = add_task(tmp_workspace, "Q3 planning gamma", now=_at(3))
    assert task.id is not None

    candidates = link_candidates(tmp_workspace, "q3 planning")
    targets = find_link_targets(tmp_workspace, "q3 planning")

    assert targets == tuple(c.target for c in candidates)
