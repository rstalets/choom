from __future__ import annotations

import endpaper
from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.status_bar import StatusBar, render_version


async def test_version_renders_on_the_list_screen(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        assert render_version() in str(status.content)
        assert f"v{endpaper.__version__}" in str(status.content)


async def test_version_renders_on_the_preview_screen(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        status = app.screen.query_one(StatusBar)
        assert render_version() in str(status.content)


async def test_version_renders_on_the_edit_screen(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        status = app.screen.query_one(StatusBar)
        assert render_version() in str(status.content)
