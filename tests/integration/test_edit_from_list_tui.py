from __future__ import annotations

from textual.widgets import TextArea

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import DocumentRow, ListScreen, ListView


async def _to_meetings(pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.pause()
    await pilot.press("tab", "tab")  # tasks -> notes -> meetings
    await pilot.pause()


async def test_e_from_list_opens_the_raw_markdown(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        assert app.screen.file.path == meeting.path
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text.startswith("---\n")
        assert "Q3 planning" in editor.text


async def test_save_and_exit_returns_to_list_with_the_row_updated(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)

        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text.replace("Q3 planning", "Q3 planning (revised)")

        await pilot.press("ctrl+x")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)
        list_view = app.screen.query_one("#meeting-list", ListView)
        highlighted = list_view.highlighted_child
        assert isinstance(highlighted, DocumentRow)
        assert highlighted.document.title == "Q3 planning (revised)"


async def test_e_is_a_noop_on_tasks(tmp_workspace: Workspace) -> None:
    from endpaper.core.tasks import add_task

    add_task(tmp_workspace, "buy milk")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)


async def test_e_is_a_noop_on_the_empty_state(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)

        await pilot.press("e")
        await pilot.pause()

        assert isinstance(app.screen, ListScreen)


async def test_e_from_list_and_e_from_preview_produce_identical_edit_screens(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    from_list = EndpaperApp(tmp_workspace)
    async with from_list.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("e")
        await pilot.pause()
        list_screen = from_list.screen
        assert type(list_screen) is EditScreen
        list_text = list_screen.query_one("#editor", TextArea).text

    from_preview = EndpaperApp(tmp_workspace)
    async with from_preview.run_test(size=(80, 24)) as pilot:
        await _to_meetings(pilot)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        preview_screen = from_preview.screen
        assert type(preview_screen) is EditScreen
        preview_text = preview_screen.query_one("#editor", TextArea).text

    # Both routes go through the same `open_editor()` (research R10), so they
    # necessarily construct the same screen class with the same bindings --
    # what remains to verify is that the buffer contents agree too.
    assert list_text == preview_text
