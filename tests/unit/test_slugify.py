from __future__ import annotations

import pytest

from choom.core.text import slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Q3 planning", "q3-planning"),
        ("Q3   planning!!", "q3-planning"),
        ("Café résumé", "cafe-resume"),
        ("!!!", "untitled"),
        ("🎉🎉", "untitled"),
        ("", "untitled"),
    ],
)
def test_slug_table(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_truncates_to_40_chars_and_strips_trailing_hyphen_after_cut() -> None:
    sentence = "this is a very long meeting description that goes past forty characters"
    slug = slugify(sentence)
    assert len(slug) <= 40
    assert not slug.endswith("-")


def test_truncation_boundary_strips_hyphen_created_by_cut() -> None:
    # 39 word chars + a hyphen would land exactly on the 40-char cut boundary.
    text = "a" * 39 + " " + "b" * 10
    slug = slugify(text)
    assert len(slug) <= 40
    assert not slug.endswith("-")
