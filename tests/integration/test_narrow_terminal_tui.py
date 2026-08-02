from __future__ import annotations

import re

from textual.widgets import TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.collection_bar import CollectionBar
from tests.helpers import editor_pane, list_view, to_collection


async def test_narrow_terminal_does_not_crash_and_keeps_active_collection_visible(
    tmp_workspace: Workspace,
) -> None:
    # Spec edge case: "a terminal too narrow for three panes plus the top bar"
    # must degrade without truncating the collection names into ambiguity, and
    # the highlighted collection must remain identifiable.
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(20, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        assert "[reverse]" in rendered  # the active collection is still marked
        plain = rendered.replace("[reverse]", "").replace("[/reverse]", "")
        # The compact one-letter form is decided from the collections' own
        # width alone, never from whether the workspace path (US6) also fits
        # -- it is exactly what it always was, never truncated into
        # ambiguity (FR-036). The path itself is free to overflow a terminal
        # this narrow rather than disappear (spec edge case).
        assert plain.startswith("T N M")


async def test_extremely_narrow_terminal_still_boots(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(10, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"


async def test_inline_editor_wraps_without_horizontal_scroll_at_40_columns(
    tmp_workspace: Workspace,
) -> None:
    # `#preview-pane` is narrower than the full screen the editor used to
    # have at this width, and carries a line-number gutter (research R11) --
    # the same no-horizontal-scroll property the full-screen editor already
    # guarantees (test_edit_presentation.py) must hold inline too.
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    long_paragraph = "word " * 60
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + "\n" + long_paragraph + "\n",
        encoding="utf-8",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(40, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("e")
        await pilot.pause()

        pane = editor_pane(app)
        editor = pane.query_one("#editor", TextArea)
        assert editor.soft_wrap is True
        assert editor.scrollable_content_region.width <= editor.size.width


# --- T025 (020-vertical-tui-mode, US4, FR-039): width degradation is
# identical in vertical -- the same mechanisms, exercised at the same size,
# just with vertical active first.


async def test_vertical_at_20x24_still_compacts_the_collection_bar(
    tmp_workspace: Workspace,
) -> None:
    from choom.core.preferences import set_view_orientation
    from choom.tui.collection_bar import CollectionBar

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(20, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        # Vertical is still active -- width alone never triggers the
        # horizontal fallback (FR-035/FR-039); only height does.
        assert app.screen.query("#upper-band")

        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        assert "[reverse]" in rendered
        plain = rendered.replace("[reverse]", "").replace("[/reverse]", "")
        # Identical compact form to the horizontal case
        # (test_narrow_terminal_does_not_crash_and_keeps_active_collection_visible
        # above): decided from the collections' own width alone, never from
        # whether vertical's wider list pane also fits.
        assert plain.startswith("T N M")


async def test_vertical_at_20x24_list_still_drops_to_date_and_title_only(
    tmp_workspace: Workspace,
) -> None:
    """Date and title are never dropped, however narrow the pane (FR-032,
    `columns.py::column_widths`) -- the same rule as horizontal, just
    exercised against whatever width vertical's `#list-pane` ends up with
    at this terminal size."""
    from choom.core.preferences import set_view_orientation
    from choom.tui.list_screen import DocumentRow

    set_view_orientation("vertical")
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(20, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        row = next(r for r in list_view(app).children if isinstance(r, DocumentRow))
        text = str(row.children[0].content)  # type: ignore[attr-defined]
        # Date always survives (10 chars, YYYY-MM-DD); title always
        # survives too, even if truncated to a single-character ellipsis at
        # this width -- it is never dropped outright the way type/tags are
        # (FR-032). No wall-clock literal (Principle VI): checked by shape,
        # not by today's actual date.
        date_cell = text[:10]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_cell)
        assert len(text.strip()) > 10  # something -- the title column -- follows it


async def test_width_alone_never_triggers_the_horizontal_fallback(
    tmp_workspace: Workspace,
) -> None:
    """A terminal 1000 rows tall and 10 columns wide stays vertical --
    the threshold is a height floor, never a width one."""
    from choom.core.preferences import set_view_orientation

    set_view_orientation("vertical")
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(10, 1000)) as pilot:
        await pilot.pause()
        assert app.screen.query("#upper-band")
