from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pytest

from endpaper.core import mirrors as mirrors_module
from endpaper.core.mirrors import reconcile_on_open
from endpaper.core.models import Workspace
from endpaper.core.tasks import load_tasks, render_task_line
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
def test_reconcile_on_open_costs_little_more_than_the_read_it_must_do(tmp_path: Path) -> None:
    """SC-008 budgets reconcile-on-open at under 50 ms on a workspace holding
    several years of documents. That number is a claim about a user's machine,
    and it holds -- this measures ~5 ms locally, serially.

    It is not a claim this test can assert directly. CI runs `pytest -n auto` on
    a shared runner, so every timing here competes with the rest of the suite for
    CPU; the same code measured 0.055 s and 0.174 s on two runners of one build.
    Asserting the product budget against that measures the runner, not the code,
    and it went red on exactly that.

    So the sharp assertion is relative. Reconciling reads one file -- tasks.md --
    and does a little string work on a document already in memory, so its cost
    should sit within a small multiple of that read alone, measured in the same
    process under the same load. The regression this exists to catch is
    reconcile scanning the workspace instead of reading one file, which is
    orders of magnitude, not a fraction. A slow runner slows both halves and the
    ratio holds.
    """
    workspace = init_workspace(tmp_path).workspace
    target_id = _build_large_tasks_file(workspace)

    document_text = f"- [ ] [call Terry](../../../tasks.md#{target_id})\n" + (
        "Some ordinary prose about the meeting.\n" * 200
    )

    load_tasks(workspace)  # warm the page cache so the baseline is CPU, not first-read I/O
    start = time.perf_counter()
    load_tasks(workspace)
    baseline = time.perf_counter() - start

    start = time.perf_counter()
    report = reconcile_on_open(workspace, document_text, source=workspace.root / _SOURCE)
    elapsed = time.perf_counter() - start

    assert report.text != document_text  # the task is done; the mirror gets corrected
    assert f"[x] [call Terry](../../../tasks.md#{target_id})" in report.text

    # The 10 ms floor keeps a fast, noisy baseline from making the bound absurd.
    ceiling = baseline * 3 + 0.010
    assert elapsed < ceiling, (
        f"reconcile_on_open took {elapsed:.3f}s against a {baseline:.3f}s bare "
        f"load_tasks on the same file -- more than one file read's worth of work"
    )
    # Absolute backstop, at the same order as the workspace-wide link scan's
    # budget. Loose enough for the slowest runner; tight enough that a scan of
    # the whole workspace could never pass it.
    assert elapsed < 0.5, f"reconcile_on_open took {elapsed:.3f}s"


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
