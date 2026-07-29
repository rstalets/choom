from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from endpaper.cli.main import main
from endpaper.core.tasks import add_task, load_tasks
from endpaper.core.workspace import init_workspace


def test_bare_checkbox_gains_id_in_place_rest_of_file_unchanged(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    original = "# My tasks\n\n- [ ] buy milk\n\nSome trailing prose.\n"
    workspace.tasks_file.write_text(original, encoding="utf-8", newline="\n")

    tasks, warnings = load_tasks(workspace)

    assert warnings == []
    assert len(tasks) == 1
    assert tasks[0].id is not None
    assert tasks[0].text == "buy milk"

    text = workspace.tasks_file.read_text(encoding="utf-8")
    assert text.startswith("# My tasks\n\n- [ ] buy milk <!-- id:")
    assert text.endswith("\n\nSome trailing prose.\n")


def test_truncated_comment_is_skipped_warned_and_left_byte_identical(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    original = "- [ ] thing <!-- id:\n"
    workspace.tasks_file.write_text(original, encoding="utf-8", newline="\n")

    tasks, warnings = load_tasks(workspace)

    assert tasks == []
    assert len(warnings) == 1
    assert warnings[0].reason == "task_unterminated_comment"
    assert workspace.tasks_file.read_text(encoding="utf-8") == original


def test_headings_prose_and_non_task_list_items_survive_verbatim(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    original = (
        "# Tasks\n\n## Today\n\nSome prose about the day.\n\n- not a checkbox\n"
        "  - [ ] indented sub-task\n"
    )
    workspace.tasks_file.write_text(original, encoding="utf-8", newline="\n")

    tasks, warnings = load_tasks(workspace)
    assert warnings == []
    assert len(tasks) == 1
    assert tasks[0].text == "indented sub-task"

    text = workspace.tasks_file.read_text(encoding="utf-8")
    assert text.startswith("# Tasks\n\n## Today\n\nSome prose about the day.\n\n- not a checkbox\n")


def test_crlf_no_final_newline_preserved_across_toggle_and_backfill(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    original = "- [ ] one\r\n- [ ] bare"
    with open(workspace.tasks_file, "w", encoding="utf-8", newline="") as fh:
        fh.write(original)

    tasks, warnings = load_tasks(workspace)
    assert warnings == []

    text = workspace.tasks_file.read_text(encoding="utf-8", newline="")
    assert text.endswith("bare <!-- id:") is False
    assert "\r\n" in text
    assert not text.endswith("\n")

    from endpaper.core.tasks import set_task_state

    bare_task = next(t for t in tasks if t.text == "bare")
    assert bare_task.id is not None
    set_task_state(workspace, bare_task.id, done=True)

    text_after = workspace.tasks_file.read_text(encoding="utf-8", newline="")
    assert not text_after.endswith("\n")
    assert "- [x] bare" in text_after


def test_add_task_on_no_final_newline_file_adds_terminator_and_nothing_else(
    tmp_path: Path,
) -> None:
    workspace = init_workspace(tmp_path).workspace
    original = "- [ ] existing <!-- id:t_aaaa -->"
    with open(workspace.tasks_file, "w", encoding="utf-8", newline="") as fh:
        fh.write(original)

    add_task(workspace, "new task")

    text = workspace.tasks_file.read_text(encoding="utf-8", newline="")
    assert text.startswith(original + "\n")
    assert text.endswith("\n")


def test_users_own_comment_is_bare_and_gains_metadata_comment_after_it(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    original = "- [ ] fix the <!-- hack --> path\n"
    workspace.tasks_file.write_text(original, encoding="utf-8", newline="\n")

    tasks, warnings = load_tasks(workspace)
    assert warnings == []
    assert len(tasks) == 1
    assert tasks[0].text == "fix the <!-- hack --> path"
    assert tasks[0].id is not None

    text = workspace.tasks_file.read_text(encoding="utf-8")
    assert text.startswith("- [ ] fix the <!-- hack --> path <!-- id:")

    # Round-trips: scanning again yields the same text for that task.
    tasks_again, warnings_again = load_tasks(workspace)
    assert warnings_again == []
    assert tasks_again[0].text == "fix the <!-- hack --> path"
    assert tasks_again[0].id == tasks[0].id


def test_read_only_file_degrades_gracefully(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    tasks_path = tmp_path / "tasks.md"
    tasks_path.write_text(
        "- [ ] bare task\n- [ ] typed task <!-- id:t_fixed -->\n",
        encoding="utf-8",
        newline="\n",
    )
    before = tasks_path.read_bytes()

    original_mode = tasks_path.stat().st_mode
    tasks_dir_mode = tasks_path.parent.stat().st_mode
    os.chmod(tasks_path, stat.S_IREAD)
    os.chmod(tasks_path.parent, stat.S_IREAD | stat.S_IEXEC)
    try:
        exit_code = main(["task", "list", "--json"])
        assert exit_code == 0
        captured = capsys.readouterr()
        records = json.loads(captured.out)
        assert len(records) == 2
        bare = next(r for r in records if r["text"] == "bare task")
        assert bare["id"] is None
        assert captured.err != ""

        exit_code = main(["task", "done", "t_fixed"])
        assert exit_code == 3
    finally:
        os.chmod(tasks_path.parent, tasks_dir_mode)
        os.chmod(tasks_path, original_mode)

    assert tasks_path.read_bytes() == before
