from __future__ import annotations

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace


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
