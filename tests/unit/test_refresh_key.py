"""Unit tests for the periodic-refresh change-detection key (010-read-on-load,
US2, research R4). The key is built from a read result and compared against
the previous render's key -- equal means the tick skips the redraw entirely,
so the key must change exactly when the display would change, and only then.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from choom.core.models import Document, Task
from choom.tui.list_screen import _document_key, _task_key

_DOCUMENT = Document(
    id="meeting_20260801_aaaa",
    path=Path("/vault/meetings/2026/08/2026-08-01-q3-planning.md"),
    title="Q3 planning",
    type="standup",
    tags=("finance",),
    created="2026-08-01T09:00:00",
    updated="2026-08-01T09:00:00",
)

_TASK = Task(
    id="task_aaaa",
    text="call Terry",
    done=False,
    type="errand",
    tags=("home",),
    created=date(2026, 8, 1),
    line=1,
)


def test_identical_document_reads_produce_equal_keys() -> None:
    first = _document_key([_DOCUMENT])
    second = _document_key([replace(_DOCUMENT)])
    assert first == second


def test_identical_task_reads_produce_equal_keys() -> None:
    first = _task_key([_TASK])
    second = _task_key([replace(_TASK)])
    assert first == second


def test_a_changed_document_title_produces_a_different_key() -> None:
    changed = replace(_DOCUMENT, title="Q4 planning")
    assert _document_key([_DOCUMENT]) != _document_key([changed])


def test_a_changed_document_type_produces_a_different_key() -> None:
    changed = replace(_DOCUMENT, type="retro")
    assert _document_key([_DOCUMENT]) != _document_key([changed])


def test_a_changed_document_tag_produces_a_different_key() -> None:
    changed = replace(_DOCUMENT, tags=("finance", "urgent"))
    assert _document_key([_DOCUMENT]) != _document_key([changed])


def test_a_changed_document_updated_timestamp_produces_a_different_key() -> None:
    changed = replace(_DOCUMENT, updated="2026-08-01T10:00:00")
    assert _document_key([_DOCUMENT]) != _document_key([changed])


def test_a_changed_task_done_state_produces_a_different_key() -> None:
    changed = replace(_TASK, done=True)
    assert _task_key([_TASK]) != _task_key([changed])


def test_reordering_with_no_content_change_is_still_a_different_key() -> None:
    """Order is rendered (row position), so a re-sort with identical content
    per row must still register as a change."""
    other = replace(_DOCUMENT, id="meeting_20260801_bbbb", created="2026-08-02T09:00:00")
    forward = _document_key([_DOCUMENT, other])
    backward = _document_key([other, _DOCUMENT])
    assert forward != backward


def test_an_empty_read_produces_an_equal_key_to_another_empty_read() -> None:
    assert _document_key([]) == _document_key([])
    assert _task_key([]) == _task_key([])
