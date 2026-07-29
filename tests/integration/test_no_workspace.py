from __future__ import annotations

from pathlib import Path

from endpaper.cli.main import main


def test_bare_endpaper_outside_workspace_exits_3_with_guidance(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)

    exit_code = main([])
    assert exit_code == 3

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "no workspace found" in captured.err
    assert "endpaper init" in captured.err


def test_meeting_list_outside_workspace_exits_3(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    exit_code = main(["meeting", "list"])
    assert exit_code == 3
    assert "no workspace found" in capsys.readouterr().err
