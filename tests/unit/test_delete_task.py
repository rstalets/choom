from __future__ import annotations

import pytest

from choom.core.errors import NotFoundError, UsageError
from choom.core.models import Workspace
from choom.core.tasks import delete_task, load_tasks
from tests.conftest import tasks_file, write_raw, write_tasks


def test_deletes_lone_task_leaving_an_empty_file(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")

    task = delete_task(tmp_workspace, "t_a1b2")

    assert task.id == "t_a1b2"
    assert task.text == "call the vendor"
    assert tasks_file(tmp_workspace).read_text(encoding="utf-8") == ""


def test_body_span_removed_whole(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n"
        "\n"
        "  old detail\n"
        "  more detail\n"
        "\n"
        "- [ ] next <!-- id:t_c3d4 -->\n",
    )

    task = delete_task(tmp_workspace, "t_a1b2")

    assert task.body == "old detail\nmore detail"
    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    # The blank line between the body and the next task's checkbox sits
    # outside the body span (it is a trailing separator, dropped by
    # `_body_span`'s own rule, not committed content) -- per data-model.md
    # §2, deletion removes exactly `lines[:checkbox_idx] + lines[span.end:]`
    # and that line is part of `lines[span.end:]`, so it survives untouched.
    assert text == "\n- [ ] next <!-- id:t_c3d4 -->\n"


def test_neighbouring_tasks_byte_identical(tmp_workspace: Workspace) -> None:
    original = (
        "# My tasks\n\n"
        "- [ ] one <!-- id:t_0001 type:followup tags:legal created:2026-07-20 -->\n"
        "\n"
        "  keep me\n"
        "\n"
        "- [ ] two <!-- id:t_0002 -->\n"
        "\n"
        "  body of two\n"
        "\n"
        "- [x] three <!-- id:t_0003 -->\n"
        "\n"
        "Trailing prose that must never move.\n"
    )
    write_tasks(tmp_workspace, original)

    delete_task(tmp_workspace, "t_0002")

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert text.startswith("# My tasks\n\n")
    assert "- [ ] one <!-- id:t_0001 type:followup tags:legal created:2026-07-20 -->\n" in text
    assert "  keep me\n" in text
    assert "- [x] three <!-- id:t_0003 -->\n\nTrailing prose that must never move.\n" in text
    assert "t_0002" not in text
    assert "body of two" not in text


def test_crlf_file_stays_crlf_after_delete(tmp_workspace: Workspace) -> None:
    write_raw(
        tasks_file(tmp_workspace),
        "- [ ] one <!-- id:t_a1b2 -->\n- [ ] two <!-- id:t_c3d4 -->\n",
        newline="\r\n",
    )

    delete_task(tmp_workspace, "t_a1b2")

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert "\n" not in text.replace("\r\n", "")
    assert text == "- [ ] two <!-- id:t_c3d4 -->\r\n"


def test_lf_file_stays_lf_after_delete(tmp_workspace: Workspace) -> None:
    write_raw(
        tasks_file(tmp_workspace),
        "- [ ] one <!-- id:t_a1b2 -->\n- [ ] two <!-- id:t_c3d4 -->\n",
        newline="\n",
    )

    delete_task(tmp_workspace, "t_a1b2")

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert text == "- [ ] two <!-- id:t_c3d4 -->\n"


def test_trailing_newline_state_preserved_when_deleted_block_is_last(
    tmp_workspace: Workspace,
) -> None:
    write_raw(
        tasks_file(tmp_workspace),
        "- [ ] one <!-- id:t_a1b2 -->\n- [ ] two <!-- id:t_c3d4 -->",
        newline="\n",
    )

    delete_task(tmp_workspace, "t_c3d4")

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    # The original file had no trailing newline; the second task (with no
    # body) is now what disappears, and the first task's line -- now the
    # file's last line -- has that no-trailing-newline state restored onto
    # it, exactly as `set_task_body` restores it for a body removed from the
    # end of the file.
    assert text == "- [ ] one <!-- id:t_a1b2 -->"


def test_deleting_last_task_with_no_trailing_newline_leaves_empty_file(
    tmp_workspace: Workspace,
) -> None:
    write_raw(tasks_file(tmp_workspace), "- [ ] only <!-- id:t_a1b2 -->", newline="\n")

    delete_task(tmp_workspace, "t_a1b2")

    assert tasks_file(tmp_workspace).read_text(encoding="utf-8") == ""


def test_missing_id_raises_not_found_error(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")
    before = tasks_file(tmp_workspace).read_bytes()

    with pytest.raises(NotFoundError):
        delete_task(tmp_workspace, "t_zzzz")

    assert tasks_file(tmp_workspace).read_bytes() == before


def test_missing_tasks_file_raises_not_found_error(tmp_workspace: Workspace) -> None:
    with pytest.raises(NotFoundError):
        delete_task(tmp_workspace, "t_zzzz")


def test_duplicate_id_raises_usage_error_naming_both_lines(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] first <!-- id:t_dupe -->\n- [ ] second <!-- id:t_dupe -->\n",
    )
    before = tasks_file(tmp_workspace).read_bytes()

    with pytest.raises(UsageError, match="lines 1 and 2"):
        delete_task(tmp_workspace, "t_dupe")

    assert tasks_file(tmp_workspace).read_bytes() == before


def test_malformed_line_elsewhere_does_not_block_delete(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] good <!-- id:t_a1b2 -->\n"
        "- [ ] bad <!-- bogus stuff -->\n"
        "- [ ] other <!-- id:t_c3d4 -->\n",
    )

    delete_task(tmp_workspace, "t_a1b2")

    text = tasks_file(tmp_workspace).read_text(encoding="utf-8")
    assert "- [ ] bad <!-- bogus stuff -->\n" in text
    assert "- [ ] other <!-- id:t_c3d4 -->\n" in text
    assert "t_a1b2" not in text


def test_returns_task_as_it_was_before_deletion(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [x] call the vendor <!-- id:t_a1b2 type:followup tags:urgent -->\n",
    )

    task = delete_task(tmp_workspace, "t_a1b2")

    assert task.done is True
    assert task.type == "followup"
    assert task.tags == ("urgent",)


def test_deleted_task_no_longer_loads(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] first <!-- id:t_a1b2 -->\n- [ ] second <!-- id:t_c3d4 -->\n",
    )

    delete_task(tmp_workspace, "t_a1b2")

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []
    assert [t.id for t in tasks] == ["t_c3d4"]
