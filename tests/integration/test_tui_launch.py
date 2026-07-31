from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListScreen
from tests.helpers import list_view


async def test_tui_opens_on_tasks_list(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)
        assert app.active == "tasks"


async def test_empty_workspace_shows_empty_state_message(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        labels = [str(item.children[0].content) for item in list_view(app).children]  # type: ignore[attr-defined]
        assert labels == ["No tasks yet. Press / then 'task <description>' to create one."]
