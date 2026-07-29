from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main

EXPECTED_KEYS = {"id", "path", "title", "type", "tags", "created", "updated"}


def test_json_schema_has_exactly_seven_keys_and_no_nulls(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "hallway chat"])
    capsys.readouterr()

    main(["meeting", "list", "--json"])
    records = json.loads(capsys.readouterr().out)

    assert len(records) == 1
    record = records[0]
    assert set(record.keys()) == EXPECTED_KEYS

    assert record["type"] == ""
    assert record["tags"] == []
    assert isinstance(record["title"], str)
    assert "/" in record["path"]
    assert "\\" not in record["path"]
