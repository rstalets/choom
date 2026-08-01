from __future__ import annotations

from choom.core.models import Workspace
from choom.core.tasks import add_task


def test_task_added_with_links_renders_the_field_between_tags_and_created(
    tmp_workspace: Workspace,
) -> None:
    task = add_task(
        tmp_workspace,
        "call Terry about the renewal #procurement",
        type="followup",
        links=("meeting_20260728_9f3c1a04",),
    )
    assert task.links == ("meeting_20260728_9f3c1a04",)

    line = tmp_workspace.tasks_file.read_text(encoding="utf-8").splitlines()[-1]
    assert line == (
        "- [ ] call Terry about the renewal <!-- id:"
        f"{task.id} type:followup tags:procurement "
        "links:meeting_20260728_9f3c1a04 created:"
        f"{task.created.isoformat()} -->"
    )


def test_task_added_without_links_is_byte_identical_in_shape(tmp_workspace: Workspace) -> None:
    task = add_task(tmp_workspace, "buy milk")
    assert task.links == ()

    line = tmp_workspace.tasks_file.read_text(encoding="utf-8").splitlines()[-1]
    assert "links:" not in line
    assert line == f"- [ ] buy milk <!-- id:{task.id} created:{task.created.isoformat()} -->"


def test_multiple_links_are_recorded_in_order(tmp_workspace: Workspace) -> None:
    task = add_task(
        tmp_workspace,
        "chase the SOW",
        links=("meeting_1", "note_2"),
    )
    assert task.links == ("meeting_1", "note_2")
