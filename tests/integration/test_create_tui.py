from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListScreen
from endpaper.tui.preview_screen import PreviewScreen
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

        assert isinstance(app.screen, PreviewScreen)
        meeting = app.screen.meeting
        assert meeting.title == "Q3 planning"
        assert meeting.tags == ("platform", "legal")
        assert meeting.type == "standup"
        assert "#" not in meeting.title


async def test_retyped_leading_slash_still_creates_untyped_meeting(
    tmp_workspace: Workspace,
) -> None:
    # Users naturally retype the '/' that opened the bar even though it isn't
    # inserted automatically -- this must not be misread as a filter.
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await _type(pilot, "/meeting board")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.meeting.title == "board"
        assert app.screen.meeting.type == ""


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
        assert len(app.meetings) == 0
        status = app.screen.query_one(StatusBar)
        assert "empty" in str(status.content)
