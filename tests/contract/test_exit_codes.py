from __future__ import annotations

from pathlib import Path

import endpaper.cli.main as cli_main
from endpaper.cli.main import main
from endpaper.core.errors import NotFoundError, UsageError, WorkspaceError


def test_error_hierarchy_exit_codes() -> None:
    assert NotFoundError.exit_code == 1
    assert UsageError.exit_code == 2
    assert WorkspaceError.exit_code == 3


def test_success_exits_0(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0


def test_semantic_usage_error_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    assert main(["meeting", "new", "x", "--type", "../evil"]) == 2


def test_argparse_usage_error_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["not-a-real-command"]) == 2


def test_workspace_error_exits_3(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["meeting", "list"]) == 3


def test_reserved_note_type_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    assert main(["note", "new", "x", "--type", "daily"]) == 2


def test_note_bad_since_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    assert main(["note", "list", "--since", "yesterday"]) == 2


def test_note_no_workspace_exits_3(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["note", "list"]) == 3
    assert main(["note", "today"]) == 3


def test_task_add_success_exits_0(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    assert main(["task", "add", "buy milk"]) == 0


def test_task_add_empty_description_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    assert main(["task", "add", "#onlytags"]) == 2


def test_task_done_unknown_id_exits_1(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    assert main(["task", "done", "t_zzzz"]) == 1


def test_task_done_duplicate_id_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "tasks.md").write_text(
        "- [ ] one <!-- id:t_dupe -->\n- [ ] two <!-- id:t_dupe -->\n", encoding="utf-8"
    )
    capsys.readouterr()
    assert main(["task", "done", "t_dupe"]) == 2


def test_task_no_workspace_exits_3(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["task", "list"]) == 3
    assert main(["task", "add", "buy milk"]) == 3
    assert main(["task", "done", "t_a1b2"]) == 3


def test_not_found_error_maps_to_exit_code_1(monkeypatch, capsys) -> None:
    # No command in this feature raises NotFoundError yet -- there is no "not found"
    # surface until `endpaper find`/`read` (out of scope here). This verifies main()'s
    # generic EndpaperError -> exit_code mapping is wired for it regardless.
    def _boom(namespace: object) -> int:
        raise NotFoundError("nothing to see here")

    monkeypatch.setattr(cli_main, "_dispatch", _boom)
    assert main(["init"]) == 1
