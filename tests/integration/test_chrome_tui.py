"""App chrome: the command bar, the collection bar, and the version indicator.

These are all "does the app's surrounding chrome render and behave correctly"
tests, as opposed to tests of a specific collection's behaviour -- hence one
file. Sequential, independent assertions share a single `run_test()` session
where doing so doesn't change what's being asserted, to save on app boots.
"""

from __future__ import annotations

from pathlib import Path

from textual.widgets import Input

import choom
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.workspace import init_workspace
from choom.tui.app import ChoomApp
from choom.tui.collection_bar import COLLECTIONS, CollectionBar
from choom.tui.command_bar import CommandBar
from choom.tui.list_screen import ListView
from choom.tui.status_bar import TASK_LIST_HELP, StatusBar, render_version
from tests.helpers import type_literally


async def test_command_bar_prefix_undeletable_and_input_not_clipped(
    tmp_workspace: Workspace,
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()

        await pilot.press("/")
        await pilot.pause()
        bar = app.screen.query_one(CommandBar)
        assert bar.display is True
        prefix = bar.query_one("#bar-prefix")
        assert str(prefix.content) == "/"  # type: ignore[attr-defined]

        input_widget = bar.query_one(Input)
        # The input's rendered box must not exceed the one-row command bar it lives
        # in -- Input defaults to a 3-row bordered box, which previously clipped the
        # text row out of view, leaving only a border line visible.
        assert input_widget.region.height == bar.region.height == 1

        # The prefix is a separate widget -- no editing key on the Input can
        # touch it (FR-027, FR-028).
        for _ in range(5):
            await pilot.press("backspace")
        await pilot.pause()

        assert str(prefix.content) == "/"  # type: ignore[attr-defined]
        assert bar.display is True
        assert input_widget.value == ""

        # Typed text after the prefix must never include the slash itself. This
        # is one of the tests guarding `type_command`'s single-assignment
        # shortcut, so it types keystroke-by-keystroke rather than taking it.
        await type_literally(pilot, "filter")
        await pilot.pause()
        assert input_widget.value == "filter"

        # And it must actually render on screen rather than being clipped out
        # of view (the failure mode the region-height assertion above guards).
        svg = app.export_screenshot()
        assert "filter" in svg


async def test_collection_bar_lists_three_and_tab_cycles_with_wraparound(
    tmp_workspace: Workspace,
) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert COLLECTIONS == ("tasks", "notes", "meetings")
        assert app.active == "tasks"

        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        assert "Tasks" in rendered
        assert "Notes" in rendered
        assert "Meetings" in rendered
        # exactly one collection is styled as active
        assert rendered.count("[reverse]") == 1

        await pilot.press("tab")
        await pilot.pause()
        assert app.active == "notes"
        list_view = app.screen.query_one("#meeting-list", ListView)
        assert list_view.has_focus
        assert list_view.index == 0

        await pilot.press("tab")
        await pilot.pause()
        assert app.active == "meetings"

        await pilot.press("tab")
        await pilot.pause()
        assert app.active == "tasks"  # wrapped past Meetings back to Tasks

        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.active == "meetings"  # wraps the other way too


async def test_tab_inert_while_command_bar_open(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        await pilot.press("/")
        await pilot.pause()
        await type_literally(pilot, "fil")
        await pilot.pause()

        await pilot.press("tab")
        await pilot.pause()

        assert app.active == "tasks"  # unchanged -- the keystroke belonged to the bar
        assert app.screen.query_one(CommandBar).display is True


async def test_version_indicator_renders_on_list_preview_and_edit_screens(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        assert render_version() in str(status.content)
        assert f"v{choom.__version__}" in str(status.content)

        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        assert render_version() in str(status.content)

        await pilot.press("e")
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        assert render_version() in str(status.content)


# --- US6: the workspace path in the top bar ------------------------------------


async def test_top_bar_shows_the_workspace_path_flush_right(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    create_meeting(workspace, "Q3 planning")

    app = ChoomApp(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        # Right-aligned: the path is the last thing on the line, not
        # interleaved with the collection names (FR-034).
        assert rendered.rstrip().endswith(workspace.root.name)


async def test_top_bar_stays_flush_right_after_a_resize(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace

    app = ChoomApp(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        await pilot.resize_terminal(90, 30)
        await pilot.pause()
        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        assert rendered.rstrip().endswith(workspace.root.name)


async def test_workspace_path_with_space_and_non_ascii_renders_correctly(
    tmp_path: Path,
) -> None:
    odd_dir = tmp_path / "OneDrive - Cömpany" / "nötes"
    odd_dir.mkdir(parents=True)
    workspace = init_workspace(odd_dir).workspace

    app = ChoomApp(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        assert "nötes" in rendered
        assert "�" not in rendered  # no mangled encoding
        # The layout is otherwise unaffected -- the collection names are
        # still present and unstyled markup tags stay balanced.
        assert "Tasks" in rendered
        assert "Notes" in rendered
        assert "Meetings" in rendered


async def test_bottom_bar_is_unchanged_by_the_workspace_path(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace

    app = ChoomApp(workspace)
    async with app.run_test(size=(120, 30)) as pilot:
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        rendered = str(status.content)
        assert TASK_LIST_HELP in rendered
        assert render_version() in rendered
        # No width from the bottom bar is spent on the workspace path
        # (FR-038) -- it never appears there.
        assert workspace.root.name not in rendered
