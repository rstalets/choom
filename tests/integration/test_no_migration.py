from __future__ import annotations

import hashlib
import json


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def test_old_scheme_ids_still_list_read_and_resolve_with_no_migration(cli) -> None:
    """A workspace holding pre-008 ids (`m_`, `n_`, `t_`) still lists, reads, and
    resolves under the new `meeting_`/`note_`/`task_` scheme, and no file is
    rewritten to adopt it (US1 AC4, FR-013, SC-007)."""
    cli("meeting", "new", "Q3 planning")
    cli("note", "new", "vendor landscape")
    cli("task", "add", "call Terry about the renewal")

    meeting_path = next((cli.root / "meetings").rglob("*.md"))
    note_path = next((cli.root / "notes").rglob("*.md"))
    tasks_path = cli.root / "tasks.md"

    meeting_text = meeting_path.read_text(encoding="utf-8")
    meeting_text = meeting_text.replace("id: meeting_", "id: m_", 1)
    meeting_path.write_text(meeting_text, encoding="utf-8")

    note_text = note_path.read_text(encoding="utf-8")
    note_text = note_text.replace("id: note_", "id: n_", 1)
    note_path.write_text(note_text, encoding="utf-8")

    tasks_text = tasks_path.read_text(encoding="utf-8")
    tasks_text = tasks_text.replace("id:task_", "id:t_", 1)
    tasks_path.write_text(tasks_text, encoding="utf-8")
    before_hash = _md5(tasks_path.read_bytes())

    meeting_result = cli("meeting", "list", "--json")
    assert meeting_result.exit_code == 0
    meetings = json.loads(meeting_result.out)
    assert any(m["id"].startswith("m_") for m in meetings)

    note_result = cli("note", "list", "--json")
    assert note_result.exit_code == 0
    notes = json.loads(note_result.out)
    assert any(n["id"].startswith("n_") for n in notes)

    task_result = cli("task", "list", "--json")
    assert task_result.exit_code == 0
    tasks = json.loads(task_result.out)
    assert any(t["id"] is not None and t["id"].startswith("t_") for t in tasks)

    after_hash = _md5(tasks_path.read_bytes())
    assert before_hash == after_hash


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
