from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest

from choom.core.documents import scan_month
from choom.core.meetings import MEETINGS
from choom.core.models import YearMonth
from tests.fixtures.generate import generate


@pytest.mark.performance
def test_refresh_tick_read_stays_inside_one_frame_on_a_representative_month(
    tmp_path: Path,
) -> None:
    """research R5: the periodic refresh's read runs on Textual's main thread,
    so its cost is frame budget, not just CPU -- a tick landing during a held
    movement key costs a frame rather than background CPU. Measured on the
    reference machine, `scan_month` runs at roughly 0.14 ms/document (a
    50-document month at ~7.2 ms, a 200-document one at ~28.5 ms -- see
    research.md's R5 table). 50 documents is representative of a busy month
    (issue #51's own reproduction used 200, well past this ceiling); the
    crossover into "can drop a frame" sits around 100 documents in the
    displayed month. Breaching this ceiling -- set generously above the
    reference machine's ~15 ms (one 60 fps frame) to absorb slower CI
    hardware while staying well under the SC-003 200 ms list-load budget --
    is the stated trigger to move the tick's read to a worker thread
    (research R5), not a reason to shorten REFRESH_SECONDS or skip reads."""
    now = datetime.now()
    workspace = generate(tmp_path, 50, spread_months=2, now=now, current_month_count=50)

    start = time.perf_counter()
    documents, warnings = scan_month(workspace, MEETINGS, YearMonth(now.year, now.month))
    elapsed = time.perf_counter() - start

    assert len(documents) == 50
    assert warnings == []
    assert elapsed < 0.05
