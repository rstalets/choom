from __future__ import annotations

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace


def test_collision_creates_numeric_suffix_and_leaves_first_untouched(
    tmp_workspace: Workspace,
) -> None:
    first = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    first_bytes_before = first.path.read_bytes()

    second = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    assert first.path != second.path
    assert second.path.name.endswith("-2.md")
    assert first.path.read_bytes() == first_bytes_before


def test_suffixes_continue_past_9(tmp_workspace: Workspace) -> None:
    paths = [create_meeting(tmp_workspace, "Q3 planning", type="standup").path for _ in range(11)]
    assert len(set(paths)) == 11
    names = [p.name for p in paths]
    assert any(name.endswith("-10.md") for name in names)
