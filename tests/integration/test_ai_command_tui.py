from __future__ import annotations

import stat
from collections.abc import Callable
from pathlib import Path

import pytest
from textual.widgets import TextArea

from choom.core.config import set_assistant
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.tasks import load_tasks
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import EditScreen
from choom.tui.status_bar import EDIT_HELP, StatusBar
from tests.conftest import STUB_REPLY_TEXT
from tests.helpers import open_edit, submit_editor_line


async def test_reply_replaces_the_command_line(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("reply")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        before_lines = editor.text.splitlines()
        # Everything below the frontmatter block is what must stay untouched --
        # the block's own `updated:` line legitimately changes on save (FR-008).
        body_start = before_lines.index("---", 1) + 1

        line_index = await submit_editor_line(pilot, editor, "/ai summarise the bullets above")
        await app.workers.wait_for_complete()
        await pilot.pause()

        after_lines = editor.text.splitlines()
        assert after_lines[line_index : line_index + 3] == STUB_REPLY_TEXT.splitlines()
        assert after_lines[body_start:line_index] == before_lines[body_start:line_index]
        assert screen.is_dirty is True

        # The document was saved before invocation (FR-008): the file on disk
        # holds the /ai line even though the buffer has since moved on.
        saved = screen.target.display_path.read_text(encoding="utf-8")
        assert "/ai summarise the bullets above" in saved

        status = screen.query_one(StatusBar)
        assert EDIT_HELP in str(status.content)


async def test_reply_with_task_lines_captures_real_linked_tasks(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("reply_with_tasks")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai summarise and track")
        await app.workers.wait_for_complete()
        await pilot.pause()

        reply_lines = [editor.get_line(line_index + offset).plain for offset in range(4)]
        # Prose is byte-identical and in order; task lines are replaced by mirrors.
        assert reply_lines[0] == "Here is a summary of the discussion."
        assert reply_lines[2] == "One more thing worth tracking down the line."
        assert reply_lines[1] != "/task call Terry about the renewal"
        assert reply_lines[3] != "/task.followup review the budget numbers #finance"
        assert reply_lines[1].startswith("- [ ] [call Terry about the renewal]")
        assert reply_lines[3].startswith("- [ ] [review the budget numbers]")

        tasks, warnings = load_tasks(tmp_workspace)
        assert warnings == []
        assert len(tasks) == 2
        first, second = tasks
        assert first.text == "call Terry about the renewal"
        assert first.type == ""
        assert first.links == (meeting.id,)
        assert second.text == "review the budget numbers"
        assert second.type == "followup"
        assert second.tags == ("finance",)
        assert second.links == (meeting.id,)

        for task in tasks:
            assert task.id is not None
            assert f"#{task.id}" in editor.get_line(line_index + (1 if task is first else 3)).plain

        status = screen.query_one(StatusBar)
        status_text = str(status.content)
        assert "2 tasks captured" in status_text
        assert "⚠" not in status_text

        # Still the same screen, editor focused -- no navigation happened.
        assert isinstance(app.screen, EditScreen)
        assert app.screen is screen
        assert editor.has_focus


async def test_reply_containing_a_slash_ai_line_is_inserted_as_literal_text(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("reply_with_slash")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai nest one for me")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert editor.get_line(line_index).plain == "/ai nested attempt"
        assert editor.get_line(line_index + 1).plain == "still here"
        # Inserted text is never re-parsed: no second request was started, and
        # control has already returned to ordinary editing.
        assert screen._request is None
        assert editor.read_only is False


async def test_cancel_restores_the_line_and_kills_the_process(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("sleep")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai anything")
        assert screen._request is not None
        assert editor.read_only is True
        process = screen._request._process  # type: ignore[attr-defined]
        assert process is not None
        assert process.poll() is None  # still running

        await pilot.press("ctrl+c")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert screen._request is None
        assert editor.read_only is False
        assert editor.get_line(line_index).plain == "/ai anything"
        assert process.poll() is not None  # the child is gone, no orphan

        status = screen.query_one(StatusBar)
        assert "⚠" not in str(status.content)  # a requested cancel is not a failure


async def test_non_zero_exit_shows_a_message_and_restores_the_line(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("fail")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        title_line = next(line for line in editor.text.splitlines() if line.startswith("title:"))

        line_index = await submit_editor_line(pilot, editor, "/ai broken")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert editor.get_line(line_index).plain == "/ai broken"
        assert editor.read_only is False
        status = screen.query_one(StatusBar)
        assert "Claude Code CLI" in str(status.content)
        assert "stub failure" in str(status.content)
        # the saved document (from FR-008's pre-invocation save) is untouched
        # beyond the /ai line itself -- frontmatter content survives, and the
        # command line appears exactly once, at the end.
        saved = screen.target.display_path.read_text(encoding="utf-8")
        assert title_line in saved
        assert saved.count("/ai broken") == 1
        assert saved.endswith("/ai broken\n")


async def test_empty_reply_shows_a_message_and_restores_the_line(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("empty")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai say nothing")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert editor.get_line(line_index).plain == "/ai say nothing"
        status = screen.query_one(StatusBar)
        assert "empty reply" in str(status.content)


async def test_no_assistant_available_reports_and_restores_the_line(
    tmp_workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No stub_assistant fixture, and PATH is replaced entirely so this is
    # deterministic even on a machine with a real `claude`/`copilot` installed.
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))

    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai anything")
        await pilot.pause()

        # No profile resolved -- control returns without ever entering the
        # in-flight state, and no request is spawned.
        assert screen._request is None
        assert editor.read_only is False
        assert editor.get_line(line_index).plain == "/ai anything"
        status = screen.query_one(StatusBar)
        assert "/config assistant" in str(status.content)


async def test_configured_but_missing_binary_names_the_assistant(
    tmp_workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Configured as claude, but PATH is replaced entirely -- so this is
    # distinguishable from the generic "nothing found" case (FR-016 edge case).
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    monkeypatch.setenv("PATH", str(empty_bin))
    set_assistant(tmp_workspace, "claude")

    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai anything")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert editor.get_line(line_index).plain == "/ai anything"
        status = screen.query_one(StatusBar)
        assert "Claude Code CLI" in str(status.content)
        assert "not installed" in str(status.content) or "not on your PATH" in str(status.content)


async def test_bare_ai_reports_a_prompt_is_needed(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/ai")
        await pilot.pause()

        assert screen._request is None
        status = screen.query_one(StatusBar)
        assert "needs a prompt" in str(status.content)
        # nothing was saved on account of the bare command
        assert screen.is_dirty is True  # the appended blank command line is still unsaved


async def test_both_assistants_installed_nothing_configured_reports_ambiguous(
    tmp_workspace: Workspace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two stub binaries on PATH, isolated from whatever the host machine has
    # installed for real, and nothing configured -- FR-023.
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name in ("claude", "copilot"):
        script = bindir / name
        script.write_text("#!/usr/bin/env python3\nprint('hi')\n", encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))

    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai anything")
        await pilot.pause()

        assert screen._request is None
        assert editor.get_line(line_index).plain == "/ai anything"
        status = screen.query_one(StatusBar)
        text = str(status.content)
        assert "claude" in text and "copilot" in text
        assert "/config assistant" in text


async def test_resize_mid_request_updates_the_breadcrumb_display(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("sleep")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/ai anything")
        assert screen._request is not None
        status = screen.query_one(StatusBar)
        wide_text = str(status.content)
        assert "— ctrl+c to cancel" in wide_text

        await pilot.resize_terminal(20, 24)
        await pilot.pause()

        narrow_text = str(status.content)
        assert "— ctrl+c to cancel" in narrow_text
        assert "⋯" in narrow_text

        # Clean up: cancel so the sleeping stub doesn't outlive the test.
        await pilot.press("ctrl+c")
        await app.workers.wait_for_complete()
        await pilot.pause()


async def test_save_failure_never_invokes_the_assistant(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("echo")  # would prove invocation happened, if it did
    directory = meeting.path.parent
    original_mode = directory.stat().st_mode

    directory.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        app = ChoomApp(tmp_workspace)
        async with app.run_test(size=(80, 24)) as pilot:
            screen = await open_edit(app, pilot)
            editor = screen.query_one("#editor", TextArea)
            buffer_before = editor.text
            expected = (
                buffer_before + "/ai anything"
                if buffer_before.endswith("\n")
                else buffer_before + "\n/ai anything"
            )

            await submit_editor_line(pilot, editor, "/ai anything")
            await pilot.pause()

            assert isinstance(app.screen, EditScreen)
            assert screen._request is None
            assert editor.read_only is False
            # the buffer holds exactly what was typed -- nothing else was inserted
            assert editor.text == expected
            status = screen.query_one(StatusBar)
            assert "⚠" in str(status.content)
    finally:
        directory.chmod(original_mode)
