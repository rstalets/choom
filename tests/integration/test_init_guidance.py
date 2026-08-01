from __future__ import annotations

from pathlib import Path

from choom.cli.main import main


def test_claude_md_created_in_empty_directory_and_names_agents_md(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    exit_code = main(["init"])
    assert exit_code == 0

    claude_md = tmp_path / "CLAUDE.md"
    assert claude_md.is_file()
    assert "AGENTS.md" in claude_md.read_text(encoding="utf-8")

    err = capsys.readouterr().err
    assert err == ""


def test_preexisting_claude_md_byte_identical_after_init(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    original = "# My own instructions\n\nDo not touch.\n"
    claude_md.write_text(original, encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    exit_code = main(["init"])
    assert exit_code == 0
    assert claude_md.read_text(encoding="utf-8") == original

    out = capsys.readouterr()
    assert str(tmp_path.resolve()) in out.out
    assert "CLAUDE.md" in out.err


def test_preexisting_agents_md_byte_identical_after_init(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    agents_md = tmp_path / "AGENTS.md"
    original = "# Existing repo conventions\n\nRead me first.\n"
    agents_md.write_text(original, encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    exit_code = main(["init"])
    assert exit_code == 0
    assert agents_md.read_text(encoding="utf-8") == original

    out = capsys.readouterr()
    assert str(tmp_path.resolve()) in out.out
    assert "AGENTS.md" in out.err
