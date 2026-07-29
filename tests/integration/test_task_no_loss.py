from __future__ import annotations

import random

from endpaper.core.models import Workspace
from endpaper.core.tasks import add_task, load_tasks, set_task_state


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
