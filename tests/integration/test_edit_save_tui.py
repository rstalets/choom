from __future__ import annotations

import re
from datetime import datetime

from textual.widgets import TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import EditScreen, _pad_for_cursor
from choom.tui.list_screen import DocumentRow
from choom.tui.preview_screen import PreviewScreen
from tests.helpers import (
    in_scope_month,
    list_view,
    open_edit,
    row_titles,
    to_collection,
    type_literally,
)

_UPDATED = re.compile(r"^updated: (.+)$", re.MULTILINE)
_CREATED = re.compile(r"^created: (.+)$", re.MULTILINE)


async def test_e_opens_raw_markdown_including_frontmatter(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    original_text = meeting.path.read_text(encoding="utf-8")
    # The cursor lands one blank line below the file's content (US7,
    # FR-039); trailing blanks the file already had are normalised into
    # that same single line rather than stacked (FR-040).
    expected_text, _cursor_row = _pad_for_cursor(original_text)

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == expected_text
        assert editor.text.startswith("---\n")


async def test_ctrl_o_writes_and_preserves_cursor_position(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\nAn appended line.\n"
        editor.cursor_location = (2, 3)

        await pilot.press("ctrl+o")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        assert editor.cursor_location == (2, 3)
        path = app.screen.pane.target.display_path
        assert "An appended line." in path.read_text(encoding="utf-8")


async def test_ctrl_s_behaves_identically_to_ctrl_o(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\nSaved via ctrl+s.\n"

        await pilot.press("ctrl+s")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        path = app.screen.pane.target.display_path
        assert "Saved via ctrl+s." in path.read_text(encoding="utf-8")


async def test_ctrl_x_saves_and_returns_to_preview_with_new_content(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text.replace("Q3 planning", "Q3 planning (revised)")

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        from textual.widgets import Markdown

        rendered = app.screen.query_one("#full-preview", Markdown)
        assert "Q3 planning (revised)" in rendered._markdown  # type: ignore[attr-defined]


async def test_title_change_appears_in_list_row_with_no_other_row_moved(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "first meeting", now=in_scope_month(20, 9))
    create_meeting(tmp_workspace, "second meeting", now=in_scope_month(21, 9))
    create_meeting(tmp_workspace, "third meeting", now=in_scope_month(22, 9))

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        list_view(app).index = 1  # "second meeting" (newest-first: third, second, first)

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text.replace("second meeting", "second meeting (renamed)")

        await pilot.press("ctrl+x")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        assert row_titles(app) == ["third meeting", "second meeting (renamed)", "first meeting"]


async def test_updated_advances_while_created_stays_fixed(tmp_workspace: Workspace) -> None:
    # A fixed past time within the current month: month-scoping still finds it,
    # and it is guaranteed to differ from the real "now" the save stamps in.
    now = datetime.now()
    meeting = create_meeting(
        tmp_workspace, "Q3 planning", type="standup", now=now.replace(day=1, hour=0, minute=0)
    )
    original_created = meeting.created

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\nnew body content\n"

        await pilot.press("ctrl+o")
        await pilot.pause()

        text = meeting.path.read_text(encoding="utf-8")
        created_match = _CREATED.search(text)
        updated_match = _UPDATED.search(text)
        assert created_match is not None
        assert updated_match is not None
        assert created_match.group(1) == original_created
        assert updated_match.group(1) != original_created


async def test_esc_without_editing_leaves_bytes_and_mtime_untouched(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before_bytes = meeting.path.read_bytes()
    before_mtime = meeting.path.stat().st_mtime_ns

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)

        await pilot.press("escape")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert meeting.path.read_bytes() == before_bytes
        assert meeting.path.stat().st_mtime_ns == before_mtime


async def test_resize_while_editing_preserves_buffer_cursor_and_dirty_state(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text + "\nresize me not away.\n"
        editor.cursor_location = (1, 3)
        expected_text = editor.text

        await pilot.resize_terminal(120, 40)
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text == expected_text
        assert editor.cursor_location == (1, 3)
        assert app.screen.pane.is_dirty is True


async def test_edit_that_drops_out_of_active_filter_moves_selection_to_remaining_row(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "vendor renewal", tags=("procurement",))
    create_meeting(tmp_workspace, "standup", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("/")
        await pilot.pause()
        # Kept on `type_literally` deliberately: this asserts on the live,
        # narrows-as-you-type filtering, which `type_command`'s single
        # assignment shortcut would not exercise.
        await type_literally(pilot, "filter vendor")
        await pilot.pause()
        assert len(app.visible_documents()) == 1

        await pilot.press("enter")  # closes the filter bar, applying the filter
        await pilot.pause()

        assert isinstance(list_view(app).highlighted_child, DocumentRow)

        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text.replace("vendor renewal", "totally different title")

        await pilot.press("ctrl+x")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        # the edited document no longer matches "vendor" -- it must not remain
        # selected, and the list must not be left with nothing highlighted
        highlighted = list_view(app).highlighted_child
        assert len(app.visible_documents()) == 0 or (
            isinstance(highlighted, DocumentRow)
            and highlighted.document.title != "totally different title"
        )
