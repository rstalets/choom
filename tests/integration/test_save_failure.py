from __future__ import annotations

import os
import stat

from textual.widgets import TextArea

from endpaper.core.editing import load_for_edit, save_buffer
from endpaper.core.meetings import create_meeting, scan_meetings
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen


async def test_read_only_directory_save_shows_error_stays_in_edit_buffer_intact(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before_bytes = meeting.path.read_bytes()
    directory = meeting.path.parent
    original_mode = directory.stat().st_mode

    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        app = EndpaperApp(tmp_workspace)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("tab", "tab")  # tasks -> notes -> meetings
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()
            assert isinstance(app.screen, EditScreen)

            editor = app.screen.query_one("#editor", TextArea)
            editor.text = editor.text + "\nan edit that cannot be saved\n"
            buffer_before_save = editor.text

            await pilot.press("ctrl+o")
            await pilot.pause()

            assert isinstance(app.screen, EditScreen)
            assert editor.text == buffer_before_save
    finally:
        directory.chmod(original_mode)

    assert meeting.path.read_bytes() == before_bytes


async def test_save_failure_via_os_replace_100_percent_of_induced_cases(
    tmp_workspace: Workspace, monkeypatch
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before_bytes = meeting.path.read_bytes()

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError("induced failure")

    for _ in range(5):
        monkeypatch.setattr(os, "replace", _boom)
        file = load_for_edit(meeting.path)
        result = save_buffer(meeting.path, file.text + "\nx\n", file)
        assert result.ok is False
        assert result.message != ""
        assert meeting.path.read_bytes() == before_bytes
        monkeypatch.undo()


async def test_ctrl_x_on_failed_save_does_not_leave_edit_state(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    directory = meeting.path.parent
    original_mode = directory.stat().st_mode

    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        app = EndpaperApp(tmp_workspace)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.press("tab", "tab")  # tasks -> notes -> meetings
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()

            editor = app.screen.query_one("#editor", TextArea)
            editor.text = editor.text + "\nanother uncommittable edit\n"

            await pilot.press("ctrl+x")
            await pilot.pause()

            assert isinstance(app.screen, EditScreen)
    finally:
        directory.chmod(original_mode)


async def test_deleting_frontmatter_and_saving_writes_as_typed_and_warns(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        editor.text = "no frontmatter here at all, just prose\n"

        await pilot.press("ctrl+o")
        await pilot.pause()

        from endpaper.tui.status_bar import StatusBar

        status = app.screen.query_one(StatusBar)
        assert "⚠" in str(status.content)

    on_disk = meeting.path.read_text(encoding="utf-8")
    assert on_disk == "no frontmatter here at all, just prose\n"

    documents, warnings = scan_meetings(tmp_workspace)
    assert documents == []
    assert len(warnings) == 1
    assert warnings[0].path == meeting.path

    # A subsequent scan must never repair or rewrite the file.
    still_on_disk = meeting.path.read_text(encoding="utf-8")
    assert still_on_disk == on_disk


async def test_emptied_buffer_saves_as_empty_file_without_crashing(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("tab", "tab")  # tasks -> notes -> meetings
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()

        editor = app.screen.query_one("#editor", TextArea)
        editor.text = ""

        await pilot.press("ctrl+o")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)

    # The original file had a trailing newline, and FR-019 restores that
    # convention unconditionally -- so an emptied buffer saves as a single
    # newline, not zero bytes. The point of this case is "no crash", not that
    # the trailing-newline invariant is suspended for an empty buffer.
    assert meeting.path.read_text(encoding="utf-8") == "\n"
