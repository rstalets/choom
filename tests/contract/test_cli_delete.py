"""Contract tests for the three `<type> delete <id> --force` commands
(contracts/cli-delete.md, US3): exit codes, stream separation, `--force`
required, and the non-blocking guarantee."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from choom.cli.main import main


def _meeting_id(tmp_path: Path, capsys) -> str:
    main(["meeting", "list", "--json"])
    records = json.loads(capsys.readouterr().out)
    return str(records[0]["id"])


def _note_id(tmp_path: Path, capsys) -> str:
    main(["note", "list", "--json"])
    records = json.loads(capsys.readouterr().out)
    return str(records[0]["id"])


# --- meeting delete -----------------------------------------------------------


def test_meeting_delete_success_exits_0_empty_stdout_and_removes_file(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning"])
    relative_path = capsys.readouterr().out.strip()
    meeting_id = _meeting_id(tmp_path, capsys)

    exit_code = main(["meeting", "delete", meeting_id, "--force"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""
    assert not (tmp_path / relative_path).exists()


def test_meeting_delete_without_force_deletes_nothing_and_exits_2(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning"])
    relative_path = capsys.readouterr().out.strip()
    meeting_id = _meeting_id(tmp_path, capsys)

    exit_code = main(["meeting", "delete", meeting_id])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "--force" in captured.err
    assert (tmp_path / relative_path).exists()


def test_meeting_delete_unknown_id_exits_1(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["meeting", "delete", "meeting_zzzz", "--force"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "meeting_zzzz" in captured.err


def test_meeting_delete_of_a_note_id_exits_1_wrong_kind(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "an idea"])
    capsys.readouterr()
    note_id = _note_id(tmp_path, capsys)

    exit_code = main(["meeting", "delete", note_id, "--force"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "meeting" in captured.err
    assert note_id in captured.err


# --- note delete ----------------------------------------------------------------


def test_note_delete_success_exits_0_and_removes_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "an idea"])
    relative_path = capsys.readouterr().out.strip()
    note_id = _note_id(tmp_path, capsys)

    exit_code = main(["note", "delete", note_id, "--force"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert not (tmp_path / relative_path).exists()


def test_note_delete_without_force_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "an idea"])
    capsys.readouterr()
    note_id = _note_id(tmp_path, capsys)

    exit_code = main(["note", "delete", note_id])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "refusing to delete without --force" in captured.err


# --- task delete ------------------------------------------------------------------


def test_task_delete_success_removes_line_and_body_exits_0(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    task_id = capsys.readouterr().out.strip()

    exit_code = main(["task", "delete", task_id, "--force"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    tasks_text = (tmp_path / "tasks.md").read_text(encoding="utf-8")
    assert task_id not in tasks_text


def test_task_delete_again_exits_1_not_found(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    task_id = capsys.readouterr().out.strip()
    main(["task", "delete", task_id, "--force"])
    capsys.readouterr()

    exit_code = main(["task", "delete", task_id, "--force"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert task_id in captured.err


def test_task_delete_ambiguous_id_exits_2_naming_every_path(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "tasks.md").write_text(
        "- [ ] first <!-- id:task_dupe -->\n- [ ] second <!-- id:task_dupe -->\n",
        encoding="utf-8",
    )
    capsys.readouterr()

    exit_code = main(["task", "delete", "task_dupe", "--force"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "task_dupe" in captured.err
    tasks_text = (tmp_path / "tasks.md").read_text(encoding="utf-8")
    assert "task_dupe" in tasks_text  # nothing was deleted
    assert tasks_text.count("task_dupe") == 2


def test_task_delete_no_workspace_exits_3(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["task", "delete", "task_a1b2", "--force"])

    assert exit_code == 3


# --- argparse-level usage errors ------------------------------------------------


def test_missing_id_argument_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["task", "delete", "--force"])

    assert exit_code == 2


# --- --json is not offered -------------------------------------------------------


def test_delete_has_no_json_flag(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    task_id = capsys.readouterr().out.strip()

    exit_code = main(["task", "delete", task_id, "--force", "--json"])

    assert exit_code == 2  # argparse: unrecognized argument


# --- no ANSI on either stream ----------------------------------------------------


def test_no_ansi_on_success_or_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    task_id = capsys.readouterr().out.strip()

    main(["task", "delete", task_id, "--force"])
    captured = capsys.readouterr()
    assert "\x1b" not in captured.out
    assert "\x1b" not in captured.err

    exit_code = main(["task", "delete", task_id, "--force"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "\x1b" not in captured.out
    assert "\x1b" not in captured.err


# --- non-blocking, subprocess-level -----------------------------------------------


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "choom", *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_delete_never_blocks_with_stdin_closed_and_stdout_redirected(tmp_path: Path) -> None:
    assert _run(["init"], tmp_path).returncode == 0
    add_result = _run(["task", "add", "buy milk"], tmp_path)
    assert add_result.returncode == 0
    task_id = add_result.stdout.strip()

    # With the flag: succeeds, promptly, with no prompt text or escapes anywhere.
    result = _run(["task", "delete", task_id, "--force"], tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""
    assert "\x1b" not in result.stdout
    assert "\x1b" not in result.stderr

    # Without the flag: never blocks waiting for a confirmation that never comes.
    result = _run(["task", "add", "buy milk"], tmp_path)
    task_id = result.stdout.strip()
    result = _run(["task", "delete", task_id], tmp_path)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "\x1b" not in result.stdout
