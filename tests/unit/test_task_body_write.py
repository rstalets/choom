from __future__ import annotations

import os
import stat

import pytest

from choom.core.errors import NotFoundError, UsageError, WorkspaceError
from choom.core.models import Workspace
from choom.core.tasks import load_tasks, set_task_body
from tests.conftest import tasks_file, write_raw, write_tasks

# --- writer behaviour (T013) --------------------------------------------------


def test_adds_a_body_where_none_existed(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")

    task = set_task_body(tmp_workspace, "t_a1b2", "Need the Q3 comparison.")

    assert task.body == "Need the Q3 comparison."
    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text == ("- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n")


def test_replaces_an_existing_body(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  old detail\n",
    )

    task = set_task_body(tmp_workspace, "t_a1b2", "new detail")

    assert task.body == "new detail"
    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text == "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  new detail\n"


def test_empty_body_removes_the_span_leaving_a_lone_task_line(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n"
        "\n"
        "  old detail\n"
        "\n"
        "- [ ] next <!-- id:t_c3d4 -->\n",
    )

    task = set_task_body(tmp_workspace, "t_a1b2", "")

    assert task.body == ""
    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text == "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n- [ ] next <!-- id:t_c3d4 -->\n"


def test_task_own_line_and_every_other_line_stay_byte_identical(
    tmp_workspace: Workspace,
) -> None:
    original = (
        "# My tasks\n\n"
        "- [ ] one <!-- id:t_0001 type:followup tags:legal created:2026-07-20 -->\n"
        "\n"
        "  original body\n"
        "\n"
        "- [x] two <!-- id:t_0002 -->\n"
        "\n"
        "Trailing prose that must never move.\n"
    )
    write_tasks(tmp_workspace, original)

    set_task_body(tmp_workspace, "t_0001", "new body")

    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text.startswith("# My tasks\n\n")
    assert "- [ ] one <!-- id:t_0001 type:followup tags:legal created:2026-07-20 -->\n" in text
    assert "- [x] two <!-- id:t_0002 -->\n\nTrailing prose that must never move.\n" in text


def test_identical_body_performs_no_write_at_all(tmp_workspace: Workspace) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n",
    )
    path = tasks_file(tmp_workspace)
    before_bytes = path.read_bytes()
    before_mtime = os.stat(path).st_mtime_ns

    task = set_task_body(tmp_workspace, "t_a1b2", "Need the Q3 comparison.")

    assert task.body == "Need the Q3 comparison."
    assert path.read_bytes() == before_bytes
    assert os.stat(path).st_mtime_ns == before_mtime


def test_saving_empty_body_when_none_existed_is_also_a_no_op(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")
    path = tasks_file(tmp_workspace)
    before_bytes = path.read_bytes()

    set_task_body(tmp_workspace, "t_a1b2", "")

    assert path.read_bytes() == before_bytes


# --- trailing-blank normalisation (011, research R10) --------------------------


def test_body_with_trailing_blank_lines_saves_the_same_as_without_them(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")

    task = set_task_body(tmp_workspace, "t_a1b2", "Need the Q3 comparison.\n\n\n")

    assert task.body == "Need the Q3 comparison."
    text = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text == "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n"


def test_body_identical_once_trailing_blanks_are_stripped_is_still_a_no_op(
    tmp_workspace: Workspace,
) -> None:
    # A padded editor buffer (US7) ends with one blank line below the
    # content -- saving it unedited must not grow the file by a blank line
    # every time, or a save-without-typing would never be stable.
    write_tasks(
        tmp_workspace,
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  Need the Q3 comparison.\n",
    )
    path = tasks_file(tmp_workspace)
    before_bytes = path.read_bytes()

    task = set_task_body(tmp_workspace, "t_a1b2", "Need the Q3 comparison.\n")

    assert task.body == "Need the Q3 comparison."
    assert path.read_bytes() == before_bytes


def test_saving_a_padded_body_twice_in_a_row_is_idempotent(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")

    set_task_body(tmp_workspace, "t_a1b2", "Need the Q3 comparison.\n")
    after_first = tasks_file(tmp_workspace).read_bytes()

    set_task_body(tmp_workspace, "t_a1b2", "Need the Q3 comparison.\n")
    after_second = tasks_file(tmp_workspace).read_bytes()

    assert after_first == after_second


# --- writer failure and preservation (T014) ----------------------------------


def test_crlf_file_stays_crlf_after_adding_a_body(tmp_workspace: Workspace) -> None:
    write_raw(
        tasks_file(tmp_workspace),
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n",
        newline="\r\n",
    )

    set_task_body(tmp_workspace, "t_a1b2", "line one\nline two")

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert "\n" not in text.replace("\r\n", "")
    assert text == ("- [ ] call the vendor <!-- id:t_a1b2 -->\r\n\r\n  line one\r\n  line two\r\n")


def test_file_with_no_trailing_newline_keeps_that_state(tmp_workspace: Workspace) -> None:
    write_raw(
        tasks_file(tmp_workspace),
        "- [ ] call the vendor <!-- id:t_a1b2 -->",
        newline="\n",
    )

    set_task_body(tmp_workspace, "t_a1b2", "a detail")

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert not text.endswith("\n")
    assert text == "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  a detail"


def test_removing_a_body_that_was_the_last_content_restores_no_trailing_newline(
    tmp_workspace: Workspace,
) -> None:
    write_raw(
        tasks_file(tmp_workspace),
        "- [ ] call the vendor <!-- id:t_a1b2 -->\n\n  a detail",
        newline="\n",
    )

    set_task_body(tmp_workspace, "t_a1b2", "")

    with open(tmp_workspace.tasks_file, encoding="utf-8", newline="") as fh:
        text = fh.read()
    assert text == "- [ ] call the vendor <!-- id:t_a1b2 -->"


def test_non_ascii_body_round_trips(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")
    body = "Café review — 日本語のメモ 🎉"

    set_task_body(tmp_workspace, "t_a1b2", body)

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []
    assert tasks[0].body == body


def test_unknown_id_raises_not_found_error(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")
    before = tasks_file(tmp_workspace).read_bytes()

    with pytest.raises(NotFoundError):
        set_task_body(tmp_workspace, "t_zzzz", "anything")

    assert tasks_file(tmp_workspace).read_bytes() == before


def test_duplicated_id_raises_usage_error_naming_both_lines(
    tmp_workspace: Workspace,
) -> None:
    write_tasks(
        tmp_workspace,
        "- [ ] first <!-- id:t_dupe -->\n- [ ] second <!-- id:t_dupe -->\n",
    )
    before = tasks_file(tmp_workspace).read_bytes()

    with pytest.raises(UsageError, match="lines 1 and 2"):
        set_task_body(tmp_workspace, "t_dupe", "anything")

    assert tasks_file(tmp_workspace).read_bytes() == before


def test_unwritable_file_raises_workspace_error(tmp_workspace: Workspace) -> None:
    write_tasks(tmp_workspace, "- [ ] call the vendor <!-- id:t_a1b2 -->\n")
    path = tasks_file(tmp_workspace)
    original_dir_mode = path.parent.stat().st_mode

    os.chmod(path.parent, stat.S_IREAD | stat.S_IEXEC)
    try:
        with pytest.raises(WorkspaceError):
            set_task_body(tmp_workspace, "t_a1b2", "a new detail")
    finally:
        os.chmod(path.parent, original_dir_mode)
