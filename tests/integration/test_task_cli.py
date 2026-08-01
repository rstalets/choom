from __future__ import annotations

import json
import os
import re
import time
from datetime import date
from pathlib import Path

import pytest

_ID_PATTERN = re.compile(r"^task_[0-9a-f]{4}$")


def test_task_add_appends_one_line_with_id_type_tag_and_today(cli) -> None:
    result = cli(
        "task", "add", "send the vendor comparison", "--type", "followup", "--tag", "procurement"
    )
    assert result.exit_code == 0

    task_id = result.out
    assert _ID_PATTERN.match(task_id)

    text = cli.read("tasks.md")
    assert text.count("\n") == text.count("- [")
    assert "send the vendor comparison" in text
    assert f"id:{task_id}" in text
    assert "type:followup" in text
    assert "tags:procurement" in text
    assert f"created:{date.today().isoformat()}" in text


def test_task_add_leaves_pre_existing_prose_unchanged(cli) -> None:
    (cli.root / "tasks.md").write_text(
        "# My tasks\n\nSome notes.\n", encoding="utf-8", newline="\n"
    )

    cli("task", "add", "buy milk")

    text = cli.read("tasks.md")
    assert text.startswith("# My tasks\n\nSome notes.\n")
    assert "buy milk" in text


def test_task_add_recreates_deleted_tasks_file(cli) -> None:
    tasks_path = cli.root / "tasks.md"
    if tasks_path.exists():
        tasks_path.unlink()
    assert not tasks_path.exists()

    result = cli("task", "add", "buy milk")
    assert result.exit_code == 0
    assert tasks_path.is_file()
    assert "buy milk" in cli.read("tasks.md")


def test_repeated_tag_preserves_order_and_dedupes(cli) -> None:
    cli("task", "add", "vendor renewal", "--tag", "legal", "--tag", "procurement", "--tag", "legal")

    text = cli.read("tasks.md")
    assert "tags:legal,procurement" in text


def test_quoted_hash_tag_is_extracted_from_description(cli) -> None:
    cli("task", "add", "vendor call #procurement #legal")

    text = cli.read("tasks.md")
    assert "vendor call <!--" in text
    assert "tags:procurement,legal" in text
    assert "#" not in text.split("vendor call")[0] + text.split("vendor call")[1].split("<!--")[0]


def test_empty_after_tag_removal_exits_2_and_leaves_file_untouched(cli) -> None:
    tasks_path = cli.root / "tasks.md"
    before = tasks_path.read_bytes() if tasks_path.exists() else None

    result = cli("task", "add", "#onlytags")
    assert result.exit_code == 2

    after = tasks_path.read_bytes() if tasks_path.exists() else None
    assert before == after


def test_invalid_type_exits_2(cli) -> None:
    result = cli("task", "add", "buy milk", "--type", "../evil")
    assert result.exit_code == 2


def test_invalid_tag_exits_2(cli) -> None:
    result = cli("task", "add", "buy milk", "--tag", "../evil")
    assert result.exit_code == 2


_SEED = (
    "- [ ] one <!-- id:task_0001 created:2026-07-20 -->\n"
    "- [ ] two <!-- id:task_0002 type:followup tags:legal created:2026-07-21 -->\n"
    "- [x] three <!-- id:task_0003 created:2026-07-22 -->\n"
    "- [x] four <!-- id:task_0004 created:2026-07-23 -->\n"
    "- [ ] five <!-- id:task_0005 created:2026-07-19 -->\n"
)

#: Ids whose seeded checkbox is "[x]" -- shared by every case below, since the
#: seed is fixed. Lets each parametrized case assert the state column/field
#: without needing its own bespoke expectation.
_DONE_IDS = {"task_0003", "task_0004"}


def _seed_tasks(cli) -> Path:
    path = cli.root / "tasks.md"
    path.write_text(_SEED, encoding="utf-8", newline="\n")
    return path


# filter_tasks() (src/choom/core/tasks.py) always sorts oldest-first, so every
# case's expected order is fully determined by the seed's `created` dates, not just
# by the case's own filter -- task_0005 (07-19), task_0001 (07-20), task_0002 (07-21),
# task_0003 (07-22), task_0004 (07-23).
_LIST_CASES = [
    pytest.param(
        ["task", "list"],
        ["task_0005", "task_0001", "task_0002"],
        id="default-shows-open-oldest-first",
    ),
    pytest.param(
        ["task", "list", "--all"],
        ["task_0005", "task_0001", "task_0002", "task_0003", "task_0004"],
        id="all-includes-completed",
    ),
    pytest.param(
        ["task", "list", "--all", "--type", "followup", "--tag", "legal"],
        ["task_0002"],
        id="type-and-tag-are-conjunctive",
    ),
    pytest.param(
        ["task", "list", "--done"], ["task_0003", "task_0004"], id="done-shows-completed-only"
    ),
    pytest.param(
        ["task", "list", "--done", "--json"],
        ["task_0003", "task_0004"],
        id="done-json-matches-table",
    ),
    pytest.param(
        ["task", "list", "--done", "--all"], ["task_0003", "task_0004"], id="done-wins-over-all"
    ),
]


