from __future__ import annotations

import pytest

from endpaper.core.errors import UsageError
from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace


def test_empty_slug_falls_back_to_untitled(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "!!! \U0001f389\U0001f389")
    assert meeting.path.name.endswith("-untitled.md")


def test_path_traversal_type_rejected_before_any_file_written(tmp_workspace: Workspace) -> None:
    with pytest.raises(UsageError):
        create_meeting(tmp_workspace, "hack", type="../evil")

    assert list(tmp_workspace.meetings_dir.glob("*.md")) == []


def test_empty_description_after_tag_stripping_is_usage_error(tmp_workspace: Workspace) -> None:
    with pytest.raises(UsageError):
        create_meeting(tmp_workspace, "#onlyatag")

    assert list(tmp_workspace.meetings_dir.glob("*.md")) == []
