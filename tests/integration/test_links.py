from __future__ import annotations

from textual.widgets import Label, ListView, TextArea

from choom.core.links import (
    check_links,
    heal_links,
    inbound_links,
    outbound_for_target,
    outbound_links,
    relative_destination,
    resolve_href,
    resolve_id,
)
from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.core.notes import create_note
from choom.core.tasks import add_task
from choom.tui.app import ChoomApp
from choom.tui.links_pane import LinkRow
from choom.tui.list_screen import DocumentRow
from choom.tui.status_bar import StatusBar
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

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot, collection="notes")
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/link q3 planning")

        expected_dest = relative_destination(screen.target.display_path, meeting.path)
        expected = f"[Q3 planning]({expected_dest}#{meeting.id})"
        assert editor.get_line(line_index).plain == expected

        status = app.screen.query_one(StatusBar)
        assert "⚠" not in str(status.content)


async def test_link_zero_matches_leaves_the_line_and_reports(tmp_workspace: Workspace) -> None:
    create_note(tmp_workspace, "vendor landscape")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot, collection="notes")
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/link nothing matches this at all")

        assert editor.get_line(line_index).plain == "/link nothing matches this at all"
        status = app.screen.query_one(StatusBar)
        assert "no record matches" in str(status.content)


async def test_link_several_matches_leaves_the_line_and_names_candidates(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning alpha")
    create_meeting(tmp_workspace, "Q3 planning beta")
    create_note(tmp_workspace, "vendor landscape")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        screen = await open_edit(app, pilot, collection="notes")
        editor = screen.query_one("#editor", TextArea)

        line_index = await submit_editor_line(pilot, editor, "/link q3 planning")

        assert editor.get_line(line_index).plain == "/link q3 planning"
        status = app.screen.query_one(StatusBar)
        text = str(status.content)
        assert "Q3 planning alpha" in text
        assert "Q3 planning beta" in text


async def test_link_partial_line_is_ordinary_text_not_a_command(
    tmp_workspace: Workspace,
) -> None:
    create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    before_bytes = note.path.read_bytes()

    app = ChoomApp(tmp_workspace)
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

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "notes")
        await pilot.press("enter")
        await pilot.pause()

        links_section = app.screen.query_one("#links-section")
        assert links_section.display is False  # collapsed on open

        await pilot.press("b")
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

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()

        # Before expansion: the section is not visible at all.
        links_section = app.screen.query_one("#links-section")
        assert links_section.display is False

        await pilot.press("b")
        await pilot.pause()

        list_view = app.screen.query_one("#links-list", ListView)
        rows = [row for row in list_view.children if hasattr(row, "link")]
        assert len(rows) == 1
        assert rows[0].direction == "in"
        assert rows[0].target is not None
        assert rows[0].target.title == "vendor landscape"


async def test_a_record_nothing_points_at_says_so(tmp_workspace: Workspace) -> None:
    create_meeting(tmp_workspace, "nothing points here")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("b")
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

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "notes")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()

        from choom.tui.preview_screen import PreviewScreen

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

    from choom.tui.preview_screen import PreviewScreen

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("b")
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
        from choom.tui.list_screen import ListScreen

        assert isinstance(app.screen, ListScreen)


async def test_jk_move_within_the_links_section(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    dest = relative_destination(note.path, meeting.path)
    text = note.path.read_text(encoding="utf-8")
    note.path.write_text(text + f"\n[Q3]({dest}#{meeting.id})\n", encoding="utf-8")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 30)) as pilot:
        await to_collection(app, pilot, "notes")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("b")
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


# --- markdown links inside tasks.md (007's task bodies meet 008's links) --------


def _task_with_body_link(workspace: Workspace, meeting_id: str) -> str:
    """A task whose indented body holds an ordinary fragment-only markdown link."""
    task = add_task(workspace, "call Terry", type="followup")
    path = workspace.tasks_file
    path.write_text(
        path.read_text(encoding="utf-8").rstrip("\n")
        + f"\n\n  See [Q3 planning](#{meeting_id}) for context.\n",
        encoding="utf-8",
    )
    assert task.id is not None
    return task.id


def test_a_link_in_a_task_body_is_an_inbound_link(tmp_workspace: Workspace) -> None:
    """tasks.md carries `links:` field ids *and* ordinary markdown links in a
    task's text or indented body. Before task bodies existed (007) the second
    kind could not occur, so the scan treated tasks.md as metadata-only and a
    body link was invisible to every direction."""
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    _task_with_body_link(tmp_workspace, meeting.id)

    inbound = inbound_links(tmp_workspace, meeting.id)
    assert len(inbound) == 1
    assert inbound[0].source == tmp_workspace.tasks_file
    assert inbound[0].text == "Q3 planning"


