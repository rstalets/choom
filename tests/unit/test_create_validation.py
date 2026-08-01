from __future__ import annotations

import pytest

from choom.core.errors import UsageError
from choom.core.meetings import create_meeting
from choom.core.models import Workspace


def test_empty_slug_falls_back_to_untitled(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "!!! \U0001f389\U0001f389")
    assert meeting.path.name.endswith("-untitled.md")


def test_path_traversal_type_rejected_before_any_file_written(tmp_workspace: Workspace) -> None:
    with pytest.raises(UsageError):
        create_meeting(tmp_workspace, "hack", type="../evil")

    assert list(tmp_workspace.meetings_dir.glob("*.md")) == []


def test_empty_description_after_tag_stripping_is_usage_error(tmp_workspace: Workspace) -> None:
    # NOT a contract-layer duplicate: this exercises core/documents.py's
    # create_document (shared by create_meeting/create_note). The contract-level
    # "#onlytags" exit-2 test only reaches core/tasks.py's separate, differently
    # numbered raise of the same message -- a different code path. Dropping this
    # would leave documents.py's empty-description branch with no test.
    with pytest.raises(UsageError):
        create_meeting(tmp_workspace, "#onlyatag")

    assert list(tmp_workspace.meetings_dir.glob("*.md")) == []
