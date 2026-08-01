from __future__ import annotations

from datetime import date

import pytest

from endpaper.core.errors import UsageError
from endpaper.core.meetings import MEETINGS, create_meeting
from endpaper.core.models import Workspace
from endpaper.core.notes import NOTES, create_note, open_daily_note
from endpaper.core.tasks import add_task
from endpaper.core.text import new_document_id


def test_new_document_id_honours_its_prefix() -> None:
    document_id = new_document_id(date(2026, 7, 28), "n_")
    assert document_id.startswith("n_20260728_")
    assert len(document_id) == len("n_20260728_") + 8


def test_reserved_type_raises_before_any_directory_is_created(tmp_workspace: Workspace) -> None:
    with pytest.raises(UsageError):
        create_note(tmp_workspace, "hack", type="daily")

    assert list(tmp_workspace.notes_dir.glob("*.md")) == []


# --- US1: ids name their collection in full ------------------------------------


def test_meetings_collection_uses_the_full_name_prefix() -> None:
    assert MEETINGS.id_prefix == "meeting_"


def test_notes_collection_uses_the_full_name_prefix() -> None:
    assert NOTES.id_prefix == "note_"


def test_new_meeting_carries_the_meeting_prefix(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning")
    assert meeting.id.startswith("meeting_")


def test_new_note_carries_the_note_prefix(tmp_workspace: Workspace) -> None:
    note = create_note(tmp_workspace, "vendor landscape")
    assert note.id.startswith("note_")


def test_new_daily_note_carries_the_note_prefix(tmp_workspace: Workspace) -> None:
    daily = open_daily_note(tmp_workspace)
    assert daily.document is not None
    assert daily.document.id.startswith("note_")


def test_new_task_carries_the_task_prefix(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "call Terry about the renewal")
    assert task.id is not None
    assert task.id.startswith("task_")
