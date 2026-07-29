from __future__ import annotations

from textual.widgets import Input

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.command_bar import CommandBar


async def test_command_bar_input_is_not_clipped_when_open(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        bar = app.screen.query_one(CommandBar)
        await pilot.press("/")
        await pilot.pause()

        input_widget = bar.query_one(Input)
        # The input's rendered box must not exceed the one-row command bar it lives
        # in -- Input defaults to a 3-row bordered box, which previously clipped the
        # text row out of view, leaving only a border line visible.
        assert input_widget.region.height == bar.region.height == 1

        for ch in "hello":
            await pilot.press(ch)
        await pilot.pause()

        svg = app.export_screenshot()
        assert "hello" in svg
