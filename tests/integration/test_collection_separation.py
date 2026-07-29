from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main


def test_note_list_never_returns_a_meeting_and_vice_versa(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning"])
    capsys.readouterr()
    main(["note", "new", "an idea"])
    capsys.readouterr()

    main(["note", "list", "--json"])
    notes = json.loads(capsys.readouterr().out)
    assert len(notes) == 1
    assert notes[0]["id"].startswith("n_")

    main(["meeting", "list", "--json"])
    meetings = json.loads(capsys.readouterr().out)
    assert len(meetings) == 1
    assert meetings[0]["id"].startswith("m_")


def test_non_markdown_files_under_notes_are_ignored(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "an idea"])
    capsys.readouterr()

    (tmp_path / "notes" / "readme.txt").write_text("not a note", encoding="utf-8")

    exit_code = main(["note", "list", "--json"])
    assert exit_code == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == 1


def test_subdirectories_of_notes_other_than_daily_are_ignored(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "an idea"])
    capsys.readouterr()

    nested_dir = tmp_path / "notes" / "archive"
    nested_dir.mkdir()
    (nested_dir / "2020-01-01-old.md").write_text(
        '---\nid: n_20200101_deadbeef\ntype: ""\ntitle: "old"\ntags: []\n'
        "created: 2020-01-01T09:00:00\nupdated: 2020-01-01T09:00:00\n---\n",
        encoding="utf-8",
    )

    exit_code = main(["note", "list", "--json"])
    assert exit_code == 0
    records = json.loads(capsys.readouterr().out)
    assert len(records) == 1
    assert records[0]["title"] == "an idea"
