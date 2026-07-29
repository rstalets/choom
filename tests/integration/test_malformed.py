from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main
from endpaper.core.tasks import load_tasks
from endpaper.core.workspace import init_workspace


def test_malformed_file_is_skipped_warned_and_left_byte_identical(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning", "--type", "standup"])
    capsys.readouterr()

    broken = tmp_path / "meetings" / "2026-07-28-broken.md"
    broken.write_text("---\nid: broken\n", encoding="utf-8")
    before = broken.read_bytes()

    exit_code = main(["meeting", "list", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    records = json.loads(captured.out)
    assert len(records) == 1
    assert records[0]["title"] == "Q3 planning"

    assert "broken" in captured.err

    after = broken.read_bytes()
    assert before == after


def test_malformed_note_is_skipped_warned_and_left_byte_identical_and_others_still_list(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "vendor landscape", "--type", "research"])
    capsys.readouterr()

    broken = tmp_path / "notes" / "2026-07-28-broken.md"
    broken.write_text("---\nid: broken\n", encoding="utf-8")
    before = broken.read_bytes()

    exit_code = main(["note", "list", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    records = json.loads(captured.out)
    assert len(records) == 1
    assert records[0]["title"] == "vendor landscape"

    assert "broken" in captured.err

    after = broken.read_bytes()
    assert before == after


def test_one_in_ten_malformed_task_lines_still_lists_all_well_formed(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    lines = []
    well_formed_count = 0
    for i in range(100):
        if i % 10 == 0:
            lines.append(f"- [ ] broken {i} <!-- id:\n")
        else:
            lines.append(f"- [ ] task {i} <!-- id:t_{i:04x} -->\n")
            well_formed_count += 1
    workspace.tasks_file.write_text("".join(lines), encoding="utf-8", newline="\n")

    tasks, warnings = load_tasks(workspace)

    assert len(tasks) == well_formed_count
    assert len(warnings) == 10
    assert all(w.reason == "task_unterminated_comment" for w in warnings)
