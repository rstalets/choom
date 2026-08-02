from __future__ import annotations

from textual.widgets import TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.collection_bar import CollectionBar
from tests.helpers import editor_pane, to_collection


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
