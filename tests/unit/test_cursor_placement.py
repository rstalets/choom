from __future__ import annotations

from choom.tui.edit_screen import _pad_for_cursor

# FR-039: the cursor's line is separated from the last non-empty line by exactly
# one blank line -- two lines below the content, not one. Every assertion below
# checks the separator explicitly, because "the last line of the buffer is empty"
# is also true of the off-by-one that these tests originally locked in.


def test_content_without_trailing_blanks_gets_a_blank_line_then_the_cursor_line() -> None:
    padded, cursor_row = _pad_for_cursor("# Notes\nfirst line")

    assert padded == "# Notes\nfirst line\n\n"
    assert cursor_row == 3  # 0-indexed -- "line 4" in the contract's 1-indexed table

    lines = padded.split("\n")
    assert lines[1] == "first line"  # last content
    assert lines[2] == ""  # the separating blank line
    assert lines[cursor_row] == ""  # the line the cursor sits on


def test_content_with_several_trailing_blanks_is_normalised_not_stacked() -> None:
    padded, cursor_row = _pad_for_cursor("# Notes\nfirst line\n\n\n")

    # Same result as no trailing blanks at all (FR-040) -- existing trailing
    # blank lines are collapsed, not added to.
    assert padded == "# Notes\nfirst line\n\n"
    assert cursor_row == 3


def test_content_with_exactly_one_trailing_blank_is_still_given_the_separator() -> None:
    padded, cursor_row = _pad_for_cursor("abc\n\n")

    assert padded == "abc\n\n"
    assert cursor_row == 2


def test_content_with_no_trailing_newline_at_all() -> None:
    padded, cursor_row = _pad_for_cursor("abc")

    assert padded == "abc\n\n"
    assert cursor_row == 2


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

    assert padded == "line1\n\nline2\n\n"
    assert cursor_row == 4


def test_multiple_paragraphs_with_trailing_blanks() -> None:
    padded, cursor_row = _pad_for_cursor("one\n\ntwo\n\nthree\n\n\n\n")

    assert padded == "one\n\ntwo\n\nthree\n\n"
    assert cursor_row == 6


def test_cursor_line_is_always_blank_and_always_preceded_by_a_blank_line() -> None:
    for text in ("a", "a\n", "a\n\n", "a\nb", "a\nb\n\n\n\n", "x\n\ny"):
        padded, cursor_row = _pad_for_cursor(text)
        lines = padded.split("\n")

        assert cursor_row == len(lines) - 1, text
        assert lines[cursor_row] == "", text
        # The separator: without this the cursor would sit directly under the
        # content, which is the bug this test file previously enshrined.
        assert lines[cursor_row - 1] == "", text
        assert lines[cursor_row - 2].strip() != "", text


def test_padding_is_idempotent_reopening_an_already_padded_buffer() -> None:
    once, _row = _pad_for_cursor("# Notes\nfirst line")
    twice, cursor_row = _pad_for_cursor(once)

    # A user who saves without typing persists the padding; reopening that file
    # must not stack a second blank line on top of it.
    assert twice == once
    assert cursor_row == 3
