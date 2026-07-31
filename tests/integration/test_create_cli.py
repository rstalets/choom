from __future__ import annotations

import pytest


def test_create_prints_relative_path_and_exits_0(cli) -> None:
    r = cli("meeting", "new", "Q3 planning", "--type", "standup", "--tag", "platform")
    assert r.exit_code == 0
    assert r.out.startswith("meetings/")
    assert r.out.endswith("-standup-q3-planning.md")
    assert (cli.root / r.out).is_file()


def test_typed_note_creation_with_tags(cli) -> None:
    r = cli("note", "new", "vendor landscape", "--type", "research", "--tag", "procurement")
    assert r.exit_code == 0
    assert r.out.startswith("notes/")
    assert r.out.endswith("-research-vendor-landscape.md")
    text = cli.read(r.out)
    assert 'type: "research"' in text
    assert '"procurement"' in text


@pytest.mark.parametrize(
    ("noun", "description", "slug"),
    [
        ("meeting", "hallway chat", "hallway-chat"),
        ("note", "some idea", "some-idea"),
    ],
)
def test_untyped_create_omits_type_segment_from_filename(
    cli, noun: str, description: str, slug: str
) -> None:
    r = cli(noun, "new", description)
    assert f"-{slug}.md" in r.out
    text = cli.read(r.out)
    assert 'type: ""' in text


@pytest.mark.parametrize("noun", ["meeting", "note"])
def test_quoted_hash_tag_is_extracted_from_description(cli, noun: str) -> None:
    r = cli(noun, "new", "vendor call #procurement #legal")
    text = cli.read(r.out)
    assert 'title: "vendor call"' in text
    assert '"procurement"' in text
    assert '"legal"' in text
    assert "#" not in text.split("title:")[1].split("\n")[0]


@pytest.mark.parametrize("noun", ["meeting", "note"])
def test_repeated_tag_preserves_order_and_dedupes(cli, noun: str) -> None:
    r = cli(
        noun,
        "new",
        "vendor renewal",
        "--tag",
        "legal",
        "--tag",
        "procurement",
        "--tag",
        "legal",
    )
    text = cli.read(r.out)
    assert 'tags: ["legal", "procurement"]' in text


def test_same_day_collision_suffixes_and_leaves_original_untouched(cli) -> None:
    first = cli("note", "new", "vendor landscape", "--type", "research")
    first_text_before = cli.read(first.out)

    second = cli("note", "new", "vendor landscape", "--type", "research")

    assert first.out != second.out
    assert second.out.endswith("-2.md")
    assert cli.read(first.out) == first_text_before
