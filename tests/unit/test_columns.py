from __future__ import annotations

from choom.tui.columns import TASK_LEAD, column_widths, render_header, render_row


def test_all_four_columns_fit_at_80_columns() -> None:
    layout = column_widths(80)

    assert layout.show_type is True
    assert layout.show_tags is True

    header = render_header(layout)
    assert "Date" in header
    assert "Type" in header
    assert "Title" in header
    assert "Tags" in header


def test_narrow_width_drops_tags_first() -> None:
    wide = column_widths(80)
    narrower = column_widths(50)

    assert wide.show_tags is True
    assert narrower.show_type is True
    assert narrower.show_tags is False

    header = render_header(narrower)
    assert "Tags" not in header
    assert "Type" in header
    assert "Date" in header
    assert "Title" in header


def test_very_narrow_width_drops_type_too_but_keeps_date_and_title() -> None:
    layout = column_widths(25)

    assert layout.show_type is False
    assert layout.show_tags is False

    header = render_header(layout)
    assert "Date" in header
    assert "Title" in header
    assert "Type" not in header
    assert "Tags" not in header


def test_date_and_title_survive_even_at_extreme_narrowness() -> None:
    layout = column_widths(1)

    assert layout.date_width > 0
    assert layout.title_width >= 1
    header = render_header(layout)
    assert "Date" in header or header  # header renders without raising
    row = render_row(("2026-07-28", "standup", "Q3 planning", "urgent"), layout)
    assert row  # renders without raising, never wraps (single line)
    assert "\n" not in row


def test_empty_type_and_tags_leave_cells_empty_without_shifting_title() -> None:
    layout = column_widths(80)

    with_type = render_row(("2026-07-28", "standup", "Q3 planning", ""), layout)
    without_type = render_row(("2026-07-28", "", "Q3 planning", ""), layout)

    # The title starts at the same character offset regardless of whether the
    # type cell is empty -- an empty cell holds its column's width rather than
    # collapsing (FR-030).
    title_start = len("2026-07-28") + 2 + layout.type_width + 2
    assert with_type[title_start : title_start + len("Q3 planning")] == "Q3 planning"
    assert without_type[title_start : title_start + len("Q3 planning")] == "Q3 planning"
    assert len(with_type) == len(without_type)


def test_a_record_with_no_type_and_no_tags_still_has_date_and_title_in_place() -> None:
    layout = column_widths(80)
    row = render_row(("2026-07-28", "", "Untyped record", ""), layout)
    assert row.startswith("2026-07-28")
    assert "Untyped record" in row


def test_title_wider_than_its_column_is_truncated_with_an_ellipsis() -> None:
    layout = column_widths(40)  # narrow enough that title_width is small
    long_title = "a" * 200
    row = render_row(("2026-07-28", "", long_title, ""), layout)

    assert "…" in row
    assert "\n" not in row
    # The row does not exceed the layout's total rendered width.
    assert len(row) <= 40


def test_tags_wider_than_its_column_is_truncated_with_an_ellipsis() -> None:
    layout = column_widths(80)
    long_tags = ",".join(f"tag{i}" for i in range(20))
    row = render_row(("2026-07-28", "standup", "Q3 planning", long_tags), layout)

    assert len(long_tags) > layout.tags_width
    assert "…" in row


def test_header_never_scrolls_is_a_pure_function_of_width_only() -> None:
    # column_widths takes only an int -- no widget, no I/O -- so it is
    # unit-testable without a terminal (research R8).
    layout_a = column_widths(80)
    layout_b = column_widths(80)
    assert layout_a == layout_b


def test_row_never_wraps_to_a_second_line_at_various_widths() -> None:
    for width in (5, 10, 20, 34, 50, 62, 80, 120):
        layout = column_widths(width)
        row = render_row(("2026-07-28", "standup", "a" * 50, "tag1,tag2,tag3"), layout)
        assert "\n" not in row


def test_task_row_content_carries_the_same_four_fields() -> None:
    # Tasks use the same four columns: date, type, text (as "title"), tags
    # (FR-033); the done marker is layered on by the caller, outside these
    # four columns (spec Assumptions).
    layout = column_widths(80)
    row = render_row(("2026-07-28", "followup", "call the vendor", "procurement"), layout)
    assert "call the vendor" in row
    assert "followup" in row
    assert "procurement" in row


# --- the lead: room for a task's done marker ahead of the first column --------
#
# Substring assertions ("Date" is in the header, the task text is in the row)
# pass just as happily when the header sits four characters left of the cells it
# names and the row overruns the pane. These check offsets and total width.


def test_header_is_indented_by_the_lead_so_names_sit_over_their_cells() -> None:
    layout = column_widths(80, lead=TASK_LEAD)
    header = render_header(layout)
    row = "[ ] " + render_row(("2026-07-28", "followup", "call the vendor", "procurement"), layout)

    assert header.index("Date") == TASK_LEAD == row.index("2026-07-28")
    assert header.index("Title") == row.index("call the vendor")
    assert header.index("Type") == row.index("followup")
    assert header.index("Tags") == row.index("procurement")


def test_lead_is_taken_out_of_the_available_width_so_a_task_row_still_fits() -> None:
    for width in (34, 50, 62, 80, 120):
        layout = column_widths(width, lead=TASK_LEAD)
        row = "[ ] " + render_row(("2026-07-28", "followup", "a" * 60, "procurement"), layout)
        header = render_header(layout)

        assert len(row) == width, width
        assert len(header) == width, width


def test_lead_defaults_to_zero_so_documents_are_unaffected() -> None:
    assert column_widths(80).lead == 0
    assert render_header(column_widths(80)).index("Date") == 0


def test_a_wide_lead_still_leaves_date_and_title() -> None:
    # The lead eats into the same budget the drop order spends (FR-032): date
    # and title survive regardless.
    layout = column_widths(30, lead=TASK_LEAD)
    assert layout.date_width > 0
    assert layout.title_width >= 1
    assert len(render_header(layout)) <= 30
