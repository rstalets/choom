from __future__ import annotations

import time
from pathlib import Path

from endpaper.core.tasks import load_tasks
from endpaper.core.workspace import init_workspace


def test_load_tasks_on_1000_tasks_completes_under_1_second(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path)
    lines = [
        f"- [{'x' if i % 3 == 0 else ' '}] generated task {i} "
        f"<!-- id:t_{i:04x} type:followup tags:perf created:2026-01-01 -->\n"
        for i in range(1000)
    ]
    workspace.tasks_file.write_text("".join(lines), encoding="utf-8", newline="\n")

    start = time.perf_counter()
    tasks, warnings = load_tasks(workspace)
    elapsed = time.perf_counter() - start

    assert len(tasks) == 1000
    assert warnings == []
    assert elapsed < 1.0
