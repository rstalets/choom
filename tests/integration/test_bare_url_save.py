"""Integration tests for bare-URL-to-markdown-link conversion on save
(018-automatic-link-detection). `tests/unit/test_bare_url_format.py` and
`test_url_cursor_map.py` cover every guarantee decidable against a string or
against integers; this file covers the boundaries only an end-to-end save can
see: the two save paths converting and stamping in one write, the cursor and
status-line wiring in the TUI, and -- just as important -- every write choom
performs on the user's behalf (mirror sync, reconcile-on-open, `links heal`,
`links check`, `note new`/`meeting new`, a task's one-line description)
converting nothing at all (FR-015 through FR-019).
"""

from __future__ import annotations

from textual.widgets import TextArea

from choom.core.documents import _parse_document
from choom.core.editing import load_for_edit, save_buffer
from choom.core.links import check_links, find_links, heal_links, relative_destination
from choom.core.meetings import create_meeting
from choom.core.mirrors import find_mirrors, reconcile_on_open
from choom.core.models import Workspace
from choom.core.notes import create_note
from choom.core.tasks import add_task, load_tasks, set_task_body
from choom.tui.app import ChoomApp
from choom.tui.list_screen import ListScreen
from choom.tui.status_bar import StatusBar
from tests.conftest import tasks_file, write_tasks
from tests.helpers import open_edit, submit_editor_line, to_collection

# --- T015: the document save path -----------------------------------------------


def test_document_save_converts_and_stamps_in_one_write(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "vendor landscape")
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + "\nSee https://example.com/spec for details.\n", encoding="utf-8"
    )

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok
    assert len(result.conversions) == 1
    assert "[https://example.com/spec](https://example.com/spec)" in result.saved_text
    on_disk = note.path.read_text(encoding="utf-8")
    assert on_disk == result.saved_text  # exactly one write; saved_text matches it


def test_document_save_heals_a_stale_link_and_converts_a_url_without_disturbing_either(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    stale_line = f"Stale: [Q3](wrong/path.md#{meeting.id})\n"
    bare_url_line = "Bare: https://example.com/spec\n"
    note.path.write_text(original + "\n" + stale_line + bare_url_line, encoding="utf-8")

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok

    expected_dest = relative_destination(note.path, meeting.path)
    assert f"[Q3]({expected_dest}#{meeting.id})" in result.saved_text  # healed
    assert "wrong/path.md" not in result.saved_text
    assert "[https://example.com/spec](https://example.com/spec)" in result.saved_text  # converted
    assert len(result.conversions) == 1


# --- T026: whole-document guarantees survive a save -----------------------------


def test_whole_document_guarantees_survive_a_save(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    task = add_task(tmp_workspace, "call Terry")

    dest = relative_destination(note.path, meeting.path)
    task_dest = relative_destination(note.path, tmp_workspace.tasks_file)
    body = (
        f"\nSee [Q3 planning]({dest}#{meeting.id}) and https://example.com/spec.\n"
        "\n"
        f"- [ ] [call Terry]({task_dest}#{task.id})\n"
        "\n"
        "```\n"
        "curl https://api.example.com/v1\n"
        "```\n"
        "\n"
        "Also https://en.wikipedia.org/wiki/Foo_(bar) for background.\n"
    )
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(original + body, encoding="utf-8")
    before_newlines = (note.path.read_text(encoding="utf-8")).count("\n")

    file = load_for_edit(note.path)
    result = save_buffer(note.path, file.text, file, workspace=tmp_workspace)
    assert result.ok
    assert len(result.conversions) == 2  # the spec URL and the wikipedia URL

    on_disk = note.path.read_text(encoding="utf-8")
    assert on_disk.count("\n") == before_newlines

    doc, warning = _parse_document(on_disk, note.path)
    assert doc is not None
    assert warning is None
    assert doc.title == "vendor landscape"

    links = find_links(on_disk, source=note.path)
    # The record link and the mirror's own link -- neither converted URL
    # counts, since a URL-scheme destination is never a record link.
    assert len(links) == 2
    assert {link.target_id for link in links} == {meeting.id, task.id}

    mirrors = find_mirrors(on_disk, source=note.path)
    assert len(mirrors) == 1
    assert mirrors[0].task_id == task.id

    # A second save with no intervening edit reports zero conversions.
    file2 = load_for_edit(note.path)
    result2 = save_buffer(note.path, file2.text, file2, workspace=tmp_workspace)
    assert result2.ok
    assert result2.conversions == ()


# --- T017/T018: cursor mapping and the status line, in the running TUI ---------


async def test_cursor_does_not_land_inside_a_url_that_was_just_wrapped(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "Ref https://example.com/a and more")
        # Place the cursor inside the URL text the save is about to wrap.
        editor.cursor_location = (line_index, len("Ref https://exam"))

        await pilot.press("ctrl+o")
        await pilot.pause()

        row, column = editor.cursor_location
        assert row == line_index  # no conversion ever inserts a newline
        line = editor.get_line(row).plain
        # The cursor must not sit strictly inside either copy of the URL.
        first = line.index("https://example.com/a")
        second = line.index("https://example.com/a", first + 1)
        assert not (first < column < first + len("https://example.com/a"))
        assert not (second < column < second + len("https://example.com/a"))


async def test_status_line_reports_the_conversion_count_only_when_nonzero(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(
            pilot, editor, "See https://example.com/a and https://example.com/b"
        )
        await pilot.press("ctrl+o")
        await pilot.pause()

        status = app.screen.query_one(StatusBar)
        assert "formatted 2 links" in str(status.content)

        # A second save with nothing new to convert says nothing about it.
        await pilot.press("ctrl+o")
        await pilot.pause()
        status = app.screen.query_one(StatusBar)
        assert "formatted" not in str(status.content)


async def test_status_line_uses_singular_for_exactly_one_conversion(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "See https://example.com/a")
        await pilot.press("ctrl+o")
        await pilot.pause()

        status = app.screen.query_one(StatusBar)
        assert "formatted 1 link" in str(status.content)
        assert "formatted 1 links" not in str(status.content)


# --- T019/T029 (task body): converts on save, never on open --------------------


async def test_task_body_save_converts_a_bare_url(tmp_workspace: Workspace) -> None:
    add_task(tmp_workspace, "buy milk")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)

        editor = app.screen.query_one("#editor", TextArea)
        editor.text = "See https://example.com/a for the vendor quote."

        await pilot.press("ctrl+x")
        await pilot.pause()

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert "[https://example.com/a](https://example.com/a)" in text


async def test_opening_a_task_with_no_save_leaves_the_bare_url_untouched(
    tmp_workspace: Workspace,
) -> None:
    """The test that keeps T019's placement honest (research R9): if the
    conversion is ever moved inside `set_task_body` itself, it would also run
    on reconcile-on-open, and this is what would catch it."""
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  See https://example.com/a please.\n",
    )
    before = tasks_file(tmp_workspace).read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("e")  # opens the task-body editor; no save
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)

    assert tasks_file(tmp_workspace).read_bytes() == before


