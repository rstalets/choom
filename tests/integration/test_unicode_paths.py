from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from endpaper.core.assistants import compose_prompt, resolve_assistant, start_request
from endpaper.core.config import get_assistant, set_assistant
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


def test_ai_and_config_assistant_work_in_a_workspace_with_spaces_and_non_ascii(
    tmp_path: Path, stub_assistant: Callable[[str], None]
) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace
    stub_assistant("echo")

    set_assistant(workspace, "claude")
    assert get_assistant(workspace) == "claude"

    meeting = create_meeting(workspace, "café résumé — naïve", type="standup")
    prompt = compose_prompt("résumé the café notes", meeting.path, 3)
    assert str(meeting.path) in prompt

    resolved = resolve_assistant(get_assistant(workspace))
    assert resolved.profile is not None

    request = start_request(resolved.profile, prompt, cwd=workspace.root)
    reply = request.wait()
    assert reply.ok is True
    assert "résumé the café notes" in reply.text
