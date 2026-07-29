from __future__ import annotations

import time
from pathlib import Path

from endpaper.core.meetings import filter_meetings, match_meeting, scan_meetings
from endpaper.core.models import MeetingFilter
from tests.fixtures.generate import generate


def test_filter_meetings_1000_completes_under_100ms(tmp_path: Path) -> None:
    workspace = generate(tmp_path, 1000)
    meetings, _ = scan_meetings(workspace)

    start = time.perf_counter()
    filtered = filter_meetings(meetings, MeetingFilter(type="standup"))
    elapsed = time.perf_counter() - start

    assert filtered
    assert elapsed < 0.1


def test_live_filter_predicate_1000_completes_under_100ms(tmp_path: Path) -> None:
    workspace = generate(tmp_path, 1000)
    meetings, _ = scan_meetings(workspace)

    start = time.perf_counter()
    visible = [m for m in meetings if match_meeting(m, "generated")]
    elapsed = time.perf_counter() - start

    assert len(visible) == 1000
    assert elapsed < 0.1
