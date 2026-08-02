from __future__ import annotations

import stat
from collections.abc import Callable
from pathlib import Path

import pytest
from textual.widgets import TextArea

from choom.core.assistants import PROFILES, AssistantRequest
from choom.core.config import set_assistant, set_launch_offer_made
from choom.core.meetings import create_meeting
from choom.core.models import AssistantReply, Workspace
from choom.core.tasks import load_tasks
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import _PLACEHOLDER, EditScreen
from choom.tui.status_bar import EDIT_HELP, StatusBar
from tests.conftest import STUB_REPLY_TEXT
from tests.helpers import list_view, open_edit, submit_editor_line, task_rows, to_collection


@pytest.fixture(autouse=True)
def _offer_already_made(tmp_workspace: Workspace) -> None:
    """Record the discovery offer as already made, for every test in this module.

    These tests are about `/ai`, and they reach it by putting exactly one assistant
    on PATH (`stub_assistant`, or an emptied PATH plus an explicit setting). That is
    precisely the condition 013-assistant-discovery-file's launch offer fires on, so
    without this the app opens onto a `ConfirmDialog` and every query for a widget on
    the list underneath fails with `NoMatches`. First-run discovery has its own
    coverage in `test_launch_offer.py`; here it is noise.

    Module-scoped rather than in `tmp_workspace` itself: the unit tests for the config
    writer and for `should_offer_discovery` need a workspace that has *not* been
    through this, and pre-recording it globally would quietly gut them.
    """
    set_launch_offer_made(tmp_workspace, True)


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

        status = app.screen.query_one(StatusBar)
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

        status = app.screen.query_one(StatusBar)
        status_text = str(status.content)
        assert "2 tasks captured" in status_text
        assert "⚠" not in status_text

        # Still the same screen, editor focused -- no navigation happened.
        assert isinstance(app.screen, EditScreen)
        assert app.screen.pane is screen
        assert editor.has_focus


