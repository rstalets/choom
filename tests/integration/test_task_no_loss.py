from __future__ import annotations

import random

from choom.core.models import Workspace
from choom.core.tasks import add_task, load_tasks, set_task_body, set_task_state


def test_thousand_random_operations_lose_nothing(tmp_workspace: Workspace) -> None:
    rng = random.Random(20260728)
    known_ids: list[str] = []
    expected_text_by_id: dict[str, str] = {}
    non_task_prelude = "# Tasks\n\nA line of prose that must never be touched.\n"
    tmp_workspace.tasks_file.write_text(non_task_prelude, encoding="utf-8", newline="\n")

    for i in range(1000):
        op = rng.choice(["add", "complete", "reopen"]) if known_ids else "add"
        if op == "add":
            text = f"task number {i}"
            task = add_task(tmp_workspace, text)
            known_ids.append(task.id)  # type: ignore[arg-type]
            expected_text_by_id[task.id] = text  # type: ignore[index]
        else:
            task_id = rng.choice(known_ids)
            set_task_state(tmp_workspace, task_id, done=(op == "complete"))

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []
    assert len(tasks) == len(known_ids)

    found_texts = {t.id: t.text for t in tasks}
    for task_id, text in expected_text_by_id.items():
        assert found_texts[task_id] == text

    text_on_disk = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text_on_disk.startswith(non_task_prelude)


def test_body_bearing_fixtures_survive_random_operations(tmp_workspace: Workspace) -> None:
    """SC-004 under load: irregular indentation, a fenced code block, and
    non-ASCII text all round-trip through interleaved body writes, checkbox
    toggles, and new tasks -- with no line lost or reordered anywhere else in
    the file."""
    rng = random.Random(20260731)
    known_ids: list[str] = []
    expected_body_by_id: dict[str, str] = {}
    non_task_prelude = "# Tasks\n\nA line of prose that must never be touched.\n"
    tmp_workspace.tasks_file.write_text(non_task_prelude, encoding="utf-8", newline="\n")

    # Each fixture round-trips idempotently through `set_task_body`: a body with
    # a *uniform* leading prefix on every line would be indistinguishable from
    # the indent the writer itself adds, and get stripped as "common" on the
    # next read -- that hand-written-indentation case is covered directly, on
    # a file `set_task_body` never touches, in test_task_handedit.py.
    fixture_bodies = [
        "a plain multi-line detail\n\nwith a second paragraph",
        "```python\ndef f():\n    return 1\n```",
        "Café review — 日本語のメモ 🎉",
        "",
    ]

    for i in range(500):
        op = rng.choice(["add", "complete", "reopen", "set_body"]) if known_ids else "add"
        if op == "add":
            text = f"task number {i}"
            task = add_task(tmp_workspace, text)
            known_ids.append(task.id)  # type: ignore[arg-type]
            expected_body_by_id[task.id] = ""  # type: ignore[index]
        elif op == "set_body":
            task_id = rng.choice(known_ids)
            body = rng.choice(fixture_bodies)
            set_task_body(tmp_workspace, task_id, body)
            expected_body_by_id[task_id] = body
        else:
            task_id = rng.choice(known_ids)
            set_task_state(tmp_workspace, task_id, done=(op == "complete"))

    tasks, warnings = load_tasks(tmp_workspace)
    assert warnings == []
    assert len(tasks) == len(known_ids)

    found_bodies = {t.id: t.body for t in tasks}
    for task_id, body in expected_body_by_id.items():
        assert found_bodies[task_id] == body

    text_on_disk = tmp_workspace.tasks_file.read_text(encoding="utf-8")
    assert text_on_disk.startswith(non_task_prelude)
