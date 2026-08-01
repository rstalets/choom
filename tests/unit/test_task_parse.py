from __future__ import annotations

import pytest

from choom.core.tasks import parse_tasks


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
    text = "- [ ] thing <!-- id:task_a1b2 bogus -->\n"
    parsed = parse_tasks(text)
    assert parsed.tasks == ()
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].reason == "task_malformed_comment"
    assert "".join(parsed.lines) == text


def test_well_formed_with_bad_created_is_kept_with_warning() -> None:
    text = "- [ ] thing <!-- id:task_a1b2 created:yesterday -->\n"
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    task = parsed.tasks[0]
    assert task.id == "task_a1b2"
    assert task.created is None
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].reason == "task_invalid_value"


def test_well_formed_task() -> None:
    text = (
        "- [ ] send the vendor comparison "
        "<!-- id:task_a1b2 type:followup tags:procurement,q3 created:2026-07-28 -->\n"
    )
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    task = parsed.tasks[0]
    assert task.id == "task_a1b2"
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


# --- US5: the links field --------------------------------------------------


def test_links_field_with_one_id() -> None:
    text = "- [ ] call Terry <!-- id:task_a1b2 links:meeting_20260728_a1b2c3d4 -->\n"
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].links == ("meeting_20260728_a1b2c3d4",)


def test_links_field_with_several_ids() -> None:
    text = (
        "- [ ] call Terry "
        "<!-- id:task_a1b2 links:meeting_20260728_a1b2c3d4,note_20260731_ff00ff00 -->\n"
    )
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].links == ("meeting_20260728_a1b2c3d4", "note_20260731_ff00ff00")


def test_links_field_malformed_value_warns_and_skips_only_that_line() -> None:
    text = (
        "- [ ] first <!-- id:task_a1b2 links:not valid -->\n"
        "- [ ] second <!-- id:task_c3d4 links:meeting_1 -->\n"
    )
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].id == "task_c3d4"
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].reason == "task_malformed_comment"


def test_links_field_empty_value_is_malformed() -> None:
    text = "- [ ] thing <!-- id:task_a1b2 links: -->\n"
    parsed = parse_tasks(text)
    assert parsed.tasks == ()
    assert len(parsed.warnings) == 1
    assert parsed.warnings[0].reason == "task_malformed_comment"


def test_line_with_no_links_field_parses_exactly_as_before() -> None:
    text = (
        "- [ ] send the vendor comparison "
        "<!-- id:task_a1b2 type:followup tags:procurement,q3 created:2026-07-28 -->\n"
    )
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].links == ()
    assert parsed.warnings == ()


def test_hand_written_links_field_no_longer_makes_the_task_vanish() -> None:
    # Before US5, "links" was an unrecognised key, which made _classify_body
    # return "malformed" and drop the whole task from every listing (research R7).
    text = "- [ ] call Terry <!-- id:task_a1b2 links:meeting_1 created:2026-07-28 -->\n"
    parsed = parse_tasks(text)
    assert len(parsed.tasks) == 1
    assert parsed.warnings == ()


def test_pre_feature_file_with_no_bodies_parses_identically_and_is_not_rewritten() -> None:
    """A tasks.md written before this feature (007) has no indented continuation
    lines at all. Every task must still list exactly as it did, with an empty
    body and a zero-width span -- proof that adding body support changes
    nothing about a file that never had one (FR-006, SC-006)."""
    text = (
        "# My tasks\n\n"
        "- [ ] one <!-- id:t_0001 created:2026-07-20 -->\n"
        "- [ ] two <!-- id:t_0002 type:followup tags:legal created:2026-07-21 -->\n"
        "- [x] three <!-- id:t_0003 created:2026-07-22 -->\n"
    )
    parsed = parse_tasks(text)

    assert "".join(parsed.lines) == text
    assert len(parsed.tasks) == 3
    assert [t.id for t in parsed.tasks] == ["t_0001", "t_0002", "t_0003"]
    for task, span in zip(parsed.tasks, parsed.bodies, strict=True):
        assert task.body == ""
        assert span.start == span.end
