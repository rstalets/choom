from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main


def test_workspace_with_no_notes_returns_empty_from_every_note_command(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A workspace created by feature 001 (init already creates notes/daily/, so there is
    nothing to migrate) returns an empty result from every note command rather than
    failing, with no migration step (SC-010)."""
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["note", "list", "--json"])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == []

    exit_code = main(["note", "list"])
    assert exit_code == 0
    assert capsys.readouterr().out == ""

    exit_code = main(["note", "today"])
    assert exit_code == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("notes/daily/")
    assert (tmp_path / out).is_file()
