from __future__ import annotations

import pytest

from endpaper.core.tasks import parse_tasks


@pytest.mark.parametrize(
    ("line", "indent_expected", "marker_expected", "done_expected"),
    [
        ("- [ ] buy milk\n", "", "-", False),
        ("* [ ] buy milk\n", "", "*", False),
        ("+ [ ] buy milk\n", "", "+", False),
        ("  - [ ] buy milk\n", "  ", "-", False),
        ("\t- [ ] buy milk\n", "\t", "-", False),
        ("- [x] buy milk\n", "", "-", True),
        ("- [X] buy milk\n", "", "-", True),
    ],
)
def test_grammar_table(
    line: str, indent_expected: str, marker_expected: str, done_expected: bool
) -> None:
    parsed = parse_tasks(line)
    assert len(parsed.tasks) == 1
    task = parsed.tasks[0]
    assert task.done is done_expected
    assert task.text == "buy milk"


def test_not_a_task_line_preserved_verbatim() -> None:
    text = "# Heading\n\nSome prose.\n- not a checkbox\n"
    parsed = parse_tasks(text)
    assert parsed.tasks == ()
    assert "".join(parsed.lines) == text


def test_bare_task_no_comment() -> None:
    parsed = parse_tasks("- [ ] buy milk\n")
    assert len(parsed.tasks) == 1
    task = parsed.tasks[0]
    assert task.id is None
    assert task.text == "buy milk"
    assert parsed.needs_id == (0,)


def test_unterminated_comment_is_malformed_and_skipped() -> None:
    text = "- [ ] thing <!-- id:\n"
    parsed = parse_tasks(text)
    assert parsed.tasks == ()
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].reason == "task_unterminated_comment"
    assert "".join(parsed.lines) == text
    assert parsed.needs_id == ()


def test_comment_without_recognized_keys_is_bare() -> None:
    text = "- [ ] fix the <!-- hack --> path\n"
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    task = parsed.tasks[0]
    assert task.id is None
    assert task.text == "fix the <!-- hack --> path"
    assert parsed.needs_id == (0,)


def test_malformed_unknown_token_is_skipped() -> None:
    text = "- [ ] thing <!-- id:t_a1b2 bogus -->\n"
    parsed = parse_tasks(text)
    assert parsed.tasks == ()
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].reason == "task_malformed_comment"
    assert "".join(parsed.lines) == text


def test_well_formed_with_bad_created_is_kept_with_warning() -> None:
    text = "- [ ] thing <!-- id:t_a1b2 created:yesterday -->\n"
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    task = parsed.tasks[0]
    assert task.id == "t_a1b2"
    assert task.created is None
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].reason == "task_invalid_value"


def test_well_formed_task() -> None:
    text = (
        "- [ ] send the vendor comparison "
        "<!-- id:t_a1b2 type:followup tags:procurement,q3 created:2026-07-28 -->\n"
    )
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    task = parsed.tasks[0]
    assert task.id == "t_a1b2"
    assert task.text == "send the vendor comparison"
    assert task.type == "followup"
    assert task.tags == ("procurement", "q3")
    from datetime import date

    assert task.created == date(2026, 7, 28)
    assert parsed.warnings == ()


@pytest.mark.parametrize(
    "text",
    [
        "- [ ] one\n- [x] two\n",
        "- [ ] one\r\n- [x] two\r\n",
        "- [ ] one\r- [x] two\r",
        "- [ ] one\n- [x] two",
        "- [ ] one\r\n- [x] two",
        "",
        "no tasks here at all",
    ],
)
def test_roundtrip_property(text: str) -> None:
    parsed = parse_tasks(text)
    assert "".join(parsed.lines) == text


def test_mixed_line_endings_roundtrip() -> None:
    text = "- [ ] one\n- [x] two\r\n- [ ] three\r- [x] four"
    parsed = parse_tasks(text)
    assert "".join(parsed.lines) == text
    assert len(parsed.tasks) == 4
