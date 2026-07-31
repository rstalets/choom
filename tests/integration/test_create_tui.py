from __future__ import annotations

from endpaper.core.documents import _read_document
from endpaper.core.meetings import scan_meetings
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import ListScreen
from endpaper.tui.status_bar import StatusBar


async def _type(pilot, text: str) -> None:
    for ch in text:
        if ch == " ":
            await pilot.press("space")
        elif ch == "/":
            await pilot.press("slash")
        else:
            await pilot.press(ch)


async def test_command_bar_creates_meeting_with_inline_tags_anywhere(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "meeting.standup Q3 #platform planning #legal")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        meeting = _read_document(app.screen.file.path)
        assert meeting is not None
        assert meeting.title == "Q3 planning"
        assert meeting.tags == ("platform", "legal")
        assert meeting.type == "standup"
        assert "#" not in meeting.title


async def test_retyped_leading_slash_is_an_unknown_command(tmp_workspace: Workspace) -> None:
    # The '/' that opens the bar is a separate widget now (research R3): the
    # Input's value never contains it. A user who retypes '/' anyway gets a
    # literal '/' in the command text, which matches no verb -- an error, not
    # the old `_normalize()` workaround that silently stripped it.
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "/meeting board")
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
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "meeting.board")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        meetings, _ = scan_meetings(tmp_workspace)
        assert meetings == []
        status = app.screen.query_one(StatusBar)
        assert "empty" in str(status.content)
