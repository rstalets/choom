from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main

EXPECTED_KEYS = {"id", "path", "title", "type", "tags", "created", "updated"}


def test_json_output_has_seven_key_schema(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "vendor landscape", "--type", "research", "--tag", "procurement"])
    capsys.readouterr()

    exit_code = main(["note", "list", "--json"])
    assert exit_code == 0

    records = json.loads(capsys.readouterr().out)
    assert len(records) == 1
    assert set(records[0].keys()) == EXPECTED_KEYS


def test_filters_combine_conjunctively(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "research one", "--type", "research", "--tag", "platform"])
    capsys.readouterr()
    main(["note", "new", "research two", "--type", "research", "--tag", "legal"])
    capsys.readouterr()
    main(["note", "new", "idea", "--type", "idea", "--tag", "platform"])
    capsys.readouterr()

    main(["note", "list", "--json", "--type", "research", "--tag", "platform"])
    records = json.loads(capsys.readouterr().out)

    assert len(records) == 1
    assert records[0]["title"] == "research one"


def test_since_is_inclusive_and_filters_by_created_date(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "new", "old note"])
    capsys.readouterr()

    exit_code = main(["note", "list", "--json", "--since", "2099-01-01"])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_type_daily_selects_exactly_the_daily_notes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["note", "today"])
    capsys.readouterr()
    main(["note", "new", "an idea", "--type", "idea"])
    capsys.readouterr()

    main(["note", "list", "--json", "--type", "daily"])
    records = json.loads(capsys.readouterr().out)

    assert len(records) == 1
    assert records[0]["type"] == "daily"


def test_empty_workspace_lists_empty_array_and_exits_0(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["note", "list", "--json"])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_empty_workspace_no_json_prints_nothing_and_exits_0(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["note", "list"])
    assert exit_code == 0
    assert capsys.readouterr().out == ""
