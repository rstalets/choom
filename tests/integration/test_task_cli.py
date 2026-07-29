from __future__ import annotations

import re
from pathlib import Path

from endpaper.cli.main import main

_ID_PATTERN = re.compile(r"^t_[0-9a-f]{4}$")


def test_task_add_appends_one_line_with_id_type_tag_and_today(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(
        ["task", "add", "send the vendor comparison", "--type", "followup", "--tag", "procurement"]
    )
    assert exit_code == 0

    task_id = capsys.readouterr().out.strip()
    assert _ID_PATTERN.match(task_id)

    text = (tmp_path / "tasks.md").read_text(encoding="utf-8")
    assert text.count("\n") == text.count("- [")
    assert "send the vendor comparison" in text
    assert f"id:{task_id}" in text
    assert "type:followup" in text
    assert "tags:procurement" in text
    import datetime

    today = datetime.date.today().isoformat()
    assert f"created:{today}" in text


def test_task_add_leaves_pre_existing_prose_unchanged(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    tasks_path = tmp_path / "tasks.md"
    tasks_path.write_text("# My tasks\n\nSome notes.\n", encoding="utf-8", newline="\n")

    main(["task", "add", "buy milk"])
    capsys.readouterr()

    text = tasks_path.read_text(encoding="utf-8")
    assert text.startswith("# My tasks\n\nSome notes.\n")
    assert "buy milk" in text


def test_task_add_recreates_deleted_tasks_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    tasks_path = tmp_path / "tasks.md"
    if tasks_path.exists():
        tasks_path.unlink()
    assert not tasks_path.exists()

    exit_code = main(["task", "add", "buy milk"])
    assert exit_code == 0
    assert tasks_path.is_file()
    assert "buy milk" in tasks_path.read_text(encoding="utf-8")


def test_repeated_tag_preserves_order_and_dedupes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(
        [
            "task",
            "add",
            "vendor renewal",
            "--tag",
            "legal",
            "--tag",
            "procurement",
            "--tag",
            "legal",
        ]
    )
    capsys.readouterr()

    text = (tmp_path / "tasks.md").read_text(encoding="utf-8")
    assert "tags:legal,procurement" in text


def test_quoted_hash_tag_is_extracted_from_description(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["task", "add", "vendor call #procurement #legal"])
    capsys.readouterr()

    text = (tmp_path / "tasks.md").read_text(encoding="utf-8")
    assert "vendor call <!--" in text
    assert "tags:procurement,legal" in text
    assert "#" not in text.split("vendor call")[0] + text.split("vendor call")[1].split("<!--")[0]


def test_empty_after_tag_removal_exits_2_and_leaves_file_untouched(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    tasks_path = tmp_path / "tasks.md"
    before = tasks_path.read_bytes() if tasks_path.exists() else None

    exit_code = main(["task", "add", "#onlytags"])
    assert exit_code == 2

    after = tasks_path.read_bytes() if tasks_path.exists() else None
    assert before == after


def test_invalid_type_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["task", "add", "buy milk", "--type", "../evil"])
    assert exit_code == 2


def test_invalid_tag_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["task", "add", "buy milk", "--tag", "../evil"])
    assert exit_code == 2


_SEED = (
    "- [ ] one <!-- id:t_0001 created:2026-07-20 -->\n"
    "- [ ] two <!-- id:t_0002 type:followup tags:legal created:2026-07-21 -->\n"
    "- [x] three <!-- id:t_0003 created:2026-07-22 -->\n"
    "- [x] four <!-- id:t_0004 created:2026-07-23 -->\n"
    "- [ ] five <!-- id:t_0005 created:2026-07-19 -->\n"
)


def _init_with_seed(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "tasks.md").write_text(_SEED, encoding="utf-8", newline="\n")


def test_list_shows_open_tasks_oldest_first(tmp_path: Path, monkeypatch, capsys) -> None:
    _init_with_seed(tmp_path, monkeypatch)
    capsys.readouterr()

    exit_code = main(["task", "list"])
    assert exit_code == 0
    lines = capsys.readouterr().out.splitlines()
    ids = [line.split("\t")[0] for line in lines]
    assert ids == ["t_0005", "t_0001", "t_0002"]


def test_list_all_includes_completed_distinguishably(tmp_path: Path, monkeypatch, capsys) -> None:
    _init_with_seed(tmp_path, monkeypatch)
    capsys.readouterr()

    main(["task", "list", "--all"])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 5
    states = {line.split("\t")[0]: line.split("\t")[1] for line in lines}
    assert states["t_0003"] == "done"
    assert states["t_0001"] == "open"


def test_list_type_and_tag_combine_conjunctively_with_all(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _init_with_seed(tmp_path, monkeypatch)
    capsys.readouterr()

    main(["task", "list", "--all", "--type", "followup", "--tag", "legal"])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert lines[0].split("\t")[0] == "t_0002"


def test_list_on_missing_tasks_file_lists_nothing_exits_0(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "tasks.md").unlink()
    capsys.readouterr()

    exit_code = main(["task", "list"])
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_list_checkbox_free_file_lists_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "tasks.md").write_text("# notes\n\nno checkboxes here\n", encoding="utf-8")
    capsys.readouterr()

    exit_code = main(["task", "list"])
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_task_done_and_undone_change_the_file(tmp_path: Path, monkeypatch, capsys) -> None:
    _init_with_seed(tmp_path, monkeypatch)
    capsys.readouterr()

    assert main(["task", "done", "t_0001"]) == 0
    text = (tmp_path / "tasks.md").read_text(encoding="utf-8")
    assert "- [x] one <!-- id:t_0001 created:2026-07-20 -->\n" in text

    assert main(["task", "undone", "t_0003"]) == 0
    text = (tmp_path / "tasks.md").read_text(encoding="utf-8")
    assert "- [ ] three <!-- id:t_0003 created:2026-07-22 -->\n" in text


def test_noop_toggle_exits_0_without_writing(tmp_path: Path, monkeypatch, capsys) -> None:
    import os
    import time

    _init_with_seed(tmp_path, monkeypatch)
    capsys.readouterr()

    tasks_path = tmp_path / "tasks.md"
    before_mtime = os.stat(tasks_path).st_mtime_ns
    time.sleep(0.01)

    exit_code = main(["task", "undone", "t_0001"])
    assert exit_code == 0
    assert os.stat(tasks_path).st_mtime_ns == before_mtime


def test_unknown_id_exits_1_changes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    _init_with_seed(tmp_path, monkeypatch)
    capsys.readouterr()

    before = (tmp_path / "tasks.md").read_bytes()
    exit_code = main(["task", "done", "t_zzzz"])
    assert exit_code == 1
    assert "no task with id" in capsys.readouterr().err
    assert (tmp_path / "tasks.md").read_bytes() == before


def test_duplicated_id_exits_2_naming_both_lines(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    (tmp_path / "tasks.md").write_text(
        "- [ ] first <!-- id:t_dupe -->\n- [ ] second <!-- id:t_dupe -->\n",
        encoding="utf-8",
    )
    capsys.readouterr()

    exit_code = main(["task", "done", "t_dupe"])
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "lines 1 and 2" in err
