from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.preview_screen import PreviewScreen


async def test_command_bar_creates_meeting_with_inline_tags_anywhere(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        text = "meeting.standup Q3 #platform planning #legal"
        for ch in text:
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        meeting = app.screen.meeting
        assert meeting.title == "Q3 planning"
        assert meeting.tags == ("platform", "legal")
        assert meeting.type == "standup"
        assert "#" not in meeting.title
