from __future__ import annotations

import json


def test_note_list_never_returns_a_meeting_and_vice_versa(cli) -> None:
    cli("meeting", "new", "Q3 planning")
    cli("note", "new", "an idea")

    notes = json.loads(cli("note", "list", "--json").out)
    assert len(notes) == 1
    assert notes[0]["id"].startswith("n_")

    meetings = json.loads(cli("meeting", "list", "--json").out)
    assert len(meetings) == 1
    assert meetings[0]["id"].startswith("m_")


def test_non_markdown_files_under_notes_are_ignored(cli) -> None:
    cli("note", "new", "an idea")

    (cli.root / "notes" / "readme.txt").write_text("not a note", encoding="utf-8")

    result = cli("note", "list", "--json")
    assert result.exit_code == 0
    records = json.loads(result.out)
    assert len(records) == 1


def test_notes_subtree_is_scanned_recursively_including_arbitrary_subdirectories(cli) -> None:
    # Post-003 (YYYY/MM partitioning): scan_documents walks a collection's whole
    # subtree, not just its top level, so any nested .md file with valid
    # frontmatter is now discoverable -- including a user's own subdirectories.
    cli("note", "new", "an idea")

    nested_dir = cli.root / "notes" / "archive"
    nested_dir.mkdir()
    (nested_dir / "2020-01-01-old.md").write_text(
        '---\nid: n_20200101_deadbeef\ntype: ""\ntitle: "old"\ntags: []\n'
        "created: 2020-01-01T09:00:00\nupdated: 2020-01-01T09:00:00\n---\n",
        encoding="utf-8",
    )

    result = cli("note", "list", "--json")
    assert result.exit_code == 0
    records = json.loads(result.out)
    assert len(records) == 2
    titles = {r["title"] for r in records}
    assert titles == {"an idea", "old"}
