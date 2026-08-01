"""The list's four labelled columns: date, type, title, tags.

Pure functions of a width, with no widget imports, so the layout math --
which of the four columns fit, how wide each is, where truncation kicks in --
is unit-testable without a terminal (research R8). `list_screen.py` is the
only caller; it supplies the pane's width and renders the results into a
header `Static` and each row's `Label`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

_SEP = "  "
_DATE_WIDTH = 10  # "YYYY-MM-DD"
_TYPE_WIDTH = 10
_TAGS_WIDTH = 16
_MIN_TITLE_WIDTH = 10

_HEADERS = ("Date", "Type", "Title", "Tags")

#: Visible width of a task row's done marker plus its trailing space -- "[x] ".
#: The marker sits *outside* the four labelled columns (spec Assumptions), so the
#: columns start this far in on a task row and the header has to start there too.
TASK_LEAD = 4


@dataclass(frozen=True, slots=True)
class ColumnLayout:
    """Which columns survive at a given width, and how wide each one is.

    Date and title are never dropped (FR-032); `show_type`/`show_tags` say
    whether the other two are present. Widths are character counts, exclusive
    of the separator between columns.

    `lead` is the number of characters the columns are indented by -- 0 for
    documents, `TASK_LEAD` for tasks, whose done marker precedes the first
    column. It is subtracted from the available width before the columns are
    sized and re-applied by `render_header`, so the header's names sit over the
    cells they name instead of `lead` characters to their left, and a task row
    is no wider than the pane.
    """

    show_type: bool
    show_tags: bool
    date_width: int
    type_width: int
    title_width: int
    tags_width: int
    lead: int = 0


def column_widths(total: int, *, lead: int = 0) -> ColumnLayout:
    """Compute the column layout for a pane `total` characters wide.

    Tries four columns, then drops tags, then drops type as well -- date and
    title always remain, however narrow `total` is (FR-032). The title
    column absorbs whatever width is left over once the fixed-width columns
    and the separators between them are accounted for.

    `lead` reserves space ahead of the first column for a row prefix the
    columns do not own -- a task's done marker. The columns are sized against
    what is left, so `lead + rendered row` never exceeds `total`.

    Never raises. `total` need not be large enough for any column to look
    good; `title_width` is clamped to at least 1.
    """
    sep = len(_SEP)
    total = max(0, total - lead)
    four_columns_min = _DATE_WIDTH + sep + _TYPE_WIDTH + sep + _MIN_TITLE_WIDTH + sep + _TAGS_WIDTH
    three_columns_min = _DATE_WIDTH + sep + _TYPE_WIDTH + sep + _MIN_TITLE_WIDTH

    if total >= four_columns_min:
        title_width = total - (_DATE_WIDTH + sep + _TYPE_WIDTH + sep + _TAGS_WIDTH + sep)
        return ColumnLayout(
            show_type=True,
            show_tags=True,
            date_width=_DATE_WIDTH,
            type_width=_TYPE_WIDTH,
            title_width=title_width,
            tags_width=_TAGS_WIDTH,
            lead=lead,
        )

    if total >= three_columns_min:
        title_width = total - (_DATE_WIDTH + sep + _TYPE_WIDTH + sep)
        return ColumnLayout(
            show_type=True,
            show_tags=False,
            date_width=_DATE_WIDTH,
            type_width=_TYPE_WIDTH,
            title_width=title_width,
            tags_width=0,
            lead=lead,
        )

    title_width = max(1, total - (_DATE_WIDTH + sep))
    return ColumnLayout(
        show_type=False,
        show_tags=False,
        date_width=_DATE_WIDTH,
        type_width=0,
        title_width=title_width,
        tags_width=0,
        lead=lead,
    )


def _truncate(value: str, width: int) -> str:
    """`value` padded or truncated to exactly `width` characters, with a
    visible ellipsis marking truncation (FR-031). `width <= 0` renders as
    empty -- the layout's own minimums keep this from happening for title or
    date, but a caller passing an already-degenerate width fails safe rather
    than raising."""
    if width <= 0:
        return ""
    if len(value) <= width:
        return value.ljust(width)
    if width == 1:
        return "…"
    return value[: width - 1] + "…"


def render_header(layout: ColumnLayout) -> str:
    """The header row naming the surviving columns, aligned exactly as
    `render_row` aligns its cells (FR-028, FR-029).

    Indented by `layout.lead`, so on the tasks list -- where every row starts
    with a done marker the columns do not own -- each name still sits directly
    over its own cells rather than over the marker.
    """
    parts = [_truncate(_HEADERS[0], layout.date_width)]
    if layout.show_type:
        parts.append(_truncate(_HEADERS[1], layout.type_width))
    parts.append(_truncate(_HEADERS[2], layout.title_width))
    if layout.show_tags:
        parts.append(_truncate(_HEADERS[3], layout.tags_width))
    return " " * layout.lead + _SEP.join(parts)


def render_row(cells: Sequence[str], layout: ColumnLayout) -> str:
    """One row: `cells` is `(date, type, title, tags)` in that fixed order,
    already formatted as plain strings (e.g. a date already sliced to its
    10-character form, tags already comma-joined). Each surviving column is
    truncated and padded to its width and joined by the same separator the
    header uses, so an empty value leaves its cell empty without shifting any
    other column's position (FR-030), and the title starts at the same
    character offset on every row regardless of which neighbouring fields are
    empty."""
    date, type_, title, tags = cells
    parts = [_truncate(date, layout.date_width)]
    if layout.show_type:
        parts.append(_truncate(type_, layout.type_width))
    parts.append(_truncate(title, layout.title_width))
    if layout.show_tags:
        parts.append(_truncate(tags, layout.tags_width))
    return _SEP.join(parts)
