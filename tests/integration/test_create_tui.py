from __future__ import annotations

import pytest

from choom.core.documents import _read_document
from choom.core.meetings import scan_meetings
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import ListScreen
from choom.tui.status_bar import StatusBar
from tests.helpers import type_command, type_literally


@pytest.mark.parametrize(
    ("command_text", "dir_attr", "title", "doc_type", "tags"),
    [
        pytest.param(
            "meeting.standup Q3 #platform planning #legal",
            "meetings_dir",
            "Q3 planning",
            "standup",
            ("platform", "legal"),
            id="meeting",
        ),
        pytest.param(
            "note.research vendor landscape #procurement",
            "notes_dir",
            "vendor landscape",
            "research",
            ("procurement",),
            id="note",
        ),
    ],
)
async def test_dotted_command_creates_typed_document_with_tags(
    tmp_workspace: Workspace,
    command_text: str,
    dir_attr: str,
    title: str,
    doc_type: str,
    tags: tuple[str, ...],
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, command_text)

        assert isinstance(app.screen, EditScreen)
        document = _read_document(app.screen.target.display_path)
        assert document is not None
        assert document.title == title
        assert document.tags == tags
        assert document.type == doc_type
        assert "#" not in document.title
        assert document.path.is_relative_to(getattr(tmp_workspace, dir_attr))


async def test_retyped_leading_slash_is_an_unknown_command(tmp_workspace: Workspace) -> None:
    # The '/' that opens the bar is a separate widget now (research R3): the
    # Input's value never contains it. A user who retypes '/' anyway gets a
    # literal '/' in the command text, which matches no verb -- an error, not
    # the old `_normalize()` workaround that silently stripped it.
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await type_literally(pilot, "/meeting board")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        status = app.screen.query_one(StatusBar)
        assert "unknown command" in str(status.content)
        meetings, _ = scan_meetings(tmp_workspace)
        assert meetings == []


async def test_dotted_command_with_no_description_shows_error_not_silence(
    tmp_workspace: Workspace,
) -> None:
    # "meeting.board" parses as type="board" with an empty description -- that's
    # a real usage error (no title), but it must be visible, not a silent no-op.
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "meeting.board")

        assert isinstance(app.screen, ListScreen)
        meetings, _ = scan_meetings(tmp_workspace)
        assert meetings == []
        status = app.screen.query_one(StatusBar)
        assert "empty" in str(status.content)


async def test_bare_note_with_description_creates_untyped_note_not_daily(
    tmp_workspace: Workspace,
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note vendor landscape")

        assert isinstance(app.screen, EditScreen)
        document = _read_document(app.screen.target.display_path)
        assert document is not None
        assert document.title == "vendor landscape"
        assert document.type == ""

        # The daily note must not exist -- a description means a note, never
        # the daily note (spec Assumptions, R5).
        assert list(tmp_workspace.daily_dir.glob("*.md")) == []
