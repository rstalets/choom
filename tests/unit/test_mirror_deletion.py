"""Unit coverage for `plan_mirror_deletion`/`commit_mirror_deletion`
(017-editor-task-delete) -- everything about *what* a deletion removes,
decidable against a string with no terminal involved (plan.md gate VI).
"""

from __future__ import annotations

from pathlib import Path

from choom.core.errors import UsageError
from choom.core.mirrors import commit_mirror_deletion, plan_mirror_deletion
from choom.core.models import Workspace
from tests.conftest import tasks_file, write_tasks

_SOURCE = Path("/ws/meetings/2026/08/q3-planning.md")


def _bare_line(task_id: str, text: str = "call Terry") -> str:
    return f"- [ ] [{text}](../../../tasks.md#{task_id})\n"


# --- FR-008: not a task line -----------------------------------------------------


def test_prose_is_not_a_task_line(tmp_workspace: Workspace) -> None:
    assert plan_mirror_deletion(tmp_workspace, "just prose\n", 1, source=_SOURCE) is None


def test_heading_is_not_a_task_line(tmp_workspace: Workspace) -> None:
    assert plan_mirror_deletion(tmp_workspace, "# a heading\n", 1, source=_SOURCE) is None


def test_blank_line_is_not_a_task_line(tmp_workspace: Workspace) -> None:
    assert plan_mirror_deletion(tmp_workspace, "\n", 1, source=_SOURCE) is None


def test_frontmatter_line_is_not_a_task_line(tmp_workspace: Workspace) -> None:
    text = "---\ntitle: x\n---\n"
    assert plan_mirror_deletion(tmp_workspace, text, 2, source=_SOURCE) is None


def test_checklist_item_with_no_link_is_not_a_task_line(tmp_workspace: Workspace) -> None:
    assert plan_mirror_deletion(tmp_workspace, "- [ ] buy milk\n", 1, source=_SOURCE) is None


def test_checklist_item_whose_only_link_is_not_a_task_link_is_not_a_task_line(
    tmp_workspace: Workspace,
) -> None:
    text = "- [ ] see [the July meeting](../../meetings/2026/07/x.md#meeting_2026abc)\n"
    assert plan_mirror_deletion(tmp_workspace, text, 1, source=_SOURCE) is None


def test_task_line_inside_a_fence_is_not_a_task_line(tmp_workspace: Workspace) -> None:
    text = "```\n" + _bare_line("task_a1b2") + "```\n"
    assert plan_mirror_deletion(tmp_workspace, text, 2, source=_SOURCE) is None


def test_task_line_inside_an_inline_code_span_is_not_a_task_line(
    tmp_workspace: Workspace,
) -> None:
    text = "- [ ] `[call Terry](../../../tasks.md#task_a1b2)`\n"
    assert plan_mirror_deletion(tmp_workspace, text, 1, source=_SOURCE) is None


# --- The splice invariant --------------------------------------------------------


def _assert_splice_invariant(text: str, line: int, workspace: Workspace) -> None:
    plan = plan_mirror_deletion(workspace, text, line, source=_SOURCE)
    assert plan is not None
    assert plan.outcome in ("deletable", "line_only")
    assert plan.text == text[: plan.span[0]] + text[plan.span[1] :]


