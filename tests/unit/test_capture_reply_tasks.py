from __future__ import annotations

import re
import stat

from choom.core.meetings import create_meeting
from choom.core.mirrors import capture_reply_tasks, capture_task
from choom.core.models import Workspace

_ID_OR_CREATED = re.compile(r"(id|created):\S+")


def test_no_eligible_lines_returns_the_input_unchanged(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "just some prose\nand a second line"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)
    assert capture.text is text  # identity, not equality
    assert capture.tasks == ()
    assert capture.warnings == ()


def test_each_eligible_line_is_replaced_by_its_mirror_others_untouched(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "here is a summary\n/task call Terry\nsome closing prose"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)
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
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)
    assert len(capture.text.split("\n")) == 5
    assert [t.text for t in capture.tasks] == ["first thing", "second thing"]


def test_tasks_are_returned_in_reply_order(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task alpha\n/task beta\n/task gamma"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)
    assert [t.text for t in capture.tasks] == ["alpha", "beta", "gamma"]


def test_tags_and_type_suffix_reach_the_task(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task.followup call Terry #urgent #procurement"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)
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


# --- T025: a reply-captured task is indistinguishable from a typed one (US4) ---


def test_a_reply_captured_task_matches_a_typed_capture_of_the_same_words(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")

    typed_task, _typed_line = capture_task(
        tmp_workspace,
        "call Terry about the renewal #urgent",
        type="followup",
        source=meeting.path,
        source_id=meeting.id,
    )
    capture = capture_reply_tasks(
        tmp_workspace,
        "/task.followup call Terry about the renewal #urgent",
        source=meeting.path,
        source_id=meeting.id,
    )
    reply_task = capture.tasks[0]

    assert reply_task.id != typed_task.id  # two distinct tasks
    assert reply_task.text == typed_task.text
    assert reply_task.type == typed_task.type
    assert reply_task.tags == typed_task.tags
    assert reply_task.links == typed_task.links

    # The rendered tasks.md lines differ only in id and created timestamp.
    saved_lines = tmp_workspace.tasks_file.read_text(encoding="utf-8").splitlines()
    assert len(saved_lines) == 2
    normalised = [_ID_OR_CREATED.sub(r"\1:X", line) for line in saved_lines]
    assert normalised[0] == normalised[1]


# --- T028: partial and total failure never cost a line (US5) -------------------


def test_one_failure_among_several_still_captures_the_rest_in_order(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task first thing\n/task #onlytags\n/task third thing"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)

    lines = capture.text.split("\n")
    assert len(lines) == 3  # no line ever lost
    assert lines[1] == "/task #onlytags"  # the failing line survives as text
    assert lines[0] != "/task first thing"  # the other two were captured
    assert lines[2] != "/task third thing"

    assert [t.text for t in capture.tasks] == ["first thing", "third thing"]
    assert len(capture.warnings) == 1
    assert capture.warnings[0].reason == "reply_capture_failed"
    assert capture.warnings[0].path == tmp_workspace.tasks_file


def test_every_capture_failing_leaves_the_text_identical_and_warns_per_line(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task #tag1\n/task #tag2"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)

    assert len(capture.text.split("\n")) == 2  # no line ever lost
    assert capture.text == text
    assert capture.tasks == ()
    assert len(capture.warnings) == 2


def test_bare_task_with_no_description_lands_as_text_with_a_warning(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "before\n/task\nafter"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)

    lines = capture.text.split("\n")
    assert len(lines) == 3
    assert lines == ["before", "/task", "after"]
    assert capture.tasks == ()
    assert len(capture.warnings) == 1


def test_a_description_that_is_only_tags_fails_loudly_rather_than_dropping_them(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "/task #urgent #procurement"
    capture = capture_reply_tasks(tmp_workspace, text, source=meeting.path, source_id=meeting.id)

    assert capture.text == text  # the tags are not silently dropped
    assert capture.tasks == ()
    assert len(capture.warnings) == 1
    assert capture.warnings[0].reason == "reply_capture_failed"


def test_an_unwritable_tasks_md_fails_the_line_without_losing_the_reply(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "Q3 planning", type="standup")
    text = "intro\n/task call Terry\noutro"

    root = tmp_workspace.root
    original_mode = root.stat().st_mode
    root.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        capture = capture_reply_tasks(
            tmp_workspace, text, source=meeting.path, source_id=meeting.id
        )
    finally:
        root.chmod(original_mode)

    lines = capture.text.split("\n")
    assert len(lines) == 3  # no line ever lost
    assert lines == ["intro", "/task call Terry", "outro"]
    assert capture.tasks == ()
    assert len(capture.warnings) == 1
    assert capture.warnings[0].reason == "reply_capture_failed"
