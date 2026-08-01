from __future__ import annotations

from textual.widgets import Label, ListView, TextArea

from endpaper.core.links import inbound_links, outbound_links, relative_destination
from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.core.tasks import add_task
from endpaper.tui.app import EndpaperApp
from endpaper.tui.status_bar import StatusBar
from tests.helpers import open_edit, submit_editor_line, to_collection


def test_inbound_and_outbound_end_to_end(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\nSee [Q3 planning](#{meeting.id}) for context.\n", encoding="utf-8"
    )

    inbound = inbound_links(tmp_workspace, meeting.id)
    assert len(inbound) == 1
    assert inbound[0].source == note.path
    assert inbound[0].text == "Q3 planning"

    outbound = outbound_links(tmp_workspace, note.path)
    assert len(outbound) == 1
    link, status = outbound[0]
    assert link.target_id == meeting.id
    assert status == "stale"  # fragment-only, no path yet -- gains one on save


def test_id_mentioned_as_plain_prose_is_not_an_inbound_link(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    note.path.write_text(
        original + f"\nThe meeting id is {meeting.id} but this is not a link.\n",
        encoding="utf-8",
    )

    inbound = inbound_links(tmp_workspace, meeting.id)
    assert inbound == ()


def test_own_frontmatter_id_line_is_not_a_self_link(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")

    # The frontmatter's own `id: meeting_...` line necessarily contains the id as
    # a raw byte match (a substring-filter hit) but is not markdown link syntax.
    inbound = inbound_links(tmp_workspace, meeting.id)
    assert inbound == ()


def test_a_genuine_self_link_does_appear(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    original = meeting.path.read_text(encoding="utf-8")
    meeting.path.write_text(
        original + f"\nSee also [this meeting](#{meeting.id}) itself.\n", encoding="utf-8"
    )

    inbound = inbound_links(tmp_workspace, meeting.id)
    assert len(inbound) == 1


def test_empty_result_for_a_record_nothing_points_at(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "nothing points here")
    assert inbound_links(tmp_workspace, meeting.id) == ()


def test_inbound_finds_the_target_after_it_moves(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")

    original = note.path.read_text(encoding="utf-8")
    dest = relative_destination(note.path, meeting.path)
    note.path.write_text(
        original + f"\nSee [Q3 planning]({dest}#{meeting.id}).\n", encoding="utf-8"
    )

    # id still resolves the same regardless of what the path says
    inbound = inbound_links(tmp_workspace, meeting.id)
    assert len(inbound) == 1


def test_a_task_links_field_appears_as_an_inbound_link(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    task = add_task(tmp_workspace, "call Terry about the renewal")
    assert task.id is not None

    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    updated = text.replace(f"id:{task.id}", f"id:{task.id} links:{meeting.id}")
    tmp_workspace.tasks_file.write_text(updated, encoding="utf-8")

    inbound = inbound_links(tmp_workspace, meeting.id)
    assert len(inbound) == 1
    assert inbound[0].source == tmp_workspace.tasks_file
    assert inbound[0].in_tasks_field is True
    assert inbound[0].text == "call Terry about the renewal"


# --- US6: /link in the editor ---------------------------------------------------


async def test_link_one_match_inserts_a_correct_markdown_link(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    create_note(tmp_workspace, "vendor landscape")  # a note to open and edit

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot, collection="notes")
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/link q3 planning")

        expected_dest = relative_destination(screen.file.path, meeting.path)
        expected = f"[Q3 planning]({expected_dest}#{meeting.id})"
        assert editor.get_line(line_index).plain == expected

        status = screen.query_one(StatusBar)
        assert "⚠" not in str(status.content)


async def test_link_zero_matches_leaves_the_line_and_reports(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "vendor landscape")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot, collection="notes")
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/link nothing matches this at all")

        assert editor.get_line(line_index).plain == "/link nothing matches this at all"
        status = screen.query_one(StatusBar)
        assert "no record matches" in str(status.content)


async def test_link_several_matches_leaves_the_line_and_names_candidates(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning alpha")
    create_meeting(tmp_workspace, "Q3 planning beta")
    create_note(tmp_workspace, "vendor landscape")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot, collection="notes")
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/link q3 planning")

        assert editor.get_line(line_index).plain == "/link q3 planning"
        status = screen.query_one(StatusBar)
        text = str(status.content)
        assert "Q3 planning alpha" in text
        assert "Q3 planning beta" in text


async def test_link_partial_line_is_ordinary_text_not_a_command(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    before_bytes = note.path.read_bytes()

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot, collection="notes")
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "note: /link q3 planning")

        # Falls through to ordinary newline handling -- the typed text stays
        # exactly as typed, and no /link command ever fires (so no save
        # happens on its account and the file on disk is untouched).
        assert editor.get_line(line_index).plain == "note: /link q3 planning"

    assert note.path.read_bytes() == before_bytes


# --- US7: the preview Links section ---------------------------------------------


async def test_outbound_links_render_on_expanding_the_section(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    dest = relative_destination(note.path, meeting.path)
    text = note.path.read_text(encoding="utf-8")
    note.path.write_text(text + f"\n[Q3 planning]({dest}#{meeting.id})\n", encoding="utf-8")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "notes")
        await pilot.press("enter")
        await pilot.pause()

        links_section = app.screen.query_one("#links-section")
        assert links_section.display is False  # collapsed on open

        await pilot.press("l")
        await pilot.pause()

        assert links_section.display is True
        list_view = app.screen.query_one("#links-list", ListView)
        rendered = "\n".join(str(label.content) for label in list_view.query(Label))
        assert "Q3 planning" in rendered


async def test_inbound_links_appear_only_once_expanded(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    text = note.path.read_text(encoding="utf-8")
    note.path.write_text(text + f"\n[Q3 planning](#{meeting.id})\n", encoding="utf-8")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()

        # Before expansion: the section is not visible at all.
        links_section = app.screen.query_one("#links-section")
        assert links_section.display is False

        await pilot.press("l")
        await pilot.pause()

        list_view = app.screen.query_one("#links-list", ListView)
        rows = [row for row in list_view.children if hasattr(row, "link")]
        assert len(rows) == 1
        assert rows[0].direction == "in"
        assert rows[0].target is not None
        assert rows[0].target.title == "vendor landscape"


async def test_a_record_nothing_points_at_says_so(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "nothing points here")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("l")
        await pilot.pause()

        list_view = app.screen.query_one("#links-list", ListView)
        rendered = "\n".join(str(label.content) for label in list_view.query(Label))
        assert "nothing points at this record" in rendered
        assert "points at nothing" in rendered


async def test_opening_a_dead_link_reports_and_does_not_change_the_view(
    tmp_workspace: Workspace,
) -> None:
    note = create_note(tmp_workspace, "vendor landscape")
    text = note.path.read_text(encoding="utf-8")
    note.path.write_text(text + "\n[gone](#meeting_00000000_deadbeef)\n", encoding="utf-8")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "notes")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("l")
        await pilot.pause()

        from endpaper.tui.preview_screen import PreviewScreen

        assert isinstance(app.screen, PreviewScreen)
        list_view = app.screen.query_one("#links-list", ListView)
        target_index = next(
            i
            for i, row in enumerate(list_view.children)
            if hasattr(row, "link") and row.direction == "out"
        )
        # The list's initial index is None (before the first row), so landing
        # on `target_index` takes target_index + 1 presses.
        for _ in range(target_index + 1):
            await pilot.press("down")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        # Still on the same preview screen -- opening a dead link does not navigate.
        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.path == note.path
        status = app.screen.query_one(StatusBar)
        assert "does not resolve" in str(status.content)


async def test_escape_collapses_the_links_section_without_leaving_preview(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")

    from endpaper.tui.preview_screen import PreviewScreen

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("l")
        await pilot.pause()

        assert app.screen.query_one("#links-section").display is True

        await pilot.press("escape")
        await pilot.pause()

        # Collapsed, but still the same preview screen -- esc did not pop it.
        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.query_one("#links-section").display is False

        await pilot.press("escape")
        await pilot.pause()

        # A second esc, with the section already collapsed, goes back to the list.
        from endpaper.tui.list_screen import ListScreen

        assert isinstance(app.screen, ListScreen)


async def test_jk_move_within_the_links_section(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    dest = relative_destination(note.path, meeting.path)
    text = note.path.read_text(encoding="utf-8")
    note.path.write_text(text + f"\n[Q3]({dest}#{meeting.id})\n", encoding="utf-8")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "notes")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("l")
        await pilot.pause()

        list_view = app.screen.query_one("#links-list", ListView)
        assert list_view.index is None

        await pilot.press("j")
        await pilot.pause()
        assert list_view.index == 0

        await pilot.press("j")
        await pilot.pause()
        assert list_view.index == 1

        await pilot.press("k")
        await pilot.pause()
        assert list_view.index == 0