def test_splice_invariant_holds_for_a_deletable_mirror(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    text = _bare_line("task_a1b2")
    _assert_splice_invariant(text, 1, tmp_workspace)


def test_splice_invariant_holds_for_a_line_only_mirror(tmp_workspace: Workspace) -> None:
    text = _bare_line("task_gone")
    _assert_splice_invariant(text, 1, tmp_workspace)


# --- What survives around the removed line ---------------------------------------


def test_blank_lines_above_and_below_both_survive(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    text = "above\n\n" + _bare_line("task_a1b2") + "\nbelow\n"
    plan = plan_mirror_deletion(tmp_workspace, text, 3, source=_SOURCE)
    assert plan is not None
    assert plan.text == "above\n\n\nbelow\n"


def test_indented_continuation_beneath_the_line_survives(tmp_workspace: Workspace) -> None:
    # Deliberately unlike tasks.md, where a task's indented body is part of the
    # record and goes with it -- here the cursor was on one line, so one line
    # is removed and the orphaned indentation stays exactly as typed.
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    text = _bare_line("task_a1b2") + "  a nested note\n  a second line of it\n"
    plan = plan_mirror_deletion(tmp_workspace, text, 1, source=_SOURCE)
    assert plan is not None
    assert plan.text == "  a nested note\n  a second line of it\n"


def test_nested_task_line_is_removed_with_its_own_indentation_and_no_neighbour_reindented(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    text = "- top level\n  - [ ] [call Terry](../../../tasks.md#task_a1b2)\n- another top level\n"
    plan = plan_mirror_deletion(tmp_workspace, text, 2, source=_SOURCE)
    assert plan is not None
    assert plan.text == "- top level\n- another top level\n"


# --- Span: last line, only line -------------------------------------------------


def test_last_line_with_a_trailing_newline_runs_to_end_of_text(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    text = "above\n" + _bare_line("task_a1b2")
    plan = plan_mirror_deletion(tmp_workspace, text, 2, source=_SOURCE)
    assert plan is not None
    assert plan.text == "above\n"
    assert plan.span == (len("above\n"), len(text))


def test_last_line_with_no_trailing_newline_absorbs_the_preceding_terminator(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    line = _bare_line("task_a1b2").rstrip("\n")
    text = "above\n" + line
    plan = plan_mirror_deletion(tmp_workspace, text, 2, source=_SOURCE)
    assert plan is not None
    assert plan.text == "above"
    assert not plan.text.endswith("\n")


def test_the_only_line_of_the_file_spans_the_whole_buffer(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    text = _bare_line("task_a1b2").rstrip("\n")
    plan = plan_mirror_deletion(tmp_workspace, text, 1, source=_SOURCE)
    assert plan is not None
    assert plan.text == ""
    assert plan.span == (0, len(text))


# --- extra_text (FR-011) ---------------------------------------------------------


def test_extra_text_is_false_for_a_bare_mirror_line(tmp_workspace: Workspace) -> None:
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.extra_text is False


def test_extra_text_is_true_for_trailing_prose(tmp_workspace: Workspace) -> None:
    text = "- [ ] [call Terry](../../../tasks.md#task_gone) before Friday, ask Dana\n"
    plan = plan_mirror_deletion(tmp_workspace, text, 1, source=_SOURCE)
    assert plan is not None
    assert plan.extra_text is True


def test_extra_text_is_true_for_a_second_link_on_the_line(tmp_workspace: Workspace) -> None:
    text = (
        "- [ ] [call Terry](../../../tasks.md#task_first) "
        "and [Jan](../../../tasks.md#task_second)\n"
    )
    plan = plan_mirror_deletion(tmp_workspace, text, 1, source=_SOURCE)
    assert plan is not None
    assert plan.extra_text is True


# --- deletable vs line_only -------------------------------------------------------


def test_outcome_is_deletable_when_exactly_one_task_record_carries_the_id(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_a1b2"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "deletable"


def test_outcome_is_line_only_when_no_task_record_carries_the_id(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] someone else <!-- id:task_other -->\n")
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "line_only"
    assert plan.message == ""


def test_outcome_is_line_only_when_tasks_md_does_not_exist(tmp_workspace: Workspace) -> None:
    # init_workspace touches an empty tasks.md; remove it to exercise the
    # genuinely-missing-file branch rather than the empty-but-present one.
    tasks_file(tmp_workspace).unlink()
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "line_only"


# --- The unreadable/invalid boundary (FR-021, FR-022; research R6) --------------


def test_unresolvable_id_plus_unterminated_comment_is_unreadable(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] broken <!-- id:task_broken\n")
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "unreadable_tasks"
    assert "tasks.md:1" in plan.message
    assert plan.text == ""
    assert plan.span == (0, 0)


def test_unresolvable_id_plus_malformed_comment_is_unreadable(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] broken <!-- id:task_broken unknown:x -->\n")
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "unreadable_tasks"


def test_unresolvable_id_plus_only_an_invalid_value_warning_is_line_only(
    tmp_workspace: Workspace,
) -> None:
    # task_invalid_value still falls through to _append_task -- the task is
    # findable by id, so an unrelated unresolvable id must not be refused
    # merely because this warning exists (FR-022).
    write_tasks(tmp_workspace, "- [ ] fine <!-- id:task_fine created:not-a-date -->\n")
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "line_only"


def test_a_resolvable_id_still_deletes_when_the_file_also_has_an_unreadable_line(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call Terry <!-- id:task_a1b2 -->\n- [ ] broken <!-- id:task_broken\n",
    )
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_a1b2"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "deletable"


# --- Ambiguous id (FR-023) --------------------------------------------------------


def test_ambiguous_id_names_both_conflicting_lines(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call Terry <!-- id:task_dupe -->\n- [ ] call Terry again <!-- id:task_dupe -->\n",
    )
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_dupe"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "ambiguous_id"
    assert "1" in plan.message and "2" in plan.message
    assert plan.text == ""
    assert plan.span == (0, 0)


# --- Self-referential (FR-024) ---------------------------------------------------


def test_self_referential_when_body_task_id_matches_the_lines_task(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    plan = plan_mirror_deletion(
        tmp_workspace,
        _bare_line("task_a1b2"),
        1,
        source=_SOURCE,
        body_task_id="task_a1b2",
    )
    assert plan is not None
    assert plan.outcome == "self_referential"
    assert plan.text == ""
    assert plan.span == (0, 0)


def test_body_task_id_for_a_different_task_does_not_refuse(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call Terry <!-- id:task_a1b2 -->\n")
    plan = plan_mirror_deletion(
        tmp_workspace,
        _bare_line("task_a1b2"),
        1,
        source=_SOURCE,
        body_task_id="task_other",
    )
    assert plan is not None
    assert plan.outcome == "deletable"


# --- commit_mirror_deletion -------------------------------------------------------


def test_commit_deletable_removes_the_record_and_leaves_the_rest_byte_identical(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] first <!-- id:task_a -->\n- [ ] call Terry <!-- id:task_a1b2 -->\n"
        "- [ ] last <!-- id:task_c -->\n",
    )
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_a1b2"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "deletable"

    result = commit_mirror_deletion(tmp_workspace, plan)
    assert result is plan

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert "task_a1b2" not in text
    assert "task_a" in text
    assert "task_c" in text


def test_commit_line_only_writes_nothing_at_all(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] someone else <!-- id:task_other -->\n")
    path = tasks_file(tmp_workspace)
    before = path.read_bytes()

    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "line_only"

    commit_mirror_deletion(tmp_workspace, plan)

    assert path.read_bytes() == before


def test_commit_raises_usage_error_for_each_refusing_outcome(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] broken <!-- id:task_broken\n")
    plan = plan_mirror_deletion(tmp_workspace, _bare_line("task_gone"), 1, source=_SOURCE)
    assert plan is not None
    assert plan.outcome == "unreadable_tasks"
    try:
        commit_mirror_deletion(tmp_workspace, plan)
    except UsageError:
        pass
    else:
        raise AssertionError("expected UsageError")


def test_the_two_new_functions_and_the_result_type_import_from_core() -> None:
    from choom.core import MirrorDeletion, commit_mirror_deletion, plan_mirror_deletion

    assert plan_mirror_deletion is not None
    assert commit_mirror_deletion is not None
    assert MirrorDeletion is not None
