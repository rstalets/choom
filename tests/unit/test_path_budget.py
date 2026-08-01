from __future__ import annotations

from datetime import datetime

from choom.core.links import relative_destination
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.notes import create_note, open_daily_note


def test_worst_case_generated_path_is_within_120_chars_of_workspace_root(
    tmp_workspace: Workspace,
) -> None:
    long_type = "t" * 40
    long_description = "w" * 200
    meeting = create_meeting(tmp_workspace, long_description, type=long_type)

    relative = meeting.path.relative_to(tmp_workspace.root).as_posix()
    assert len(relative) <= 120


def test_worst_case_with_collision_suffix_stays_within_budget(tmp_workspace: Workspace) -> None:
    long_type = "t" * 40
    long_description = "w" * 200
    first = create_meeting(tmp_workspace, long_description, type=long_type)
    second = create_meeting(tmp_workspace, long_description, type=long_type)

    for meeting in (first, second):
        relative = meeting.path.relative_to(tmp_workspace.root).as_posix()
        assert len(relative) <= 120


def test_worst_case_note_path_stays_within_budget(tmp_workspace: Workspace) -> None:
    long_type = "t" * 40
    long_description = "w" * 200
    note = create_note(tmp_workspace, long_description, type=long_type)

    relative = note.path.relative_to(tmp_workspace.root).as_posix()
    assert len(relative) <= 120
    # notes/ is three characters shorter than meetings/, so the worst case here
    # is strictly shorter than the meeting worst case (R9).
    assert len(relative) < 120


def test_daily_note_path_is_well_under_budget(tmp_workspace: Workspace) -> None:
    daily = open_daily_note(tmp_workspace, now=datetime(2026, 7, 28, 9, 0, 0))

    relative = daily.path.relative_to(tmp_workspace.root).as_posix()
    assert relative == "notes/daily/2026/07/2026-07-28.md"
    assert len(relative) <= 120


def test_worst_case_link_destination_stays_well_inside_the_windows_budget(
    tmp_workspace: Workspace,
) -> None:
    # research R3's worst case: a daily note pointing at a maximally-long
    # meeting filename, measured at 117 characters. This is text *inside* a
    # file, not a filesystem path, so the 260-character budget does not apply
    # to it directly -- but it must stay small regardless of how deep the
    # layout gets, since a link destination is meant to be readable.
    long_type = "t" * 40
    long_description = "w" * 200
    meeting = create_meeting(tmp_workspace, long_description, type=long_type)

    daily = open_daily_note(tmp_workspace, now=datetime(2026, 7, 28, 9, 0, 0))
    dest = relative_destination(daily.path, meeting.path)

    assert len(dest) < 260
    assert len(dest) < 150
