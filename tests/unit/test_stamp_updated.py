from __future__ import annotations

from endpaper.core.editing import stamp_updated

_TIMESTAMP = "2026-07-28T09:14:00"


def _diff_line_count(before: str, after: str) -> int:
    before_lines = before.split("\n")
    after_lines = after.split("\n")
    assert len(before_lines) == len(after_lines)
    return sum(1 for b, a in zip(before_lines, after_lines, strict=True) if b != a)


def test_normal_block_stamps_only_updated_line() -> None:
    text = (
        "---\n"
        "id: m_20260101_aaaa\n"
        'type: "standup"\n'
        'title: "Q3 planning"\n'
        'tags: ["platform"]\n'
        "created: 2026-01-01T09:00:00\n"
        "updated: 2026-01-01T09:00:00\n"
        "---\n"
        "\n"
        "Body text.\n"
    )
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is True
    assert _diff_line_count(text, new_text) == 1
    assert f"updated: {_TIMESTAMP}" in new_text
    assert "created: 2026-01-01T09:00:00" in new_text


def test_created_is_never_touched() -> None:
    text = "---\ncreated: 2026-01-01T09:00:00\nupdated: 2026-01-01T09:00:00\n---\n"
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is True
    assert "created: 2026-01-01T09:00:00" in new_text


def test_user_added_seventh_field_preserved() -> None:
    text = "---\nid: m_1\nupdated: 2026-01-01T09:00:00\nextra: hand-added\n---\n"
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is True
    assert "extra: hand-added" in new_text


def test_hand_reordered_fields_preserve_order() -> None:
    text = '---\ntitle: "reordered"\nupdated: 2026-01-01T09:00:00\nid: m_1\n---\n'
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is True
    lines = new_text.split("\n")
    assert lines[1] == 'title: "reordered"'
    assert lines[3] == "id: m_1"


def test_single_quoted_values_preserved() -> None:
    text = "---\nid: m_1\ntitle: 'single quoted'\nupdated: 2026-01-01T09:00:00\n---\n"
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is True
    assert "title: 'single quoted'" in new_text


def test_no_frontmatter_returns_unchanged() -> None:
    text = "just a plain markdown file\n"
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is False
    assert new_text == text


def test_unterminated_block_returns_unchanged() -> None:
    text = "---\nid: m_1\nupdated: 2026-01-01T09:00:00\nno terminator here\n"
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is False
    assert new_text == text


def test_block_with_no_updated_line_returns_unchanged() -> None:
    text = '---\nid: m_1\ntitle: "no updated key"\n---\n'
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is False
    assert new_text == text


def test_two_updated_lines_only_first_stamped() -> None:
    text = "---\nupdated: 2026-01-01T09:00:00\nupdated: 2026-01-02T09:00:00\n---\n"
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is True
    lines = new_text.split("\n")
    assert lines[1] == f"updated: {_TIMESTAMP}"
    assert lines[2] == "updated: 2026-01-02T09:00:00"


def test_updated_in_body_below_block_is_untouched() -> None:
    text = "---\nid: m_1\n---\n\nSee updated: below, not frontmatter.\n"
    new_text, stamped = stamp_updated(text, _TIMESTAMP)
    assert stamped is False
    assert new_text == text


def test_empty_string_is_not_stampable() -> None:
    new_text, stamped = stamp_updated("", _TIMESTAMP)
    assert stamped is False
    assert new_text == ""
