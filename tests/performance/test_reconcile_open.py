from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pytest

from endpaper.core import mirrors as mirrors_module
from endpaper.core.mirrors import reconcile_on_open
from endpaper.core.models import Workspace
from endpaper.core.tasks import render_task_line
from endpaper.core.workspace import init_workspace

_SOURCE = Path("meetings/2026/07/2026-07-28-q3-planning.md")

#: Several years of daily task capture: ~4 tasks/day * 365 * 4 years.
_TASK_COUNT = 5840


def _build_large_tasks_file(workspace: Workspace) -> str:
    lines = []
    day = date(2022, 1, 1)
    target_id = ""
    for i in range(_TASK_COUNT):
        task_id = f"task_{i:05x}"
        is_target = i == _TASK_COUNT // 2
        if is_target:
            target_id = task_id
        lines.append(
            render_task_line(
                f"do the thing number {i}",
                id=task_id,
                type="followup",
                created=day,
                done=is_target,  # the mirror below reads open -- a real correction
            )
        )
    text = "\n".join(lines) + "\n"
    workspace.tasks_file.write_text(text, encoding="utf-8")
    return target_id


@pytest.mark.performance
def test_reconcile_on_open_stays_under_50ms(tmp_path: Path) -> None:
    workspace = init_workspace(tmp_path).workspace
    target_id = _build_large_tasks_file(workspace)

    document_text = f"- [ ] [call Terry](../../../tasks.md#{target_id})\n" + (
        "Some ordinary prose about the meeting.\n" * 200
    )

    start = time.perf_counter()
    report = reconcile_on_open(workspace, document_text, source=workspace.root / _SOURCE)
    elapsed = time.perf_counter() - start

    assert report.text != document_text  # the task is done; the mirror gets corrected
    assert f"[x] [call Terry](../../../tasks.md#{target_id})" in report.text
    assert elapsed < 0.05, f"reconcile_on_open took {elapsed:.3f}s, budget is 0.05s (SC-008)"


@pytest.mark.performance
def test_a_document_with_no_mirrors_never_reads_tasks_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = init_workspace(tmp_path).workspace
    _build_large_tasks_file(workspace)

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("load_tasks must not be called when the document has no mirrors")

    monkeypatch.setattr(mirrors_module, "load_tasks", _boom)

    document_text = "Just some ordinary prose.\n\nNo checkboxes, no links.\n" * 50
    report = reconcile_on_open(workspace, document_text, source=workspace.root / _SOURCE)

    assert report.text is document_text
