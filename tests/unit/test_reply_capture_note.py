"""The status wording for a reply's capture result (contracts/reply-capture.md §4).

Pure enough to test without an app: `_reply_capture_note` maps a `ReplyCapture` to
the note and whether it carries the `⚠` marker. The marker is the point -- a
successful capture is news, not a warning, and prefixing it teaches the user to
read `⚠` as noise.
"""

from __future__ import annotations

from pathlib import Path

from choom.core.models import ReplyCapture, ScanWarning, Task
from choom.tui.edit_screen import _reply_capture_note


def _task(task_id: str) -> Task:
    return Task(id=task_id, text="something", done=False, type="", tags=(), created=None, line=0)


def _warning(message: str) -> ScanWarning:
    return ScanWarning(path=Path("tasks.md"), reason="reply_capture_failed", message=message)


def test_no_eligible_lines_says_nothing_at_all() -> None:
    note, warn = _reply_capture_note(ReplyCapture(text="prose", tasks=(), warnings=()))
    assert note is None
    assert warn is False


def test_one_capture_is_singular_and_not_a_warning() -> None:
    note, warn = _reply_capture_note(
        ReplyCapture(text="x", tasks=(_task("task_a1b2"),), warnings=())
    )
    assert note == "1 task captured"
    assert warn is False


def test_several_captures_are_plural_and_not_a_warning() -> None:
    note, warn = _reply_capture_note(
        ReplyCapture(text="x", tasks=(_task("task_a1b2"), _task("task_c3d4")), warnings=())
    )
    assert note == "2 tasks captured"
    assert warn is False


def test_one_capture_beside_a_failure_still_reads_singular() -> None:
    # The partial-failure branch composes its own count; without sharing the
    # singular/plural rule it renders "1 tasks captured".
    note, warn = _reply_capture_note(
        ReplyCapture(
            text="x",
            tasks=(_task("task_a1b2"),),
            warnings=(_warning("tasks.md could not be written"),),
        )
    )
    assert note == "1 task captured; 1 could not be: tasks.md could not be written"
    assert warn is True


def test_partial_failure_names_the_first_reason_and_warns() -> None:
    note, warn = _reply_capture_note(
        ReplyCapture(
            text="x",
            tasks=(_task("task_a1b2"), _task("task_c3d4")),
            warnings=(_warning("first reason"), _warning("second reason")),
        )
    )
    assert note == "2 tasks captured; 2 could not be: first reason"
    assert warn is True


def test_total_failure_is_the_reason_alone_and_warns() -> None:
    note, warn = _reply_capture_note(
        ReplyCapture(text="x", tasks=(), warnings=(_warning("a description is required"),))
    )
    assert note == "a description is required"
    assert warn is True
