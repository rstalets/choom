from __future__ import annotations

from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_reply_tasks
from choom.core.models import Workspace


def test_no_eligible_lines_returns_the_input_unchanged(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "just some prose\nand a second line"
    capture = capture_reply_tasks(
        tmp_workspace, text, source=meeting.path, source_id=meeting.id
    )
    assert capture.text is text  # identity, not equality
    assert capture.tasks == ()
    assert capture.warnings == ()


def test_each_eligible_line_is_replaced_by_its_mirror_others_untouched(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "here is a summary\n/task call Terry\nsome closing prose"
    capture = capture_reply_tasks(
        tmp_workspace, text, source=meeting.path, source_id=meeting.id
    )
    lines = capture.text.split("\n")
    assert len(lines) == 3
    assert lines[0] == "here is a summary"
    assert lines[2] == "some closing prose"
    assert lines[1] != "/task call Terry"
    assert len(capture.tasks) == 1
    task = capture.tasks[0]
    assert task.id is not None
    assert f"#{task.id}" in lines[1]
    assert capture.warnings == ()


def test_line_count_and_order_are_preserved(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "\n".join(
        [
            "intro",
            "/task first thing",
            "middle prose",
            "/task second thing",
            "outro",
        ]
    )
    capture = capture_reply_tasks(
        tmp_workspace, text, source=meeting.path, source_id=meeting.id
    )
    assert len(capture.text.split("\n")) == 5
    assert [t.text for t in capture.tasks] == ["first thing", "second thing"]


def test_tasks_are_returned_in_reply_order(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task alpha\n/task beta\n/task gamma"
    capture = capture_reply_tasks(
        tmp_workspace, text, source=meeting.path, source_id=meeting.id
    )
    assert [t.text for t in capture.tasks] == ["alpha", "beta", "gamma"]


def test_tags_and_type_suffix_reach_the_task(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task.followup call Terry #urgent #procurement"
    capture = capture_reply_tasks(
        tmp_workspace, text, source=meeting.path, source_id=meeting.id
    )
    assert len(capture.tasks) == 1
    task = capture.tasks[0]
    assert task.type == "followup"
    assert set(task.tags) == {"urgent", "procurement"}
    assert task.text == "call Terry"


def test_tasks_land_in_tasks_md(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task call Terry about the renewal"
    capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)
    saved = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert "call Terry about the renewal" in saved
