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


# --- T021: fence tracking (US3) ------------------------------------------------


def test_task_line_inside_a_backtick_fence_is_not_eligible() -> None:
    text = "```\n/task call Terry\n```"
    lines = parse_reply_lines(text)
    assert lines[1].task is None


def test_task_line_inside_a_tilde_fence_is_not_eligible() -> None:
    text = "~~~\n/task call Terry\n~~~"
    lines = parse_reply_lines(text)
    assert lines[1].task is None


def test_fence_with_an_info_string_still_opens_a_fence() -> None:
    text = "```python\n/task call Terry\n```"
    lines = parse_reply_lines(text)
    assert lines[1].task is None


def test_a_closing_fence_longer_than_its_opener_still_closes() -> None:
    text = "```\n/task inside\n````\n/task outside"
    lines = parse_reply_lines(text)
    assert lines[1].task is None  # inside the fence
    assert lines[3].task is not None  # after it closed


def test_an_unclosed_fence_makes_everything_after_it_ineligible() -> None:
    text = "```\nsome code\n/task call Terry\nmore code"
    lines = parse_reply_lines(text)
    assert lines[2].task is None
    assert lines[3].task is None


def test_a_four_space_indented_block_needs_no_special_handling() -> None:
    # Already excluded by the leading-whitespace rule -- no fence involved.
    text = "    /task call Terry"
    (line,) = parse_reply_lines(text)
    assert line.task is None


def test_a_task_line_immediately_after_a_closed_fence_is_still_eligible() -> None:
    text = "```\ncode here\n```\n/task call Terry"
    lines = parse_reply_lines(text)
    assert lines[3].task is not None
    assert lines[3].task.argument == "call Terry"
