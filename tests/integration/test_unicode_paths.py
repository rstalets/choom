from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from choom.core.assistants import compose_prompt, resolve_assistant, start_request
from choom.core.config import get_assistant, set_assistant
from choom.core.editing import load_for_edit, save_buffer
from choom.core.links import relative_destination
from choom.core.meetings import create_meeting, scan_meetings
from choom.core.mirrors import (
    capture_task,
    commit_mirror_deletion,
    plan_mirror_deletion,
    propagate_to_documents,
    reconcile_on_open,
)
from choom.core.notes import create_note, open_daily_note, scan_notes
from choom.core.tasks import set_task_state
from choom.core.workspace import init_workspace


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
    prompt = compose_prompt("résumé the café notes", meeting.path, 3, task_capture=True)
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

    # A file placed by hand with a space and parens in its name -- choom's own
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


# --- T071: mirror capture and propagation in a workspace with spaces and non-ASCII


def test_capture_and_mirror_round_trip_in_a_workspace_with_spaces_and_non_ascii(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    meeting = create_meeting(workspace, "café résumé — naïve", type="standup")
    task, line = capture_task(
        workspace,
        "appeler Terry à propos du renouvellement",
        source=meeting.path,
        source_id=meeting.id,
    )
    assert task.id is not None
    # No filesystem path budget is spent by a mirror -- it is link text inside
    # a document, not a path -- but it must still round-trip correctly through
    # a workspace whose own root already carries spaces and non-ASCII.
    assert f"#{task.id}" in line
    assert line.startswith("- [ ] [appeler Terry")

    text = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(text + line + "\n", encoding="utf-8")

    updated_task = set_task_state(workspace, task.id, done=True)
    written, warnings = propagate_to_documents(workspace, updated_task)
    assert warnings == ()
    assert meeting.path in written
    assert "- [x] [appeler Terry" in meeting.path.read_text(encoding="utf-8")


# --- T024 (017-editor-task-delete): ctrl+t's core half in a non-ASCII workspace


def test_task_deletion_survives_a_workspace_path_with_spaces_and_non_ascii(
    tmp_path: Path,
) -> None:
    """The gesture's own path budget is zero -- `plan_mirror_deletion` and
    `commit_mirror_deletion` neither construct nor open a path beyond
    `workspace.tasks_file`, which every other core function already opens.
    What this exercises is the character-offset splice itself: a non-ASCII
    task description sliced out of the buffer by `str` offsets, which cannot
    split a multi-byte character the way a byte offset could."""
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    meeting = create_meeting(workspace, "café résumé — naïve", type="standup")
    task, line = capture_task(
        workspace,
        "appeler Terry à propos du renouvellement 笔记",
        source=meeting.path,
        source_id=meeting.id,
    )
    assert task.id is not None

    text = f"above\n\n{line}\n  a nested note\n\nbelow\n"
    plan = plan_mirror_deletion(workspace, text, 3, source=meeting.path)
    assert plan is not None
    assert plan.outcome == "deletable"
    # The central invariant (data-model.md §3), asserted here specifically
    # because the sliced text is non-ASCII: `str` offsets index characters,
    # never bytes, so this holds even though "appeler...笔记" is not the same
    # number of bytes as it is characters.
    assert plan.text == text[: plan.span[0]] + text[plan.span[1] :]
    assert plan.text == "above\n\n  a nested note\n\nbelow\n"

    commit_mirror_deletion(workspace, plan)
    tasks_text = workspace.tasks_file.read_text(encoding="utf-8")
    assert task.text not in tasks_text


def test_reconcile_on_open_works_in_a_workspace_with_spaces_and_non_ascii(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    meeting = create_meeting(workspace, "café résumé — naïve", type="standup")
    task, line = capture_task(workspace, "appeler Terry", source=meeting.path, source_id=meeting.id)
    assert task.id is not None
    text = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(text + line + "\n", encoding="utf-8")

    set_task_state(workspace, task.id, done=True)

    report = reconcile_on_open(
        workspace, meeting.path.read_text(encoding="utf-8"), source=meeting.path
    )
    assert "[x]" in report.text
    assert report.warnings == ()


# --- T037 (018-automatic-link-detection): bare-URL conversion in a workspace
# with spaces and non-ASCII, and across a CRLF document -----------------------


def test_a_bare_url_with_non_ascii_characters_survives_a_save(tmp_path: Path) -> None:
    """Offsets in `format_bare_urls` are character offsets into a Python
    `str`, never byte offsets, so a multi-byte character next to a URL
    cannot be split mid-character. This is the case that would catch it if
    the implementation ever moved to byte offsets: a non-ASCII character
    immediately follows the converted URL on the same line."""
    workspace_root = tmp_path / "Équipe Notes 笔记"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    note = create_note(workspace, "vendor landscape")
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + "\nVoir https://example.com/résumé puis 笔记.\n",
        encoding="utf-8",
    )

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=workspace)
    assert result.ok
    assert len(result.conversions) == 1
    conv = result.conversions[0]
    assert conv.url == "https://example.com/résumé"
    assert "[https://example.com/résumé](https://example.com/résumé)" in result.saved_text
    assert "puis 笔记." in result.saved_text  # the trailing non-ASCII text is intact


def test_a_bare_url_in_a_crlf_document_round_trips_the_line_ending_convention(
    tmp_path: Path,
) -> None:
    """`load_for_edit` normalises CRLF to LF on read and
    `_apply_line_ending_policy` restores the convention on write -- this
    feature adds no line-ending handling of its own, so a CRLF file must
    round-trip exactly as it already does. If this test ever needs new
    production code to pass, the conversion is doing something it should
    not (research R2: no mask or edit in this feature inserts or removes a
    newline)."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    workspace = init_workspace(workspace_root).workspace

    note = create_note(workspace, "vendor landscape")
    original = note.path.read_bytes().decode("utf-8")
    crlf_text = (original + "\nSee https://example.com/a for details.\n").replace("\n", "\r\n")
    note.path.write_bytes(crlf_text.encode("utf-8"))

    file = load_for_edit(note.path)
    assert file.newline == "\r\n"
    result = save_buffer(note.path, file.text, file, workspace=workspace)
    assert result.ok
    assert len(result.conversions) == 1

    on_disk = note.path.read_bytes().decode("utf-8")
    assert "\r\n" in on_disk
    assert "\n" not in on_disk.replace("\r\n", "")  # every newline is `\r\n` -- none bare
    assert "[https://example.com/a](https://example.com/a)" in on_disk
