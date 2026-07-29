from __future__ import annotations

from pathlib import Path

from endpaper.cli.main import main


def test_init_creates_all_five_paths_and_exits_0(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    exit_code = main(["init"])
    assert exit_code == 0

    assert (tmp_path / ".endpaper" / "config.toml").is_file()
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "meetings").is_dir()
    assert (tmp_path / "notes" / "daily").is_dir()
    assert (tmp_path / "tasks.md").is_file()

    out = capsys.readouterr().out.strip()
    assert out == str(tmp_path.resolve())


def test_reinit_exits_3_and_modifies_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])

    config_path = tmp_path / ".endpaper" / "config.toml"
    before = config_path.read_text()

    exit_code = main(["init"])
    assert exit_code == 3

    after = config_path.read_text()
    assert before == after

    err = capsys.readouterr().err
    assert str(tmp_path.resolve()) in err
