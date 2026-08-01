from __future__ import annotations

import os
import time

from choom.core.editing import load_for_edit, save_buffer
from choom.core.links import check_links, heal_links, relative_destination
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.notes import create_note


def test_fragment_only_link_gains_a_path_on_save(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\nSee [Q3 planning](#{meeting.id}) for context.\n", encoding="utf-8"
    )

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok

    expected_dest = relative_destination(note.path, meeting.path)
    assert f"[Q3 planning]({expected_dest}#{meeting.id})" in result.saved_text
    assert result.warnings == ()


def test_path_only_link_gains_a_fragment_on_save(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    dest = relative_destination(note.path, meeting.path)
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(original + f"\nSee [Q3 planning]({dest}) for context.\n", encoding="utf-8")

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok
    assert f"[Q3 planning]({dest}#{meeting.id})" in result.saved_text


def test_stale_path_is_corrected_on_save(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\nSee [Q3 planning](wrong/path.md#{meeting.id}) for context.\n",
        encoding="utf-8",
    )

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok

    expected_dest = relative_destination(note.path, meeting.path)
    assert f"#{meeting.id})" in result.saved_text
    assert f"({expected_dest}#{meeting.id})" in result.saved_text
    assert "wrong/path.md" not in result.saved_text


def test_dead_link_is_left_byte_identical_beside_a_stale_one(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    stale_line = f"Stale: [Q3](wrong/path.md#{meeting.id})\n"
    dead_line = "Dead: [gone](#meeting_00000000_deadbeef)\n"
    note.path.write_text(original + "\n" + stale_line + dead_line, encoding="utf-8")

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok
    assert "[gone](#meeting_00000000_deadbeef)" in result.saved_text  # untouched
    assert "wrong/path.md" not in result.saved_text  # the stale one WAS repaired
    assert len(result.warnings) == 1
    assert result.warnings[0].reason == "link_dead"


def test_link_text_and_surrounding_prose_are_unchanged(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    sentence = f"Please review [the Q3 planning notes](wrong.md#{meeting.id}) before Friday.\n"
    note.path.write_text(original + "\n" + sentence, encoding="utf-8")

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok
    assert "[the Q3 planning notes]" in result.saved_text
    assert "Please review" in result.saved_text
    assert "before Friday." in result.saved_text


def test_code_fence_around_link_syntax_is_never_rewritten(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "link syntax docs")
    original = note.path.read_text(encoding="utf-8")
    block = "\n```\n[example](#meeting_deadbeef)\n```\nInline: `[example](#meeting_deadbeef)`\n"
    note.path.write_text(original + block, encoding="utf-8")

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok
    assert "[example](#meeting_deadbeef)" in result.saved_text
    assert "```\n[example](#meeting_deadbeef)\n```" in result.saved_text
    assert "`[example](#meeting_deadbeef)`" in result.saved_text
    assert result.warnings == ()  # never resolved as a link, so never reported dead


def test_heal_dry_run_reports_exactly_what_a_real_run_then_changes(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\n[stale](wrong.md#{meeting.id})\n[dead](#meeting_00000000_deadbeef)\n",
        encoding="utf-8",
    )

    dry_reports = heal_links(tmp_workspace, dry_run=True)
    before = note.path.read_bytes()

    real_reports = heal_links(tmp_workspace)
    after = note.path.read_bytes()

    assert before != after  # the real run did change something
    dry_shape = {(r.file, r.line, r.target_id, r.status) for r in dry_reports}
    real_shape = {(r.file, r.line, r.target_id, r.status) for r in real_reports}
    assert dry_shape == real_shape


def test_dead_links_survive_heal_byte_identical_beside_repaired_ones(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\n[stale](wrong.md#{meeting.id})\n[dead](#meeting_00000000_deadbeef)\n",
        encoding="utf-8",
    )

    heal_links(tmp_workspace)
    text = note.path.read_text(encoding="utf-8")
    assert "[dead](#meeting_00000000_deadbeef)" in text
    assert "wrong.md" not in text


def test_heal_on_a_clean_workspace_writes_nothing_and_moves_no_updated(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    before_mtime = os.stat(meeting.path).st_mtime_ns
    before_bytes = meeting.path.read_bytes()
    time.sleep(0.01)

    reports = heal_links(tmp_workspace)

    assert reports == ()
    assert os.stat(meeting.path).st_mtime_ns == before_mtime
    assert meeting.path.read_bytes() == before_bytes


def test_check_never_writes(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(original + f"\n[stale](wrong.md#{meeting.id})\n", encoding="utf-8")
    before = note.path.read_bytes()

    reports = check_links(tmp_workspace)
    assert len(reports) == 1
    assert note.path.read_bytes() == before


def test_no_workspace_means_no_healing(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\nSee [Q3 planning](#{meeting.id}) for context.\n", encoding="utf-8"
    )

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file)  # no workspace passed
    assert result.ok
    assert f"[Q3 planning](#{meeting.id})" in result.saved_text  # untouched, no path added
    assert result.warnings == ()
