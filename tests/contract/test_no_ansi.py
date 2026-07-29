from __future__ import annotations

from pathlib import Path

from endpaper.cli.main import main


def _assert_clean(text: str) -> None:
    assert "\x1b" not in text


def test_no_ansi_in_any_redirected_command_output(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    main(["init"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "list"])
    _assert_clean(capsys.readouterr().out)

    main(["meeting", "list", "--json"])
    _assert_clean(capsys.readouterr().out)

    exit_code = main(["meeting", "list", "--since", "not-a-date"])
    assert exit_code == 2
    captured = capsys.readouterr()
    _assert_clean(captured.out)
    _assert_clean(captured.err)

    main(["note", "today"])
    _assert_clean(capsys.readouterr().out)

    main(["note", "new", "an idea", "--type", "idea", "--tag", "misc"])
    _assert_clean(capsys.readouterr().out)

    main(["note", "list"])
    _assert_clean(capsys.readouterr().out)

    main(["note", "list", "--json"])
    _assert_clean(capsys.readouterr().out)

    exit_code = main(["note", "list", "--since", "not-a-date"])
    assert exit_code == 2
    captured = capsys.readouterr()
    _assert_clean(captured.out)
    _assert_clean(captured.err)
