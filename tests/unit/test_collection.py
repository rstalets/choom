from __future__ import annotations

from datetime import date

import pytest

from endpaper.core.errors import UsageError
from endpaper.core.meetings import MEETINGS
from endpaper.core.models import Document, Note, Workspace
from endpaper.core.notes import NOTES, create_note
from endpaper.core.text import new_document_id


def test_meetings_descriptor_values() -> None:
    assert MEETINGS.id_prefix == "m_"
    assert MEETINGS.create_dir == "meetings"
    assert MEETINGS.scan_dirs == ("meetings",)
    assert MEETINGS.reserved_types == frozenset()


def test_notes_descriptor_values() -> None:
    assert NOTES.id_prefix == "n_"
    assert NOTES.create_dir == "notes"
    assert NOTES.scan_dirs == ("notes", "notes/daily")
    assert NOTES.reserved_types == frozenset({"daily"})


def test_new_document_id_honours_its_prefix() -> None:
    document_id = new_document_id(date(2026, 7, 28), "n_")
    assert document_id.startswith("n_20260728_")
    assert len(document_id) == len("n_20260728_") + 8


def test_meeting_is_document() -> None:
    from endpaper.core.models import Meeting

    assert Meeting is Document


def test_note_is_document() -> None:
    assert Note is Document


def test_reserved_type_raises_before_any_directory_is_created(tmp_workspace: Workspace) -> None:
    with pytest.raises(UsageError):
        create_note(tmp_workspace, "hack", type="daily")

    assert list(tmp_workspace.notes_dir.glob("*.md")) == []
