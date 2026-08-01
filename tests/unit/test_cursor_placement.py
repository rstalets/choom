from __future__ import annotations

from choom.tui.edit_screen import _pad_for_cursor


def test_content_without_trailing_blanks_gets_one_blank_line_appended() -> None:
    padded, cursor_row = _pad_for_cursor("# Notes\nfirst line")

    assert padded == "# Notes\nfirst line\n"
    assert cursor_row == 2  # 0-indexed -- "line 3" in the contract's 1-indexed table


def test_content_with_several_trailing_blanks_is_normalised_not_stacked() -> None:
    padded, cursor_row = _pad_for_cursor("# Notes\nfirst line\n\n\n")

    # Same result as no trailing blanks at all (FR-040) -- existing trailing
    # blank lines are collapsed, not added to.
    assert padded == "# Notes\nfirst line\n"
    assert cursor_row == 2


def test_content_with_exactly_one_trailing_blank_is_unchanged_in_shape() -> None:
    padded, cursor_row = _pad_for_cursor("abc\n\n")

    assert padded == "abc\n"
    assert cursor_row == 1


def test_content_with_no_trailing_newline_at_all() -> None:
    padded, cursor_row = _pad_for_cursor("abc")

    assert padded == "abc\n"
    assert cursor_row == 1


def test_empty_content_gets_nothing_inserted_above() -> None:
    padded, cursor_row = _pad_for_cursor("")

    assert padded == ""
    assert cursor_row == 0


def test_whitespace_only_content_behaves_like_empty_content() -> None:
    padded, cursor_row = _pad_for_cursor("\n\n\n")

    assert padded == ""
    assert cursor_row == 0


def test_internal_blank_lines_are_preserved_only_trailing_ones_are_touched() -> None:
    padded, cursor_row = _pad_for_cursor("line1\n\nline2")

    assert padded == "line1\n\nline2\n"
    assert cursor_row == 3


def test_multiple_paragraphs_with_trailing_blanks() -> None:
    padded, cursor_row = _pad_for_cursor("one\n\ntwo\n\nthree\n\n\n\n")

    assert padded == "one\n\ntwo\n\nthree\n"
    assert cursor_row == 5


def test_resulting_cursor_row_always_points_at_the_final_blank_line() -> None:
    for text in ("a", "a\n", "a\n\n", "a\nb", "a\nb\n\n\n\n"):
        padded, cursor_row = _pad_for_cursor(text)
        lines = padded.split("\n")
        assert cursor_row == len(lines) - 1
        assert lines[cursor_row] == ""
