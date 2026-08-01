from __future__ import annotations

import pytest

from endpaper.core.errors import UsageError
from endpaper.core.meetings import create_meeting
from endpaper.core.mirrors import capture_task
from endpaper.core.models import Workspace
from endpaper.core.tasks import load_tasks


def test_empty_description_raises_before_anything_is_written(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before = tmp_workspace.tasks_file.read_text(encoding="utf-8")

    with pytest.raises(UsageError):
        capture_task(
            tmp_workspace,
            "   ",
            source=meeting.path,
            source_id=meeting.id,
        )

    assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == before


def test_description_that_is_only_a_tag_raises_and_writes_nothing(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before = tmp_workspace.tasks_file.read_text(encoding="utf-8")

    with pytest.raises(UsageError):
        capture_task(
            tmp_workspace,
            "#onlyatag",
            source=meeting.path,
            source_id=meeting.id,
        )

    assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == before


def test_rejected_type_token_raises_and_writes_nothing(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before = tmp_workspace.tasks_file.read_text(encoding="utf-8")

    with pytest.raises(UsageError):
        capture_task(
            tmp_workspace,
            "call Terry",
            type="not a valid type!",
            source=meeting.path,
            source_id=meeting.id,
        )

    assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == before


def test_rejected_tag_token_raises_and_writes_nothing(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    before = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    # Inline #tag tokens can only ever contain characters the tag regex itself
    # accepts, so the way to reach add_task's own token validation is a tag
    # that is otherwise well-formed but longer than the 40-character limit.
    overlong_tag = "a" * 45

    with pytest.raises(UsageError):
        capture_task(
            tmp_workspace,
            f"call Terry #{overlong_tag}",
            source=meeting.path,
            source_id=meeting.id,
        )

    assert tmp_workspace.tasks_file.read_text(encoding="utf-8") == before


def test_a_task_is_created_with_exactly_one_link(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    task, line = capture_task(
        tmp_workspace,
        "call Terry about the renewal #procurement",
        type="followup",
        source=meeting.path,
        source_id=meeting.id,
    )

    assert task.links == (meeting.id,)
    assert task.text == "call Terry about the renewal"
    assert task.tags == ("procurement",)
    assert f"#{task.id}" in line
    assert line.startswith("- [ ] [")

    tasks, _warnings = load_tasks(tmp_workspace)
    assert [t.id for t in tasks] == [task.id]
