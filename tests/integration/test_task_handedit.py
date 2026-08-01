from __future__ import annotations

import json
import os
import stat

from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task, load_tasks, set_task_state
from tests.conftest import tasks_file, write_raw, write_tasks


def test_bare_checkbox_gains_id_in_place_rest_of_file_unchanged(tmp_workspace: Workspace) -> None:
    original = "# My tasks\n\n- [ ] buy milk\n\nSome trailing prose.\n"
    write_tasks(tmp_workspace, original)

    tasks, warnings = load_tasks(tmp_workspace)

    assert warnings == []
    assert len(tasks) == 1
    assert tasks[0].id is not None
    assert tasks[0].text == "buy milk"

    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text.startswith("# My tasks\n\n- [ ] buy milk <!-- id:")
    assert text.endswith("\n\nSome trailing prose.\n")


def test_truncated_comment_is_skipped_warned_and_left_byte_identical(
    tmp_workspace: Workspace,
) -> None:
    original = "- [ ] thing <!-- id:\n"
    write_tasks(tmp_workspace, original)

    tasks, warnings = load_tasks(tmp_workspace)

    assert tasks == []
    assert len(warnings) == 1
    assert warnings[0].reason == "task_unterminated_comment"
    assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == original


def test_headings_prose_and_non_task_list_items_survive_verbatim(
    tmp_workspace: Workspace,
) -> None:
    original = (
        "# Tasks\n\n## Today\n\nSome prose about the day.\n\n- not a checkbox\n"
        "  - [ ] indented sub-task\n"
    )
    write_tasks(tmp_workspace, original)

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []
    assert len(tasks) == 1
    assert tasks[0].text == "indented sub-task"

    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text.startswith("# Tasks\n\n## Today\n\nSome prose about the day.\n\n- not a checkbox\n")


def test_crlf_no_final_newline_preserved_across_toggle_and_backfill(
    tmp_workspace: Workspace,
) -> None:
    write_raw(tasks_file(tmp_workspace), "- [ ] one\n- [ ] bare", newline="\r\n")

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert text.endswith("bare <!-- id:") is False
    assert "\r\n" in text
    assert not text.endswith("\n")

    bare_task = next(t for t in tasks if t.text == "bare")
    assert bare_task.id is not None
    set_task_state(tmp_workspace, bare_task.id, done=True)

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text_after = fh.read()
    assert not text_after.endswith("\n")
    assert "- [x] bare" in text_after


def test_add_task_on_no_final_newline_file_adds_terminator_and_nothing_else(
    tmp_workspace: Workspace,
) -> None:
    original = "- [ ] existing <!-- id:task_aaaa -->"
    write_raw(tasks_file(tmp_workspace), original, newline="\n")

    add_task(tmp_workspace, "new task")

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert text.startswith(original + "\n")
    assert text.endswith("\n")


def test_users_own_comment_is_bare_and_gains_metadata_comment_after_it(
    tmp_workspace: Workspace,
) -> None:
    original = "- [ ] fix the <!-- hack --> path\n"
    write_tasks(tmp_workspace, original)

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []
    assert len(tasks) == 1
    assert tasks[0].text == "fix the <!-- hack --> path"
    assert tasks[0].id is not None

    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text.startswith("- [ ] fix the <!-- hack --> path <!-- id:")

    # Round-trips: scanning again yields the same text for that task.
    tasks_again, warnings_again = load_tasks(tmp_workspace)
    assert warnings_again == []
    assert tasks_again[0].text == "fix the <!-- hack --> path"
    assert tasks_again[0].id == tasks[0].id


def test_read_only_file_degrades_gracefully(cli) -> None:
    tasks_path = cli.root / "tasks.md"
    tasks_path.write_text(
        "- [ ] bare task\n- [ ] typed task <!-- id:task_fixed -->\n",
        encoding="utf-8",
        newline="\n",
    )
    before = tasks_path.read_bytes()

    original_mode = tasks_path.stat().st_mode
    tasks_dir_mode = tasks_path.parent.stat().st_mode
    os.chmod(tasks_path, stat.S_IREAD)
    os.chmod(tasks_path.parent, stat.S_IREAD | stat.S_IEXEC)
    try:
        result = cli("task", "list", "--json")
        assert result.exit_code == 0
        records = json.loads(result.out)
        assert len(records) == 2
        bare = next(r for r in records if r["text"] == "bare task")
        assert bare["id"] is None
        assert result.err != ""

        result = cli("task", "done", "task_fixed")
        assert result.exit_code == 3
    finally:
        os.chmod(tasks_path.parent, tasks_dir_mode)
        os.chmod(tasks_path, original_mode)

    assert tasks_path.read_bytes() == before


def test_hand_written_links_field_survives_a_task_done_round_trip(
    tmp_workspace: Workspace,
) -> None:
    original = (
        "# Tasks\n\n"
        "- [ ] call Terry "
        "<!-- id:task_a1b2 links:meeting_20260728_a1b2c3d4 created:2026-07-30 -->\n"
        "- [ ] untouched line one <!-- id:task_yyyy -->\n"
        "- [x] untouched line two <!-- id:task_zzzz -->\n"
    )
    write_tasks(tmp_workspace, original)

    tasks_before, warnings_before = load_tasks(tmp_workspace)
    assert warnings_before == []
    target = next(t for t in tasks_before if t.id == "task_a1b2")
    assert target.links == ("meeting_20260728_a1b2c3d4",)

    set_task_state(tmp_workspace, "task_a1b2", done=True)

    text_after = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert "links:meeting_20260728_a1b2c3d4" in text_after
    assert "- [x] call Terry" in text_after
    # every other line is byte-identical -- only the one checkbox character moved
    assert "- [ ] untouched line one <!-- id:task_yyyy -->\n" in text_after
    assert "- [x] untouched line two <!-- id:task_zzzz -->\n" in text_after

    tasks_after, warnings_after = load_tasks(tmp_workspace)
    assert warnings_after == []
    target_after = next(t for t in tasks_after if t.id == "task_a1b2")
    assert target_after.links == ("meeting_20260728_a1b2c3d4",)
    assert target_after.done is True


def test_tasks_md_with_no_links_anywhere_is_byte_identical_after_read_write(
    tmp_workspace: Workspace,
) -> None:
    original = (
        "- [ ] one <!-- id:task_0001 created:2026-07-20 -->\n"
        "- [ ] two <!-- id:task_0002 type:followup created:2026-07-21 -->\n"
    )
    write_tasks(tmp_workspace, original)

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []
    assert all(t.links == () for t in tasks)
    assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == original

    set_task_state(tmp_workspace, "task_0001", done=True)
    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert "links:" not in text


def test_tasks_md_remains_valid_commonmark_with_a_links_field(
    tmp_workspace: Workspace,
) -> None:
    original = (
        "# Tasks\n\n"
        "- [ ] call Terry <!-- id:task_a1b2 links:meeting_1,note_2 created:2026-07-30 -->\n"
    )
    write_tasks(tmp_workspace, original)

    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        assert stripped.startswith(("- [ ]", "- [x]", "- [X]"))
    assert "<!--" in text and "-->" in text  # metadata stays inside an HTML comment
