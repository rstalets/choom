from __future__ import annotations

from endpaper.core.links import inbound_links, outbound_links, relative_destination
from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.core.tasks import add_task


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
