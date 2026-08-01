from __future__ import annotations

from datetime import date

import pytest

from endpaper.core.errors import UsageError
from endpaper.core.tasks import render_task_line


def test_field_order_and_all_present() -> None:
    line = render_task_line(
        "send the vendor comparison",
        id="task_a1b2",
        type="followup",
        tags=("procurement", "q3"),
        created=date(2026, 7, 28),
    )
    assert line == (
        "- [ ] send the vendor comparison "
        "<!-- id:task_a1b2 type:followup tags:procurement,q3 created:2026-07-28 -->"
    )


def test_done_checkbox() -> None:
    line = render_task_line("book the room", id="task_9f0e", created=date(2026, 7, 27), done=True)
    assert line == "- [x] book the room <!-- id:task_9f0e created:2026-07-27 -->"


def test_omits_empty_type_and_tags() -> None:
    line = render_task_line("buy milk", id="task_5c31")
    assert line == "- [ ] buy milk <!-- id:task_5c31 -->"
    assert "type:" not in line
    assert "tags:" not in line
    assert "created:" not in line


def test_empty_text_raises_usage_error() -> None:
    with pytest.raises(UsageError):
        render_task_line("   ", id="task_5c31")


def test_field_order_is_id_type_tags_links_created() -> None:
    line = render_task_line(
        "call Terry",
        id="task_a1b2",
        type="followup",
        tags=("procurement",),
        links=("meeting_20260728_a1b2c3d4",),
        created=date(2026, 7, 28),
    )
    assert line == (
        "- [ ] call Terry <!-- id:task_a1b2 type:followup tags:procurement "
        "links:meeting_20260728_a1b2c3d4 created:2026-07-28 -->"
    )


def test_multiple_links_are_comma_joined() -> None:
    line = render_task_line("call Terry", id="task_a1b2", links=("meeting_1", "note_2"))
    assert line == "- [ ] call Terry <!-- id:task_a1b2 links:meeting_1,note_2 -->"


def test_empty_links_is_omitted() -> None:
    line = render_task_line("buy milk", id="task_5c31")
    assert "links:" not in line
