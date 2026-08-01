from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from choom.core import mirrors as mirrors_module
from choom.core.mirrors import reconcile_on_open
from choom.core.models import ScanWarning, Task, Workspace
from choom.core.tasks import load_tasks, render_task_line
from choom.core.workspace import init_workspace

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


def test_reconcile_on_open_reads_tasks_md_exactly_once_regardless_of_mirror_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-008's actual claim -- reconcile is one file read, not a workspace scan
    and not a read per mirror -- asserted directly by counting the read instead
    of inferring it from wall-clock time.

    The previous version of this test measured `reconcile_on_open` against a
    same-process `load_tasks` baseline (`elapsed < baseline * 3 + 0.010`) to
    correct for CI runner speed. That ratio still occasionally tipped over on a
    noisy shared runner (#63), because two back-to-back `perf_counter()` reads in
    one process can't fully protect against a context switch landing between
    them -- and it was redundant with `test_a_document_with_no_mirrors_never_reads_tasks_md`
    below anyway, which already proves the "no workspace scan" side of the claim
    without timing. This proves the other side -- multiple mirrors still cost
    one read, not N -- the same way: by counting, not timing.
    """
    workspace = init_workspace(tmp_path).workspace
    target_id = _build_large_tasks_file(workspace)

    document_text = (
        f"- [ ] [call Terry](../../../tasks.md#{target_id})\n"
        "- [ ] [an open one](../../../tasks.md#task_00000)\n"
        "- [ ] [another open one](../../../tasks.md#task_00001)\n"
    ) + ("Some ordinary prose about the meeting.\n" * 200)

    calls = 0
    real_load_tasks = load_tasks

    def _counting_load_tasks(
        *args: object, **kwargs: object
    ) -> tuple[list[Task], list[ScanWarning]]:
        nonlocal calls
        calls += 1
        return real_load_tasks(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(mirrors_module, "load_tasks", _counting_load_tasks)

    report = reconcile_on_open(workspace, document_text, source=workspace.root / _SOURCE)

    assert calls == 1, f"reconcile_on_open read tasks.md {calls} times for 3 mirrors, want 1"
    assert report.text != document_text  # the done task's mirror gets corrected
    assert f"[x] [call Terry](../../../tasks.md#{target_id})" in report.text


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
