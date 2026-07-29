from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListScreen


async def test_tui_opens_on_meetings_list(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)


async def test_empty_workspace_shows_empty_state_message(tmp_workspace: Workspace) -> None:
    from endpaper.tui.list_screen import EMPTY_STATE_MESSAGE, ListView

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        list_view = app.screen.query_one("#meeting-list", ListView)
        labels = [str(item.children[0].content) for item in list_view.children]  # type: ignore[attr-defined]
        assert labels == [EMPTY_STATE_MESSAGE]