@pytest.mark.parametrize("flags, expected_ids", _LIST_CASES)
def test_task_list_filters_and_orders(cli, flags: list[str], expected_ids: list[str]) -> None:
    _seed_tasks(cli)

    result = cli(*flags)
    assert result.exit_code == 0

    if "--json" in flags:
        rows = json.loads(result.out)
        ids = [row["id"] for row in rows]
        assert all(row["done"] == (row["id"] in _DONE_IDS) for row in rows)
    else:
        lines = result.out.splitlines()
        ids = [line.split("\t")[0] for line in lines]
        for line in lines:
            task_id, state = line.split("\t")[:2]
            assert state == ("done" if task_id in _DONE_IDS else "open")

    assert ids == expected_ids


def test_list_on_missing_tasks_file_lists_nothing_exits_0(cli) -> None:
    (cli.root / "tasks.md").unlink()

    result = cli("task", "list")
    assert result.exit_code == 0
    assert result.out == ""


def test_list_checkbox_free_file_lists_nothing(cli) -> None:
    (cli.root / "tasks.md").write_text("# notes\n\nno checkboxes here\n", encoding="utf-8")

    result = cli("task", "list")
    assert result.exit_code == 0
    assert result.out == ""


def test_task_done_and_undone_change_the_file(cli) -> None:
    _seed_tasks(cli)

    assert cli("task", "done", "task_0001").exit_code == 0
    text = cli.read("tasks.md")
    assert "- [x] one <!-- id:task_0001 created:2026-07-20 -->\n" in text

    assert cli("task", "undone", "task_0003").exit_code == 0
    text = cli.read("tasks.md")
    assert "- [ ] three <!-- id:task_0003 created:2026-07-22 -->\n" in text


def test_noop_toggle_exits_0_without_writing(cli) -> None:
    tasks_path = _seed_tasks(cli)
    before_mtime = os.stat(tasks_path).st_mtime_ns
    time.sleep(0.01)

    result = cli("task", "undone", "task_0001")
    assert result.exit_code == 0
    assert os.stat(tasks_path).st_mtime_ns == before_mtime


def test_unknown_id_exits_1_changes_nothing(cli) -> None:
    tasks_path = _seed_tasks(cli)
    before = tasks_path.read_bytes()

    result = cli("task", "done", "task_zzzz")
    assert result.exit_code == 1
    assert "no task with id" in result.err
    assert tasks_path.read_bytes() == before


def test_task_show_prints_the_body_in_human_form(cli) -> None:
    cli("task", "add", "call the vendor", "--type", "followup", "--tag", "procurement")
    tasks_path = cli.root / "tasks.md"
    text = tasks_path.read_text(encoding="utf-8")
    task_id = re.search(r"id:(task_[0-9a-f]{4})", text).group(1)  # type: ignore[union-attr]
    tasks_path.write_text(text + "\n  Need the Q3 comparison.\n", encoding="utf-8")

    result = cli("task", "show", task_id)

    assert result.exit_code == 0
    lines = result.out.splitlines()
    assert lines[0].split("\t")[0] == task_id
    assert "Need the Q3 comparison." in result.out


def test_task_show_with_no_body_prints_the_summary_line_alone(cli) -> None:
    result = cli("task", "add", "buy milk")
    task_id = result.out

    result = cli("task", "show", task_id)

    assert result.exit_code == 0
    assert result.out.count("\n") == 0
    assert result.out.split("\t")[0] == task_id


def test_task_done_leaves_the_body_intact(cli) -> None:
    result = cli("task", "add", "call the vendor")
    task_id = result.out
    tasks_path = cli.root / "tasks.md"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8") + "\n  Need the Q3 comparison.\n",
        encoding="utf-8",
    )

    assert cli("task", "done", task_id).exit_code == 0

    text = cli.read("tasks.md")
    assert "[x] call the vendor" in text
    assert "Need the Q3 comparison." in text


def test_duplicated_id_exits_2_naming_both_lines(cli) -> None:
    (cli.root / "tasks.md").write_text(
        "- [ ] first <!-- id:task_dupe -->\n- [ ] second <!-- id:task_dupe -->\n",
        encoding="utf-8",
    )

    result = cli("task", "done", "task_dupe")
    assert result.exit_code == 2
    assert "lines 1 and 2" in result.err
