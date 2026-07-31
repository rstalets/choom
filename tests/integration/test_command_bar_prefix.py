from __future__ import annotations

from textual.widgets import Input

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.command_bar import CommandBar


async def test_slash_prefix_appears_and_is_undeletable(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        await pilot.press("/")
        await pilot.pause()
        bar = app.screen.query_one(CommandBar)
        assert bar.display is True
        prefix = bar.query_one("#bar-prefix")
        assert str(prefix.content) == "/"  # type: ignore[attr-defined]

        # The prefix is a separate widget -- no editing key on the Input can
        # touch it (FR-027, FR-028).
        for _ in range(5):
            await pilot.press("backspace")
        await pilot.pause()

        assert str(prefix.content) == "/"  # type: ignore[attr-defined]
        assert bar.display is True
        assert bar.query_one(Input).value == ""


async def test_typing_after_the_prefix_never_includes_the_slash(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await pilot.press("f", "i", "l", "t", "e", "r")
        await pilot.pause()

        bar = app.screen.query_one(CommandBar)
        assert bar.query_one(Input).value == "filter"
