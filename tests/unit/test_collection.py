from __future__ import annotations

from datetime import date

import pytest

from endpaper.core.errors import UsageError
from endpaper.core.models import Workspace
from endpaper.core.notes import create_note
from endpaper.core.text import new_document_id


def test_new_document_id_honours_its_prefix() -> None:
    document_id = new_document_id(date(2026, 7, 28), "n_")
    assert document_id.startswith("n_20260728_")
    assert len(document_id) == len("n_20260728_") + 8


def test_reserved_type_raises_before_any_directory_is_created(tmp_workspace: Workspace) -> None:
    with pytest.raises(UsageError):
        create_note(tmp_workspace, "hack", type="daily")

    assert list(tmp_workspace.notes_dir.glob("*.md")) == []
