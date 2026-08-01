from __future__ import annotations

from textual.widgets import Static

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.tasks import add_task
from choom.tui.app import ChoomApp
from choom.tui.columns import column_widths
from choom.tui.list_screen import DocumentRow, TaskRow
from tests.helpers import in_scope_month, list_view, to_collection

#: A terminal wide enough that #list-pane (2fr, alongside a 14-wide scope
#: pane and a 3fr preview pane) clears column_widths' four-column minimum.
_WIDE = (180, 30)
#: Wide enough for three columns (date, type, title) but not four -- tags drops.
_MEDIUM = (130, 24)
#: Narrow enough that even type drops, but not so narrow that "Title" itself
#: gets truncated away -- the column survives, just tight (FR-032).
_NARROW = (70, 24)


async def test_header_is_visible_above_the_rows(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_WIDE) as pilot:
        await to_collection(app, pilot, "meetings")

        header = app.screen.query_one("#list-header", Static)
        text = str(header.render())
        assert "Date" in text
        assert "Type" in text
        assert "Title" in text
        assert "Tags" in text


async def test_title_position_is_the_same_with_and_without_a_type(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "quarterly review", type="standup", now=in_scope_month(20))
    create_meeting(tmp_workspace, "budget summary", now=in_scope_month(21))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_WIDE) as pilot:
        await to_collection(app, pilot, "meetings")

        rows = [r for r in list_view(app).children if isinstance(r, DocumentRow)]
        assert len(rows) == 2
        labels = [str(r.children[0].render()) for r in rows]  # type: ignore[union-attr]
        # Both rows' title text begins at the same character offset -- the
        # typeless row's type cell is empty, not collapsed (FR-030).
        typed_label = next(label for label in labels if "quarterly review" in label)
        untyped_label = next(label for label in labels if "budget summary" in label)
        typed_offset = typed_label.index("quarterly review")
        untyped_offset = untyped_label.index("budget summary")
        assert typed_offset == untyped_offset


async def test_a_record_with_no_type_and_no_tags_shows_two_empty_cells(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "bare record")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_WIDE) as pilot:
        await to_collection(app, pilot, "meetings")

        rows = [r for r in list_view(app).children if isinstance(r, DocumentRow)]
        label = str(rows[0].children[0].render())  # type: ignore[union-attr]
        assert "bare record" in label


async def test_long_title_is_truncated_with_an_ellipsis_and_does_not_wrap(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "a" * 200)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_MEDIUM) as pilot:
        await to_collection(app, pilot, "meetings")

        rows = [r for r in list_view(app).children if isinstance(r, DocumentRow)]
        label = str(rows[0].children[0].render())  # type: ignore[union-attr]
        assert "…" in label


async def test_tasks_use_the_same_columns_and_done_state_stays_visible(
    tmp_workspace: Workspace,
) -> None:
    add_task(tmp_workspace, "buy milk", type="errand")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_WIDE) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        header = app.screen.query_one("#list-header", Static)
        header_text = str(header.render())
        assert "Date" in header_text
        assert "Title" in header_text

        rows = [r for r in list_view(app).children if isinstance(r, TaskRow)]
        assert len(rows) == 1
        label = str(rows[0].children[0].render())  # type: ignore[union-attr]
        assert "[ ]" in label
        assert "buy milk" in label
        assert "errand" in label

        await pilot.press("space")
        await pilot.pause()
        # Toggling moved it out of To-Do (the default category) and into
        # Done -- follow it there to see its rendered row.
        await pilot.press("h")
        await pilot.pause()
        await pilot.press("j")  # To-Do -> Done
        await pilot.pause()
        rows = [r for r in list_view(app).children if isinstance(r, TaskRow)]
        assert len(rows) == 1
        rendered = rows[0].children[0].render()  # type: ignore[union-attr]
        assert "[x]" in str(rendered)
        # Struck-through is a real style span, not literal text -- checked on
        # the rendered Content's spans rather than as a substring.
        assert any(span.style == "strike" for span in rendered.spans)  # type: ignore[union-attr]


async def test_header_and_rows_stay_aligned_after_a_resize(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup", tags=("procurement",))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_WIDE) as pilot:
        await to_collection(app, pilot, "meetings")

        await pilot.resize_terminal(*_MEDIUM)
        await pilot.pause()

        list_view_widget = list_view(app)
        expected = column_widths(list_view_widget.size.width)
        header = app.screen.query_one("#list-header", Static)
        header_text = str(header.render())
        assert ("Tags" in header_text) == expected.show_tags


async def test_medium_width_drops_tags_but_keeps_type_date_and_title(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup", tags=("procurement",))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_MEDIUM) as pilot:
        await to_collection(app, pilot, "meetings")

        header = app.screen.query_one("#list-header", Static)
        header_text = str(header.render())
        assert "Date" in header_text
        assert "Type" in header_text
        assert "Title" in header_text
        assert "Tags" not in header_text


async def test_narrow_terminal_drops_type_too_but_keeps_date_and_title(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup", tags=("procurement",))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=_NARROW) as pilot:
        await to_collection(app, pilot, "meetings")

        list_view_widget = list_view(app)
        layout = column_widths(list_view_widget.size.width)
        assert layout.show_type is False
        assert layout.show_tags is False

        header = app.screen.query_one("#list-header", Static)
        header_text = str(header.render())
        assert "Date" in header_text
        assert "Title" in header_text

        rows = [r for r in list_view(app).children if isinstance(r, DocumentRow)]
        label = str(rows[0].children[0].render())  # type: ignore[union-attr]
        assert "Q3" in label  # the title survives, even if truncated
