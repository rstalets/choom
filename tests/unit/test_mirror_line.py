from __future__ import annotations

from datetime import date
from pathlib import Path

from choom.core.mirrors import mirror_line
from choom.core.models import Task

_TASKS_FILE = Path("/ws/tasks.md")


def _task(**overrides: object) -> Task:
    defaults: dict[str, object] = dict(
        id="task_a1b2",
        text="call Terry about the renewal",
        done=False,
        type="followup",
        tags=("procurement",),
        created=date(2026, 7, 30),
        line=1,
    )
    defaults.update(overrides)
    return Task(**defaults)  # type: ignore[arg-type]


def test_destination_from_a_meeting_three_levels_deep() -> None:
    source = Path("/ws/meetings/2026/07/2026-07-28-q3-planning.md")
    line = mirror_line(_task(), source=source, tasks_file=_TASKS_FILE)
    assert line == "- [ ] [call Terry about the renewal](../../../tasks.md#task_a1b2)"


def test_destination_from_a_daily_note_four_levels_deep() -> None:
    source = Path("/ws/notes/daily/2026/07/2026-07-31.md")
    line = mirror_line(_task(), source=source, tasks_file=_TASKS_FILE)
    assert line == "- [ ] [call Terry about the renewal](../../../../tasks.md#task_a1b2)"


def test_destination_from_a_document_outside_the_dated_layout() -> None:
    source = Path("/ws/notes/architecture-decisions.md")
    line = mirror_line(_task(), source=source, tasks_file=_TASKS_FILE)
    assert line == "- [ ] [call Terry about the renewal](../tasks.md#task_a1b2)"


def test_no_relative_prefix_is_hardcoded() -> None:
    # A document right next to tasks.md needs no "../" at all.
    source = Path("/ws/scratch.md")
    line = mirror_line(_task(), source=source, tasks_file=_TASKS_FILE)
    assert "../" not in line
    assert line == "- [ ] [call Terry about the renewal](tasks.md#task_a1b2)"


def test_done_task_renders_a_ticked_checkbox() -> None:
    source = Path("/ws/notes/scratch.md")
    line = mirror_line(_task(done=True), source=source, tasks_file=_TASKS_FILE)
    assert line.startswith("- [x] ")
