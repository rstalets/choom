from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pytest

from choom.core import tasks as tasks_module
from choom.core.models import Workspace
from choom.core.task_store import load_task_store
from choom.core.tasks import load_tasks
from choom.core.workspace import init_workspace


def _populate_done_store(tmp_path: Path, *, days: int, records_per_day: int) -> Workspace:
    workspace = init_workspace(tmp_path).workspace
    start = date(2023, 1, 1)
    for day_offset in range(days):
        day = start + timedelta(days=day_offset)
        lines = [
            f"- [x] generated task {day_offset}-{i} "
            f"<!-- id:task_{day_offset:04x}{i:02x} created:{day.isoformat()} "
            f"completed:{day.isoformat()} -->\n"
            for i in range(records_per_day)
        ]
        path = workspace.done_dir / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}-done.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return workspace


@pytest.mark.performance
def test_default_task_list_opens_exactly_one_file_with_365_done_files_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-003: `choom task list` with no flags -- `load_tasks` -- opens
    exactly one file, whatever the size of the done store. Counted, not
    timed: a count cannot flake (research R12, matching the technique
    `tests/performance/test_reconcile_open.py` established)."""
    workspace = _populate_done_store(tmp_path, days=365, records_per_day=3)
    workspace.tasks_file.write_text(
        "- [ ] one open task <!-- id:task_open -->\n", encoding="utf-8", newline="\n"
    )

    calls = 0
    real_read_text = tasks_module._read_text

    def _counting_read_text(path: Path) -> str:
        nonlocal calls
        calls += 1
        return real_read_text(path)

    monkeypatch.setattr(tasks_module, "_read_text", _counting_read_text)

    tasks, warnings = load_tasks(workspace)

    assert calls == 1, f"load_tasks read {calls} files with 365 done-store files present, want 1"
    assert warnings == []
    assert len(tasks) == 1


@pytest.mark.performance
def test_whole_store_read_stays_under_500ms_for_1000_files_5000_records(
    tmp_path: Path,
) -> None:
    """SC-005: the union view -- `task list --done`/`--all`, and every id
    resolution that has to escalate -- stays under 500 ms even at 1,000
    done-store day files holding 5,000 records. Best-of-5, the same
    single-sample-flakiness fix issue #84 applies everywhere (research R12,
    matching `test_task_scan.py`'s own technique)."""
    workspace = _populate_done_store(tmp_path, days=1000, records_per_day=5)

    samples = []
    for _ in range(5):
        start = time.perf_counter()
        tasks, warnings = load_task_store(workspace)
        samples.append(time.perf_counter() - start)

    assert len(tasks) == 5000
    assert warnings == []
    assert min(samples) < 0.5, f"load_task_store samples: {[f'{s * 1000:.1f}ms' for s in samples]}"
