from __future__ import annotations

from pathlib import Path

from endpaper.core.meetings import create_meeting, scan_meetings
from endpaper.core.workspace import init_workspace


def test_workspace_path_with_spaces_and_non_ascii_works(tmp_path: Path) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root)

    meeting = create_meeting(workspace, "café résumé — naïve", type="standup")
    assert meeting.path.is_file()
    assert meeting.title == "café résumé — naïve"

    meetings, warnings = scan_meetings(workspace)
    assert warnings == []
    assert meetings[0].title == "café résumé — naïve"
