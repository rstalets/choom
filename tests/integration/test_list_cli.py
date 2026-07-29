from __future__ import annotations

import json
from pathlib import Path

from endpaper.cli.main import main


def test_json_output_is_an_array_of_objects(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform"])
    capsys.readouterr()

    exit_code = main(["meeting", "list", "--json"])
    assert exit_code == 0

    out = capsys.readouterr().out
    records = json.loads(out)
    assert isinstance(records, list)
    assert len(records) == 1
    assert records[0]["title"] == "Q3 planning"


def test_filters_combine_conjunctively(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "standup one", "--type", "standup", "--tag", "platform"])
    capsys.readouterr()
    main(["meeting", "new", "standup two", "--type", "standup", "--tag", "legal"])
    capsys.readouterr()
    main(["meeting", "new", "vendor call", "--type", "vendor", "--tag", "platform"])
    capsys.readouterr()

    main(["meeting", "list", "--json", "--type", "standup", "--tag", "platform"])
    out = capsys.readouterr().out
    records = json.loads(out)

    assert len(records) == 1
    assert records[0]["title"] == "standup one"


def test_empty_workspace_lists_empty_array_and_exits_0(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["meeting", "list", "--json"])
    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == []


def test_empty_workspace_no_json_prints_nothing_and_exits_0(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["meeting", "list"])
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_bad_since_is_usage_error_and_lists_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()
    main(["meeting", "new", "Q3 planning"])
    capsys.readouterr()

    exit_code = main(["meeting", "list", "--json", "--since", "yesterday"])
    assert exit_code == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--since" in captured.err