async def test_unwritable_tasks_md_still_lands_the_whole_reply(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    """T031: a failed capture never costs the reply (US5). With tasks.md
    unwritable, every line of the reply still reaches the buffer -- the task
    lines exactly as the assistant wrote them, since none could be captured
    -- and the status bar names the failure."""
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("reply_with_tasks")

    root = tmp_workspace.root
    original_mode = root.stat().st_mode
    root.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        app = ChoomApp(tmp_workspace)
        async with app.run_test(size=(80, 24)) as pilot:
            screen = await open_edit(app, pilot)
            editor = screen.query_one("#editor", TextArea)

            line_index = await submit_editor_line(pilot, editor, "/ai summarise and track")
            await app.workers.wait_for_complete()
            await pilot.pause()

            expected_lines = [
                "Here is a summary of the discussion.",
                "/task call Terry about the renewal",
                "One more thing worth tracking down the line.",
                "/task.followup review the budget numbers #finance",
            ]
            actual_lines = [
                editor.get_line(line_index + offset).plain for offset in range(len(expected_lines))
            ]
            assert actual_lines == expected_lines  # no line lost, none captured

            status = app.screen.query_one(StatusBar)
            status_text = str(status.content)
            assert "⚠" in status_text
            assert "could not write" in status_text
    finally:
        root.chmod(original_mode)


async def test_cancelled_request_with_task_lines_pending_creates_no_task(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    """T032 (FR-019, research R5): a request cancelled before the reply is
    used must create nothing -- the capture runs only for a reply that will
    actually be inserted."""
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("sleep")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai anything")
        assert screen._request is not None

        await pilot.press("ctrl+c")
        await app.workers.wait_for_complete()
        await pilot.pause()

        assert editor.get_line(line_index).plain == "/ai anything"
        tasks, _warnings = load_tasks(tmp_workspace)
        assert tasks == []


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


async def test_reply_captured_tasks_reconcile_like_any_other_task(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    """Extends the US1 path (T026): a reply-captured task is not a special
    case for reconciliation -- completing it from the tasks list ticks its
    note's checklist, and ticking the note's checklist and saving completes
    it, exactly as 009 already established for a typed capture."""
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("reply_with_tasks")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/ai summarise and track")
        await app.workers.wait_for_complete()
        await pilot.pause()

        await pilot.press("ctrl+x")  # save & close -- mirrors land on disk
        await pilot.pause()
        assert not isinstance(app.screen, EditScreen)
        await pilot.press("escape")  # back from the preview to the list
        await pilot.pause()

        tasks, _warnings = load_tasks(tmp_workspace)
        assert len(tasks) == 2
        first_id, second_id = tasks[0].id, tasks[1].id
        assert first_id is not None
        assert second_id is not None

        # Complete the first task from the tasks list -- the note's mirror ticks.
        await to_collection(app, pilot, "tasks")
        await pilot.pause()
        rows = task_rows(app)
        row_index = next(i for i, row in enumerate(rows) if row.record.id == first_id)
        list_view(app).index = row_index
        await pilot.press("space")
        await pilot.pause()

        note_text = meeting.path.read_text(encoding="utf-8")
        assert "- [x] [call Terry about the renewal]" in note_text
        assert f"#{first_id})" in note_text

        # Re-open the note, tick the second mirror by hand, and save --
        # the task completes.
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)
        marker = "- [ ] [review the budget numbers"
        assert marker in editor.text
        editor.text = editor.text.replace(marker, marker.replace("[ ]", "[x]"), 1)
        await pilot.press("ctrl+o")
        await pilot.pause()

        tasks_after, _warnings = load_tasks(tmp_workspace)
        assert next(t for t in tasks_after if t.id == second_id).done is True
        assert next(t for t in tasks_after if t.id == first_id).done is True


async def test_second_save_after_capture_writes_no_spurious_task_state(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    """T027: proves the mirror baseline seeded at capture time (T013, FR-023)
    -- without it, a freshly inserted mirror is indistinguishable at the next
    save from a state change the user just made."""
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("reply_with_tasks")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/ai summarise and track")
        await app.workers.wait_for_complete()
        await pilot.pause()

        tasks, _warnings = load_tasks(tmp_workspace)
        assert len(tasks) == 2
        for task in tasks:
            assert task.id is not None
            assert screen._mirror_baseline[task.id] is False

        tasks_md_after_capture = tmp_workspace.tasks_file.read_text(encoding="utf-8")

        await pilot.press("ctrl+o")
        await pilot.pause()
        await pilot.press("ctrl+o")  # a second save straight after
        await pilot.pause()

        assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == tasks_md_after_capture
        tasks_after, _warnings = load_tasks(tmp_workspace)
        assert all(t.done is False for t in tasks_after)


async def test_reply_explaining_the_syntax_captures_nothing(
    tmp_workspace: Workspace, stub_assistant: Callable[[str], None]
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")
    stub_assistant("reply_explaining")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/ai how do I make a task")
        await app.workers.wait_for_complete()
        await pilot.pause()

        expected_lines = [
            "You can ask choom to capture a task by writing a line like this:",
            "```",
            "/task call Terry about the renewal",
            "```",
            "Just mention /task on its own line and choom does the rest.",
        ]
        actual_lines = [
            editor.get_line(line_index + offset).plain for offset in range(len(expected_lines))
        ]
        assert actual_lines == expected_lines

        # init_workspace already creates an empty tasks.md -- unchanged means
        # still empty, not merely present.
        assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == ""

        status = app.screen.query_one(StatusBar)
        status_text = str(status.content)
        assert "captured" not in status_text
        assert EDIT_HELP in status_text


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

        status = app.screen.query_one(StatusBar)
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
        status = app.screen.query_one(StatusBar)
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
        status = app.screen.query_one(StatusBar)
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
        status = app.screen.query_one(StatusBar)
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
        status = app.screen.query_one(StatusBar)
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
        status = app.screen.query_one(StatusBar)
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
        status = app.screen.query_one(StatusBar)
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
        status = app.screen.query_one(StatusBar)
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
            status = app.screen.query_one(StatusBar)
            assert "⚠" in str(status.content)
    finally:
        directory.chmod(original_mode)


async def test_a_document_deleted_mid_request_lands_the_reply_and_says_why(
    tmp_workspace: Workspace,
) -> None:
    """The spec's edge case: the source document is deleted or renamed between the
    request going out and the reply arriving, so there is no id to link a capture
    from. The reply must still land in full, and a reply that wanted tasks must say
    why it has none (FR-017, FR-018).

    The reply is delivered through `_finish_request` directly rather than through a
    stub, because the window between "document deleted" and "reply arrives" is a race
    no stub can hit deterministically -- the stub prints and exits before the test
    could unlink anything.
    """
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        # Stand the buffer where `_start_ai_request` leaves it: the submitted line
        # replaced by the placeholder the reply will overwrite.
        editor.text = editor.text.rstrip("\n") + "\n" + _PLACEHOLDER
        line_index = editor.document.line_count - 1
        await pilot.pause()

        # The document is gone by the time the reply comes back.
        screen.target.display_path.unlink()

        request = AssistantRequest(PROFILES[0], None, "")
        screen._request = request
        reply_text = "Here is the summary.\n/task call Terry about the renewal"
        screen._finish_request(
            request,
            line_index,
            "/ai summarise and track",
            AssistantReply(ok=True, text=reply_text, message="", cancelled=False),
        )
        await pilot.pause()

        # Every line of the reply reached the buffer, the task line as written.
        assert editor.get_line(line_index).plain == "Here is the summary."
        assert editor.get_line(line_index + 1).plain == "/task call Terry about the renewal"

        tasks, _ = load_tasks(tmp_workspace)
        assert tasks == []

        status = str(app.screen.query_one(StatusBar).content)
        assert "could not identify this document" in status
        assert "⚠" in status
