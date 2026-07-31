from __future__ import annotations

import json

from endpaper.core.models import Workspace
from endpaper.core.tasks import load_tasks


def test_malformed_file_is_skipped_warned_and_left_byte_identical(cli) -> None:
    cli("meeting", "new", "Q3 planning", "--type", "standup")

    broken = cli.root / "meetings" / "2026-07-28-broken.md"
    broken.write_text("---\nid: broken\n", encoding="utf-8")
    before = broken.read_bytes()

    result = cli("meeting", "list", "--json")
    assert result.exit_code == 0

    records = json.loads(result.out)
    assert len(records) == 1
    assert records[0]["title"] == "Q3 planning"

    assert "broken" in result.err

    after = broken.read_bytes()
    assert before == after


def test_malformed_note_is_skipped_warned_and_left_byte_identical_and_others_still_list(
    cli,
) -> None:
    cli("note", "new", "vendor landscape", "--type", "research")

    broken = cli.root / "notes" / "2026-07-28-broken.md"
    broken.write_text("---\nid: broken\n", encoding="utf-8")
    before = broken.read_bytes()

    result = cli("note", "list", "--json")
    assert result.exit_code == 0

    records = json.loads(result.out)
    assert len(records) == 1
    assert records[0]["title"] == "vendor landscape"

    assert "broken" in result.err

    after = broken.read_bytes()
    assert before == after


def test_one_in_ten_malformed_task_lines_still_lists_all_well_formed(
    tmp_workspace: Workspace,
) -> None:
    lines = []
    well_formed_count = 0
    for i in range(100):
        if i % 10 == 0:
            lines.append(f"- [ ] broken {i} <!-- id:\n")
        else:
            lines.append(f"- [ ] task {i} <!-- id:t_{i:04x} -->\n")
            well_formed_count += 1
    tmp_workspace.tasks_file.write_text("".join(lines), encoding="utf-8", newline="\n")

    tasks, warnings = load_tasks(tmp_workspace)

    assert len(tasks) == well_formed_count
    assert len(warnings) == 10
    assert all(w.reason == "task_unterminated_comment" for w in warnings)
