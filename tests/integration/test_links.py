from __future__ import annotations

from textual.widgets import TextArea

from endpaper.core.links import inbound_links, outbound_links, relative_destination
from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.core.tasks import add_task
from endpaper.tui.app import EndpaperApp
from endpaper.tui.status_bar import StatusBar
from tests.helpers import open_edit, submit_editor_line


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
