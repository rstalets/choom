from __future__ import annotations

import time
from pathlib import Path

import pytest

from choom.core.meetings import filter_meetings, match_meeting, scan_meetings
from choom.core.models import MeetingFilter
from tests.fixtures.generate import generate


@pytest.mark.performance
def test_filter_1000_meetings_completes_under_100ms(tmp_path: Path) -> None:
    """Best-of-5 on each of the two filter paths, same technique as
    test_refresh_tick.py::test_refresh_tick_read_stays_inside_one_frame_on_a_representative_month
    (established in 016656e): applied here preventively (issue #84) even
    though this test hasn't itself been reported flaky -- same single-sample,
    bare-absolute-budget shape that flaked on test_scan.py in PR #83. Both
    filter_meetings and the live match_meeting comprehension are pure reads
    over the same in-memory list, so repeated calls are safe.
    """
    workspace = generate(tmp_path, 1000)
    meetings, _ = scan_meetings(workspace)

    field_samples = []
    filtered: list = []
    for _ in range(5):
        start = time.perf_counter()
        filtered = filter_meetings(meetings, MeetingFilter(type="standup"))
        field_samples.append(time.perf_counter() - start)

    live_samples = []
    visible: list = []
    for _ in range(5):
        start = time.perf_counter()
        visible = [m for m in meetings if match_meeting(m, "generated")]
        live_samples.append(time.perf_counter() - start)

    assert filtered
    assert len(visible) == 1000
    assert min(field_samples) < 0.1, (
        f"field filter samples: {[f'{s * 1000:.1f}ms' for s in field_samples]}"
    )
    assert min(live_samples) < 0.1, (
        f"live filter samples: {[f'{s * 1000:.1f}ms' for s in live_samples]}"
    )
