from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main

EXPECTED_KEYS = {"id", "path", "title", "type", "tags", "created", "updated"}
EXPECTED_TASK_KEYS = {"id", "text", "done", "type", "tags", "links", "created", "line"}


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

    bare = next(r for r in records if r["text"] == "bare task")
    assert bare["id"] is not None  # backfilled by load_tasks
    assert bare["created"] is None


EXPECTED_CONFIG_ASSISTANT_KEYS = {"configured", "resolved", "source", "available"}


def test_config_assistant_json_has_exactly_four_keys_and_available_is_never_null(
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

    main(["config", "assistant", "claude"])
    capsys.readouterr()
    main(["config", "assistant", "--json"])
    record = json.loads(capsys.readouterr().out)
    assert set(record.keys()) == EXPECTED_CONFIG_ASSISTANT_KEYS
    assert record["configured"] == "claude"
    assert record["resolved"] == "claude"
    assert record["source"] == "configured"
