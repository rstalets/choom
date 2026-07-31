from __future__ import annotations

import json


def test_pre_feature_007_tasks_file_lists_unchanged_with_no_rewrite(cli) -> None:
    """A tasks.md from before task bodies existed has no indented continuation
    lines. It must list every task exactly as before, with an empty `body` in
    the JSON listing, and the file itself must not be touched by the read
    (FR-006, SC-006)."""
    original = (
        "- [ ] one <!-- id:t_0001 created:2026-07-20 -->\n"
        "- [x] two <!-- id:t_0002 type:followup tags:legal created:2026-07-21 -->\n"
    )
    tasks_path = cli.root / "tasks.md"
    tasks_path.write_text(original, encoding="utf-8", newline="\n")
    before = tasks_path.read_bytes()

    result = cli("task", "list", "--json", "--all")
    assert result.exit_code == 0
    records = json.loads(result.out)
    assert [r["id"] for r in records] == ["t_0001", "t_0002"]
    assert all(r["body"] == "" for r in records)

    assert tasks_path.read_bytes() == before


def test_workspace_with_no_notes_returns_empty_from_every_note_command(cli) -> None:
    """A workspace created by feature 001 (init already creates notes/daily/, so there is
    nothing to migrate) returns an empty result from every note command rather than
    failing, with no migration step (SC-010)."""
    result = cli("note", "list", "--json")
    assert result.exit_code == 0
    assert json.loads(result.out) == []

    result = cli("note", "list")
    assert result.exit_code == 0
    assert result.out == ""

    result = cli("note", "today")
    assert result.exit_code == 0
    assert result.out.startswith("notes/daily/")
    assert (cli.root / result.out).is_file()
