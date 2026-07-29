from __future__ import annotations

from endpaper.core.text import parse_tags


def test_tag_at_start() -> None:
    title, tags = parse_tags("#platform Q3 planning")
    assert title == "Q3 planning"
    assert tags == ("platform",)


def test_tag_in_middle() -> None:
    title, tags = parse_tags("Q3 #platform planning")
    assert title == "Q3 planning"
    assert tags == ("platform",)


def test_tag_at_end() -> None:
    title, tags = parse_tags("Q3 planning #platform")
    assert title == "Q3 planning"
    assert tags == ("platform",)


def test_repeated_tags_deduplicated_preserving_order() -> None:
    title, tags = parse_tags("vendor call #procurement #legal #procurement")
    assert title == "vendor call"
    assert tags == ("procurement", "legal")


def test_no_tags() -> None:
    title, tags = parse_tags("hallway chat")
    assert title == "hallway chat"
    assert tags == ()


def test_tags_only_description_yields_empty_title() -> None:
    title, tags = parse_tags("#onlytags")
    assert title == ""
    assert tags == ("onlytags",)


def test_multiple_tags_anywhere_and_whitespace_collapsed() -> None:
    title, tags = parse_tags("  Q3   #platform  planning  #legal  ")
    assert title == "Q3 planning"
    assert tags == ("platform", "legal")
