from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from choom.cli.main import main

EXPECTED_KEYS = {"id", "path", "title", "type", "tags", "created", "updated"}
#: 019-completed-tasks-partition adds `completed` and `file`, additive only
#: (constitution Principle II) -- kept as an exact-set assertion on purpose,
#: so a key that is renamed or removed still fails loudly here.
EXPECTED_TASK_KEYS = {
    "id",
    "text",
    "done",
    "type",
    "tags",
    "links",
    "created",
    "line",
    "body",
    "completed",
    "file",
}


def test_json_schema_has_exactly_seven_keys_and_no_nulls(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "hallway chat"])
    capsys.readouterr()

    main(["meeting", "list", "--json"])
    out = capsys.readouterr().out
    assert out.startswith("[")
    assert out.rstrip("\n").endswith("]")
    records = json.loads(out)

    assert len(records) == 1
    record = records[0]
    assert set(record.keys()) == EXPECTED_KEYS

    assert record["type"] == ""
    assert record["tags"] == []
    assert isinstance(record["title"], str)
    assert "/" in record["path"]
    assert "\\" not in record["path"]


def test_note_list_json_has_exactly_the_same_seven_keys(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "vendor landscape", "--type", "research", "--tag", "procurement"])
    capsys.readouterr()

    main(["note", "list", "--json"])
    out = capsys.readouterr().out
    assert out.startswith("[")
    assert out.rstrip("\n").endswith("]")
    records = json.loads(out)

    assert len(records) == 1
    record = records[0]
    assert set(record.keys()) == EXPECTED_KEYS
    assert record["id"].startswith("note_")
    assert "/" in record["path"]
    assert "\\" not in record["path"]


def test_task_list_json_has_exactly_seven_keys_id_and_created_nullable(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    capsys.readouterr()
    (tmp_path / "tasks.md").write_text(
        (tmp_path / "tasks.md").read_text(encoding="utf-8") + "- [ ] bare task\n",
        encoding="utf-8",
    )

    main(["task", "list", "--json", "--all"])
    records = json.loads(capsys.readouterr().out)

    assert len(records) == 2
    for record in records:
        assert set(record.keys()) == EXPECTED_TASK_KEYS
        assert record["type"] == "" or isinstance(record["type"], str)
        assert isinstance(record["tags"], list)

    typed = next(r for r in records if r["text"] == "buy milk")
    assert typed["type"] == ""
    assert typed["tags"] == []
    assert typed["id"] is not None
    assert typed["created"] is not None
    # 019-completed-tasks-partition: an open task carries no completion date
    # and lives in tasks.md.
    assert typed["completed"] is None
    assert typed["file"] == "tasks.md"

    bare = next(r for r in records if r["text"] == "bare task")
    assert bare["id"] is not None  # backfilled by load_tasks
    assert bare["created"] is None
    assert bare["completed"] is None
    assert bare["file"] == "tasks.md"


def test_task_list_json_completed_is_an_iso_date_and_file_names_the_done_store(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """019-completed-tasks-partition: `completed` and `file` are additive
    keys on the task record; this pins their actual values for a record
    that has moved, not just their presence in the key set above."""
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    task_id = capsys.readouterr().out.strip()

    main(["task", "done", task_id])
    capsys.readouterr()

    main(["task", "list", "--json", "--done"])
    records = json.loads(capsys.readouterr().out)

    assert len(records) == 1
    record = records[0]
    assert record["completed"] == date.today().isoformat()
    assert record["file"].startswith("tasks/done/")
    assert record["file"].endswith("-done.md")
    assert "tasks.md" not in record["file"]


def test_task_list_json_carries_body_for_every_entry(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    task_id = capsys.readouterr().out.strip()
    tasks_path = tmp_path / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8") + "\n  a detail line\n", encoding="utf-8"
    )

    main(["task", "list", "--json"])
    records = json.loads(capsys.readouterr().out)

    assert len(records) == 1
    assert records[0]["id"] == task_id
    assert records[0]["body"] == "a detail line"


def test_task_show_json_matches_the_shape_of_a_list_entry(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["task", "add", "buy milk"])
    task_id = capsys.readouterr().out.strip()

    main(["task", "list", "--json"])
    list_record = json.loads(capsys.readouterr().out)[0]

    main(["task", "show", task_id, "--json"])
    show_record = json.loads(capsys.readouterr().out)

    assert show_record == list_record
    assert show_record["body"] == ""


#: The four keys this surface carried before 013-assistant-discovery-file. Adding a
#: key is a minor change (constitution II); this set exists so a future change that
#: renames or removes one of these four -- the one thing that would actually be
#: breaking -- fails loudly here rather than passing by accident.
PRE_EXISTING_CONFIG_ASSISTANT_KEYS = {"configured", "resolved", "source", "available"}

#: The two keys 013-assistant-discovery-file adds (FR-016, FR-033): `discovery_file`
#: (absolute path string, or null) and `launch_offer_made` (boolean).
EXPECTED_CONFIG_ASSISTANT_KEYS = PRE_EXISTING_CONFIG_ASSISTANT_KEYS | {
    "discovery_file",
    "launch_offer_made",
}


def test_config_assistant_json_keys_and_available_is_never_null(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["config", "assistant", "--json"])
    record = json.loads(capsys.readouterr().out)
    assert set(record.keys()) == EXPECTED_CONFIG_ASSISTANT_KEYS
    assert record["configured"] is None
    assert record["available"] == [] or isinstance(record["available"], list)
    assert record["available"] is not None
    assert record["discovery_file"] is None
    assert record["launch_offer_made"] is False

    main(["config", "assistant", "claude"])
    capsys.readouterr()
    main(["config", "assistant", "--json"])
    record = json.loads(capsys.readouterr().out)
    assert set(record.keys()) == EXPECTED_CONFIG_ASSISTANT_KEYS
    assert record["configured"] == "claude"
    assert record["resolved"] == "claude"
    assert record["source"] == "configured"
    # discovery_file/launch_offer_made depend on whether a real `claude` profile
    # location was writable in the test's isolated profile root -- covered in depth
    # by tests/contract/test_config_assistant_cli.py; only the key set and types
    # matter here.
    assert record["discovery_file"] is None or isinstance(record["discovery_file"], str)
    assert isinstance(record["launch_offer_made"], bool)
