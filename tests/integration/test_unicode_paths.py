from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from endpaper.core.assistants import compose_prompt, resolve_assistant, start_request
from endpaper.core.config import get_assistant, set_assistant
from endpaper.core.editing import load_for_edit, save_buffer
from endpaper.core.links import relative_destination
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


def test_a_link_round_trips_in_a_workspace_path_with_spaces_and_non_ascii(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    meeting = create_meeting(workspace, "café résumé — naïve", type="standup")
    note = create_note(workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\nSee [Q3 planning](#{meeting.id}) for context.\n", encoding="utf-8"
    )

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=workspace)
    assert result.ok

    expected_dest = relative_destination(note.path, meeting.path)
    assert f"[Q3 planning]({expected_dest}#{meeting.id})" in result.saved_text


def test_a_destination_with_a_space_uses_the_angle_bracket_form(tmp_path: Path) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    # A file placed by hand with a space and parens in its name -- endpaper's own
    # generated filenames never need escaping, but a user's hand-placed file
    # legitimately can, and the workspace explicitly permits this.
    target = workspace.notes_dir / "Q3 (draft) notes.md"
    target.write_text(
        '---\nid: note_00000000_aaaaaaaa\ntype: ""\ntitle: "draft"\ntags: []\n'
        "created: 2026-01-01T09:00:00\nupdated: 2026-01-01T09:00:00\n---\n",
        encoding="utf-8",
    )

    linking_note = create_note(workspace, "vendor landscape")
    original = linking_note.path.read_text(encoding="utf-8")
    linking_note.path.write_text(
        original + "\nSee [the draft](#note_00000000_aaaaaaaa) for context.\n",
        encoding="utf-8",
    )

    file = load_for_edit(linking_note.path)
    result = save_buffer(linking_note.path, file.text, file, workspace=workspace)
    assert result.ok

    expected_dest = relative_destination(linking_note.path, target)
    assert " " in expected_dest  # the case that requires escaping
    assert f"(<{expected_dest}#note_00000000_aaaaaaaa>)" in result.saved_text
