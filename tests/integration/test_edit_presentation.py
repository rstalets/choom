from __future__ import annotations

from textual.widgets import TextArea

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen


async def _open_edit(app: EndpaperApp, pilot) -> None:  # type: ignore[no-untyped-def]
    await pilot.pause()
    await pilot.press("tab", "tab")  # tasks -> notes -> meetings
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("e")
    await pilot.pause()
    assert isinstance(app.screen, EditScreen)


async def test_editor_configuration_matches_contract(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.show_line_numbers is True
        assert editor.soft_wrap is True
        assert editor.tab_behavior == "focus"


async def test_gutter_line_one_is_opening_frontmatter_marker(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        first_line = editor.get_line(0)
        assert str(first_line) == "---"


async def test_wide_paragraph_wraps_without_horizontal_scroll(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    long_paragraph = "word " * 60
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + "\n" + long_paragraph + "\n",
        encoding="utf-8",
    )

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(40, 24)) as pilot:
        await _open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        assert editor.soft_wrap is True
        assert editor.scrollable_content_region.width <= editor.size.width


async def test_hundred_body_lines_all_present(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    body_lines = "\n".join(f"line {i}" for i in range(100))
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + "\n" + body_lines + "\n",
        encoding="utf-8",
    )

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        assert "line 0" in editor.text
        assert "line 99" in editor.text


async def test_tab_key_does_not_insert_a_tab_character(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        before = editor.text

        await pilot.press("tab")
        await pilot.pause()

        assert editor.text == before
        assert "\t" not in editor.text


async def test_footer_shows_edit_help(tmp_workspace: Workspace) -> None:
    from endpaper.tui.status_bar import EDIT_HELP, StatusBar

    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_edit(app, pilot)
        status = app.screen.query_one(StatusBar)
        assert str(status.content).startswith(EDIT_HELP)


async def test_non_ascii_and_emoji_round_trip_intact(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    extra = "café — 笔记 🎉 שלום עולם"
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + "\n" + extra + "\n", encoding="utf-8"
    )

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await _open_edit(app, pilot)
        editor = app.screen.query_one("#editor", TextArea)
        assert extra in editor.text

        await pilot.press("ctrl+o")
        await pilot.pause()

        assert extra in meeting.path.read_text(encoding="utf-8")
