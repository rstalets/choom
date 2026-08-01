from __future__ import annotations

import time
from pathlib import Path

import pytest

from choom.core.meetings import filter_meetings, match_meeting, scan_meetings
from choom.core.models import MeetingFilter
from tests.fixtures.generate import generate


@pytest.mark.performance
def test_filter_1000_meetings_completes_under_100ms(tmp_path: Path) -> None:
    workspace = generate(tmp_path, 1000)
    meetings, _ = scan_meetings(workspace)

    start = time.perf_counter()
    filtered = filter_meetings(meetings, MeetingFilter(type="standup"))
    elapsed_field_filter = time.perf_counter() - start

    start = time.perf_counter()
    visible = [m for m in meetings if match_meeting(m, "generated")]
    elapsed_live_filter = time.perf_counter() - start

    assert filtered
    assert len(visible) == 1000
    assert elapsed_field_filter < 0.1
    assert elapsed_live_filter < 0.1
