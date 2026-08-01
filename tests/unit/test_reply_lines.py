from __future__ import annotations

from choom.core.editor_commands import parse_reply_lines


def test_one_reply_line_per_input_line_in_order() -> None:
    text = "line one\n/task call Terry\nline three"
    lines = parse_reply_lines(text)
    assert len(lines) == 3
    assert [line.text for line in lines] == ["line one", "/task call Terry", "line three"]


def test_task_command_is_eligible() -> None:
    (line,) = parse_reply_lines("/task call Terry")
    assert line.task is not None
    assert line.task.command.name == "task"
    assert line.task.argument == "call Terry"


def test_task_with_type_suffix_is_eligible() -> None:
    (line,) = parse_reply_lines("/task.followup call Terry #urgent")
    assert line.task is not None
    assert line.task.command.name == "task"
    assert line.task.suffix == "followup"
    assert line.task.argument == "call Terry #urgent"


def test_leading_space_line_is_not_eligible() -> None:
    (line,) = parse_reply_lines("  /task call Terry")
    assert line.task is None
    assert line.text == "  /task call Terry"


def test_inline_mention_is_not_eligible() -> None:
    (line,) = parse_reply_lines("Did you know you can type /task here?")
    assert line.task is None


def test_ai_command_is_not_eligible() -> None:
    (line,) = parse_reply_lines("/ai summarise this")
    assert line.task is None


def test_link_command_is_not_eligible() -> None:
    (line,) = parse_reply_lines("/link Q3 planning")
    assert line.task is None


def test_bare_task_with_no_description_is_still_eligible() -> None:
    (line,) = parse_reply_lines("/task")
    assert line.task is not None
    assert line.task.command.name == "task"
    assert line.task.argument == ""


def test_crlf_input_is_normalised_line_by_line() -> None:
    text = "/task call Terry\r\nline two\r\nline three"
    lines = parse_reply_lines(text)
    assert len(lines) == 3
    assert lines[0].task is not None
    assert lines[0].text == "/task call Terry"
    assert lines[1].text == "line two"
    assert lines[2].text == "line three"


def test_empty_text_returns_no_lines() -> None:
    assert parse_reply_lines("") == ()
