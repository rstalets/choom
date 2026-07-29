from __future__ import annotations

from pathlib import Path

from endpaper.cli.main import main


def test_typed_note_creation_with_tags(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    exit_code = main(
        ["note", "new", "vendor landscape", "--type", "research", "--tag", "procurement"]
    )
    assert exit_code == 0

    out = capsys.readouterr().out.strip()
    assert out.startswith("notes/")
    assert out.endswith("-research-vendor-landscape.md")
    text = (tmp_path / out).read_text()
    assert 'type: "research"' in text
    assert '"procurement"' in text


def test_untyped_note_omits_type_segment_from_filename(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["note", "new", "some idea"])
    out = capsys.readouterr().out.strip()

    assert "-some-idea.md" in out
    text = (tmp_path / out).read_text()
    assert 'type: ""' in text


def test_same_day_collision_suffixes_and_leaves_original_untouched(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["note", "new", "vendor landscape", "--type", "research"])
    first_out = capsys.readouterr().out.strip()
    first_text_before = (tmp_path / first_out).read_text()

    main(["note", "new", "vendor landscape", "--type", "research"])
    second_out = capsys.readouterr().out.strip()

    assert first_out != second_out
    assert second_out.endswith("-2.md")
    assert (tmp_path / first_out).read_text() == first_text_before


def test_quoted_hash_tag_is_extracted_from_note_description(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(["note", "new", "vendor call #procurement #legal"])
    out = capsys.readouterr().out.strip()

    text = (tmp_path / out).read_text()
    assert 'title: "vendor call"' in text
    assert '"procurement"' in text
    assert '"legal"' in text


def test_repeated_tag_preserves_order_and_dedupes_for_notes(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["init"])
    capsys.readouterr()

    main(
        [
            "note",
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
