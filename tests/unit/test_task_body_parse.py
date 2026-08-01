from __future__ import annotations

from choom.core.tasks import parse_tasks

# --- span boundaries (T006) --------------------------------------------------


def test_task_with_no_body_has_empty_body_and_zero_width_span() -> None:
    text = "- [ ] buy milk <!-- id:t_a1b2 -->\n"
    parsed = parse_tasks(text)

    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].body == ""
    span = parsed.bodies[0]
    assert span.start == span.end == 1


def test_simple_body_is_read_and_dedented() -> None:
    text = "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n"
    parsed = parse_tasks(text)

    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].body == "Need the Q3 comparison."


def test_blank_line_inside_a_body_is_kept() -> None:
    text = "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  First paragraph.\n\n  Second paragraph.\n"
    parsed = parse_tasks(text)

    assert parsed.tasks[0].body == "First paragraph.\n\nSecond paragraph."


def test_trailing_blank_lines_are_excluded_from_the_span() -> None:
    text = (
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n"
        "\n"
        "  Need the Q3 comparison.\n"
        "\n"
        "\n"
        "- [x] send the invoice <!-- id:t_c3d4 -->\n"
    )
    parsed = parse_tasks(text)

    assert len(parsed.tasks) == 2
    assert parsed.tasks[0].body == "Need the Q3 comparison."
    # The blank lines separating the two tasks belong to neither.
    span = parsed.bodies[0]
    lines = parsed.lines
    assert "".join(lines[span.end :]).startswith("\n\n- [x] send the invoice")


def test_nested_checkbox_line_ends_the_body_and_stays_its_own_task() -> None:
    text = (
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n"
        "\n"
        "  Some detail.\n"
        "  - [ ] a nested checklist item\n"
    )
    parsed = parse_tasks(text)

    assert len(parsed.tasks) == 2
    assert parsed.tasks[0].body == "Some detail."
    assert parsed.tasks[1].text == "a nested checklist item"
    assert parsed.tasks[1].body == ""


def test_non_indented_line_ends_the_body() -> None:
    text = (
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n"
        "\n"
        "  Some detail.\n"
        "Some unrelated prose at column zero.\n"
    )
    parsed = parse_tasks(text)

    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].body == "Some detail."
    span = parsed.bodies[0]
    assert "".join(parsed.lines[span.end :]) == "Some unrelated prose at column zero.\n"


def test_tab_indented_body_is_read_verbatim_in_depth() -> None:
    text = "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n\tNeed the Q3 comparison.\n"
    parsed = parse_tasks(text)

    assert parsed.tasks[0].body == "Need the Q3 comparison."


def test_body_on_the_last_task_at_eof_with_no_trailing_newline() -> None:
    text = "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison."
    parsed = parse_tasks(text)

    assert parsed.tasks[0].body == "Need the Q3 comparison."
    assert "".join(parsed.lines) == text


def test_body_under_malformed_comment_line_is_not_reattached() -> None:
    text = (
        "- [ ] good task <!-- id:t_a1b2 -->\n"
        "- [ ] broken <!-- id:t_zzzz bogus -->\n"
        "  This looks like a body but its task is malformed.\n"
    )
    parsed = parse_tasks(text)

    assert len(parsed.tasks) == 1
    assert parsed.tasks[0].text == "good task"
    assert parsed.tasks[0].body == ""
    assert len(parsed.warnings) == 1
    # The dangling indented line is preserved in the file untouched.
    assert "This looks like a body" in "".join(parsed.lines)


def test_roundtrip_property_holds_with_bodies_present() -> None:
    text = (
        "- [ ] one <!-- id:t_0001 -->\n"
        "\n"
        "  detail one\n"
        "\n"
        "- [x] two <!-- id:t_0002 -->\n"
        "\n"
        "  detail two\n"
        "  - a plain bullet, not a checkbox\n"
    )
    parsed = parse_tasks(text)
    assert "".join(parsed.lines) == text
    assert len(parsed.tasks) == 2
    assert parsed.tasks[0].body == "detail one"
    assert parsed.tasks[1].body == "detail two\n- a plain bullet, not a checkbox"


# --- dedent and indent reconstruction (T007) ---------------------------------


def test_four_space_prefix_is_stripped_and_remembered() -> None:
    text = "- [ ] thing <!-- id:t_a1b2 -->\n\n    detail line\n"
    parsed = parse_tasks(text)

    assert parsed.tasks[0].body == "detail line"
    assert parsed.bodies[0].indent == "    "


def test_tab_prefix_is_stripped_and_remembered() -> None:
    text = "- [ ] thing <!-- id:t_a1b2 -->\n\n\tdetail line\n"
    parsed = parse_tasks(text)

    assert parsed.tasks[0].body == "detail line"
    assert parsed.bodies[0].indent == "\t"


def test_relative_indentation_of_nested_bullets_survives_dedent() -> None:
    text = "- [ ] thing <!-- id:t_a1b2 -->\n\n  top level\n    nested further\n"
    parsed = parse_tasks(text)

    assert parsed.tasks[0].body == "top level\n  nested further"
    assert parsed.bodies[0].indent == "  "


def test_mixed_tabs_and_spaces_degrade_to_no_dedent_without_losing_content() -> None:
    text = "- [ ] thing <!-- id:t_a1b2 -->\n\n  two spaces\n\tone tab\n"
    parsed = parse_tasks(text)

    # No common prefix between "  " and "\t" -- nothing is stripped, but every
    # character survives, just at its original depth.
    assert parsed.tasks[0].body == "  two spaces\n\tone tab"
    # The span's remembered indent still falls back to two spaces for a future write.
    assert parsed.bodies[0].indent == "  "


def test_no_body_span_falls_back_to_two_space_indent() -> None:
    text = "- [ ] thing <!-- id:t_a1b2 -->\n"
    parsed = parse_tasks(text)

    assert parsed.bodies[0].indent == "  "
