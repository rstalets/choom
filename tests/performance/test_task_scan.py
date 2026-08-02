from __future__ import annotations

import time
from pathlib import Path

import pytest

from choom.core.tasks import load_tasks
from choom.core.workspace import init_workspace


@pytest.mark.performance
def test_load_tasks_on_1000_tasks_completes_under_1_second(tmp_path: Path) -> None:
    """Best-of-5, same technique as
    test_refresh_tick.py::test_refresh_tick_read_stays_inside_one_frame_on_a_representative_month
    (established in 016656e): applied here preventively (issue #84) even
    though this test hasn't itself been reported flaky -- it has the same
    single-sample, bare-absolute-budget shape that flaked on test_scan.py in
    PR #83, and #84's whole point is to fix that shape everywhere it appears,
    not just where it has already gone red. load_tasks is a read-only parse
    of a file nothing else in the test mutates, so repeated calls are safe.
    """
    workspace = init_workspace(tmp_path).workspace
    lines = [
        f"- [{'x' if i % 3 == 0 else ' '}] generated task {i} "
        f"<!-- id:task_{i:04x} type:followup tags:perf created:2026-01-01 -->\n"
        for i in range(1000)
    ]
    workspace.tasks_file.write_text("".join(lines), encoding="utf-8", newline="\n")

    samples = []
    for _ in range(5):
        start = time.perf_counter()
        tasks, warnings = load_tasks(workspace)
        samples.append(time.perf_counter() - start)

    assert len(tasks) == 1000
    assert warnings == []
    assert min(samples) < 1.0, f"load_tasks samples: {[f'{s * 1000:.1f}ms' for s in samples]}"