def test_reconcile_on_open_does_not_convert_a_bare_url_in_a_task_body(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")
    task = load_tasks(tmp_workspace)[0][0]
    body = "See https://example.com/a please."

    set_task_body(tmp_workspace, task.id, body)
    before = tasks_file(tmp_workspace).read_bytes()

    report = reconcile_on_open(tmp_workspace, body, source=tasks_file(tmp_workspace))
    assert report.text == body  # unchanged -- format_bare_urls is never called here
    assert tasks_file(tmp_workspace).read_bytes() == before


# --- T029 (document): opening never converts ------------------------------------


def test_reconcile_on_open_does_not_convert_a_bare_url_in_a_document(
    tmp_workspace: Workspace,
) -> None:
    note = create_note(tmp_workspace, "vendor landscape")
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(original + "\nSee https://example.com/a please.\n", encoding="utf-8")
    before = note.path.read_bytes()

    file = load_for_edit(note.path)
    report = reconcile_on_open(tmp_workspace, file.text, source=note.path)
    assert report.text is file.text  # identity -- nothing needed correcting
    assert note.path.read_bytes() == before


async def test_opening_a_document_with_no_save_leaves_the_bare_url_untouched(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    original = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(
        original + "\nAssistant wrote https://example.com/untouched here.\n", encoding="utf-8"
    )
    before = meeting.path.read_bytes()

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")  # preview only, no editor, no save
        await pilot.pause()

    assert meeting.path.read_bytes() == before


# --- T030: `choom links heal`/`check` convert nothing ---------------------------


def test_heal_check_convert_zero_bare_urls(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "vendor landscape")
    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + "\nSee https://example.com/a and https://example.com/b.\n",
        encoding="utf-8",
    )
    before = note.path.read_bytes()

    check_reports = check_links(tmp_workspace)
    assert check_reports == ()  # a URL-scheme destination is never a record link
    assert note.path.read_bytes() == before  # check writes nothing, ever

    heal_reports = heal_links(tmp_workspace)
    assert heal_reports == ()
    assert note.path.read_bytes() == before  # nothing stale, so nothing written


# --- T031: `check_links` reports an identical set across a workspace-wide save --


def test_links_unchanged_reports_an_identical_set_before_and_after_every_save(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    dead_link = "Dead: [gone](#meeting_00000000_deadbeef)\n"
    bare_url = "Bare: https://example.com/spec\n"
    note.path.write_text(original + "\n" + dead_link + bare_url, encoding="utf-8")

    before = check_links(tmp_workspace)

    for path in (meeting.path, note.path):
        file = load_for_edit(path)
        result = save_buffer(path, file.text, file, workspace=tmp_workspace)
        assert result.ok

    after = check_links(tmp_workspace)
    assert before == after  # SC-005 -- this feature adds no link problem, resolves none


# --- T032: a task's one-line description never converts, on either surface -----


def test_task_description_with_a_bare_url_is_not_converted_via_add_task(
    tmp_workspace: Workspace,
) -> None:
    """A `/task` capture turns the description into the *link text* of a
    mirror; a link nested inside link text is not valid CommonMark, so the
    TUI physically cannot honour a converted description and the CLI (which
    `choom task add` calls into via this same core function) must not
    either (FR-018)."""
    task = add_task(tmp_workspace, "see https://example.com/a for the quote")
    assert task.text == "see https://example.com/a for the quote"
    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert "[https://example.com/a](https://example.com/a)" not in text


async def test_task_description_with_a_bare_url_is_not_converted_via_task_command(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning", type="standup")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        screen = await open_edit(app, pilot)
        editor = screen.query_one("#editor", TextArea)

        await submit_editor_line(pilot, editor, "/task see https://example.com/a for the quote")

        tasks, _warnings = load_tasks(tmp_workspace)
        assert len(tasks) == 1
        assert tasks[0].text == "see https://example.com/a for the quote"

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert "[https://example.com/a](https://example.com/a)" not in text


# --- T033: `note new`/`meeting new` convert nothing -----------------------------


def test_create_note_and_meeting_convert_nothing(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "notes on https://example.com/a")
    meeting = create_meeting(tmp_workspace, "kickoff for https://example.com/b")

    for doc in (note, meeting):
        text = doc.path.read_text(encoding="utf-8")
        assert "](http" not in text  # nothing was ever wrapped -- no body exists to convert
