from __future__ import annotations

import json


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
