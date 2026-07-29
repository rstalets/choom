from __future__ import annotations

import time
from pathlib import Path

from endpaper.core.meetings import scan_meetings
from tests.fixtures.generate import generate


def test_scan_1000_meetings_completes_under_2_seconds(tmp_path: Path) -> None:
    workspace = generate(tmp_path, 1000)

    start = time.perf_counter()
    meetings, warnings = scan_meetings(workspace)
    elapsed = time.perf_counter() - start

    assert len(meetings) == 1000
    assert warnings == []
    assert elapsed < 2.0