def test_a_link_in_a_task_body_is_reported_stale_and_then_healed(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    _task_with_body_link(tmp_workspace, meeting.id)

    stale = check_links(tmp_workspace)
    assert [r.status for r in stale] == ["stale"]
    assert stale[0].file == tmp_workspace.tasks_file
    assert stale[0].old_path is None

    heal_links(tmp_workspace)
    body = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert f"]({relative_destination(tmp_workspace.tasks_file, meeting.path)}#{meeting.id})" in body
    assert check_links(tmp_workspace) == ()


def test_a_body_link_belongs_to_the_task_whose_body_it_sits_in(
    tmp_workspace: Workspace,
) -> None:
    """Two tasks, one body link: `--direction out` must attribute it to the task
    that owns the line, not to every task in the file."""
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    owner_id = _task_with_body_link(tmp_workspace, meeting.id)
    other = add_task(tmp_workspace, "unrelated errand")

    owner_target, _warnings = resolve_id(tmp_workspace, owner_id)
    assert owner_target is not None
    assert [
        link.target_id for link, _status in outbound_for_target(tmp_workspace, owner_target)
    ] == [meeting.id]

    assert other.id is not None
    other_target, _warnings = resolve_id(tmp_workspace, other.id)
    assert other_target is not None
    assert outbound_for_target(tmp_workspace, other_target) == ()


def test_a_task_body_link_does_not_disturb_the_links_field(tmp_workspace: Workspace) -> None:
    """A task may carry both kinds at once; neither hides the other."""
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    task_id = _task_with_body_link(tmp_workspace, meeting.id)

    path = tmp_workspace.tasks_file
    path.write_text(
        path.read_text(encoding="utf-8").replace("type:followup", f"type:followup links:{note.id}"),
        encoding="utf-8",
    )

    target, _warnings = resolve_id(tmp_workspace, task_id)
    assert target is not None
    found = {link.target_id for link, _status in outbound_for_target(tmp_workspace, target)}
    assert found == {meeting.id, note.id}


# --- clicking a rendered link (Markdown.LinkClicked) ---------------------------


def test_a_clicked_workspace_link_resolves_to_its_record(tmp_workspace: Workspace) -> None:
    """`Markdown` sends every href to `app.open_url` unless told otherwise, which
    handed a workspace-relative path and an `#id` fragment to a web browser. A
    destination choom owns must resolve to the record instead."""
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    dest = relative_destination(note.path, meeting.path)

    for href in (f"#{meeting.id}", f"{dest}#{meeting.id}", dest):
        target = resolve_href(tmp_workspace, note.path, href)
        assert target is not None, href
        assert target.id == meeting.id


def test_an_external_url_is_not_claimed(tmp_workspace: Workspace) -> None:
    """Anything with a scheme is a browser's job; returning None is how the
    caller knows to fall through rather than swallow the click."""
    note = create_note(tmp_workspace, "vendor landscape")
    for href in ("https://example.com", "http://example.com/x#frag", "mailto:a@b.c"):
        assert resolve_href(tmp_workspace, note.path, href) is None


def test_an_unresolvable_or_empty_destination_is_not_claimed(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "vendor landscape")
    assert resolve_href(tmp_workspace, note.path, "") is None
    assert resolve_href(tmp_workspace, note.path, "#meeting_does_not_exist") is None
    assert resolve_href(tmp_workspace, note.path, "no/such/file.md") is None


# --- the links pane in the list screen's preview pane ---------------------------


async def test_backlinks_pane_works_in_the_list_preview(tmp_workspace: Workspace) -> None:
    """The links pane must exist on the list screen too, not only in the
    full-screen preview: a later feature makes the preview pane an editing pane
    and de-prioritises full screen, so this is the surface that matters."""
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    note = create_note(tmp_workspace, "vendor landscape")
    note.path.write_text(
        note.path.read_text(encoding="utf-8") + f"\nSee [Q3 planning](#{meeting.id}).\n",
        encoding="utf-8",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test() as pilot:
        await to_collection(app, pilot, "meetings")
        section = app.screen.query_one("#preview-links-section")
        assert section.display is False

        await pilot.press("b")
        await pilot.pause()
        assert section.display is True

        rows = app.screen.query_one("#preview-links-list", ListView)
        rendered = "\n".join(str(label.content) for label in rows.query(Label))
        assert "Points at" in rendered
        assert "Points here" in rendered
        assert "vendor landscape" in rendered

        await pilot.press("b")
        await pilot.pause()
        assert section.display is False


async def test_escaping_a_linked_doc_returns_to_the_record_you_left(
    tmp_workspace: Workspace,
) -> None:
    """`esc` means "back" everywhere in this app. Following a link out of the
    preview pane and escaping must return to the record you were reading, not
    strand the list on the one you visited.

    Both records are notes on purpose: the bug only shows when the link target
    is a row in the *same* list, because a pending id that matches nothing falls
    back to the first row and accidentally looks correct.
    """
    target_note = create_note(tmp_workspace, "vendor landscape")
    source_note = create_note(tmp_workspace, "renewal thinking")
    source_note.path.write_text(
        source_note.path.read_text(encoding="utf-8")
        + f"\nSee [vendor landscape](#{target_note.id}).\n",
        encoding="utf-8",
    )

    app = ChoomApp(tmp_workspace)
    async with app.run_test() as pilot:
        await to_collection(app, pilot, "notes")
        list_view = app.screen.query_one("#meeting-list", ListView)
        index_of = {
            row.document.id: i
            for i, row in enumerate(list_view.children)
            if isinstance(row, DocumentRow)
        }
        list_view.index = index_of[source_note.id]
        await pilot.pause()

        await pilot.press("b")
        await pilot.pause()
        links = app.screen.query_one("#preview-links-list", ListView)
        rows = [child for child in links.children if isinstance(child, LinkRow)]
        outbound = next(row for row in rows if row.direction == "out")
        links.index = list(links.children).index(outbound)
        await pilot.press("enter")
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        list_view = app.screen.query_one("#meeting-list", ListView)
        back_on = list_view.highlighted_child
        assert isinstance(back_on, DocumentRow)
        assert back_on.document.id == source_note.id
