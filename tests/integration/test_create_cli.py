from __future__ import annotations

from pathlib import Path

from endpaper.cli.main import main


def test_create_prints_relative_path_and_exits_0(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(["meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform"])
    assert exit_code == 0

    out = capsys.readouterr().out.strip()
    assert out.startswith("meetings/")
    assert out.endswith("-standup-q3-planning.md")
    assert (tmp_path / out).is_file()


def test_untyped_meeting_has_no_type_segment_in_filename(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["meeting", "new", "hallway chat"])
    out = capsys.readouterr().out.strip()

    assert "-hallway-chat.md" in out
    text = (tmp_path / out).read_text()
    assert 'type: ""' in text


def test_quoted_hash_tag_is_extracted_from_description(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["meeting", "new", "vendor call #procurement #legal"])
    out = capsys.readouterr().out.strip()

    text = (tmp_path / out).read_text()
    assert 'title: "vendor call"' in text
    assert '"procurement"' in text
    assert '"legal"' in text
    assert "#" not in text.split("title:")[1].split("\n")[0]


def test_repeated_tag_preserves_order_and_dedupes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(
        [
            "meeting",
            "new",
            "vendor renewal",
            "--tag",
            "legal",
            "--tag",
            "procurement",
            "--tag",
            "legal",
        ]
    )
    out = capsys.readouterr().out.strip()
    text = (tmp_path / out).read_text()

    assert 'tags: ["legal", "procurement"]' in text
