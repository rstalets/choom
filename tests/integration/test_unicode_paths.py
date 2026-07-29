from __future__ import annotations

from pathlib import Path

from endpaper.core.meetings import create_meeting, scan_meetings
from endpaper.core.notes import create_note, open_daily_note, scan_notes
from endpaper.core.workspace import init_workspace


def test_workspace_path_with_spaces_and_non_ascii_works(tmp_path: Path) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    meeting = create_meeting(workspace, "café résumé — naïve", type="standup")
    assert meeting.path.is_file()
    assert meeting.title == "café résumé — naïve"

    meetings, warnings = scan_meetings(workspace)
    assert warnings == []
    assert meetings[0].title == "café résumé — naïve"


def test_note_workspace_path_with_spaces_and_non_ascii_works(tmp_path: Path) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    note = create_note(workspace, "café résumé — naïve", type="idea")
    assert note.path.is_file()
    assert note.title == "café résumé — naïve"

    daily = open_daily_note(workspace)
    assert daily.path.is_file()
    assert daily.created is True

    notes, warnings = scan_notes(workspace)
    assert warnings == []
    assert len(notes) == 2
