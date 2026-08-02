from __future__ import annotations

import time
from pathlib import Path

import pytest

from choom.core.meetings import scan_meetings
from choom.core.notes import scan_notes
from tests.fixtures.generate import generate, generate_notes


@pytest.mark.performance
def test_scan_both_collections_at_mount_completes_under_2_seconds(tmp_path: Path) -> None:
    """SC-004/SC-005: both collections are scanned at TUI mount, so the doubled
    2,000-file walk must stay inside the same 2-second budget as a single
    1,000-file scan.

    Best-of-5, same technique as
    test_refresh_tick.py::test_refresh_tick_read_stays_inside_one_frame_on_a_representative_month
    (established in 016656e): a single perf_counter() sample is exposed to one
    bad scheduler tick on a shared, oversubscribed CI runner -- this flaked at
    2.1836s against the 2.0s budget on `test (3.11)` while `test (3.13)` passed
    on the same commit, then ran clean on rerun (PR #83, issue #84). A real
    regression -- the walk gaining a quadratic step, or re-reading a file --
    slows every sample; a transient scheduling hiccup only slows one, so
    taking the minimum removes the latter without hiding the former. Repeated
    calls are safe: scan_meetings/scan_notes are read-only walks and nothing
    else mutates the workspace during the test.
    """
    workspace = generate(tmp_path, 1000)
    generate_notes(workspace.root, 1000)

    samples = []
    for _ in range(5):
        start = time.perf_counter()
        meetings, meeting_warnings = scan_meetings(workspace)
        notes, note_warnings = scan_notes(workspace)
        samples.append(time.perf_counter() - start)

    assert len(meetings) == 1000
    assert len(notes) == 1000
    assert meeting_warnings == []
    assert note_warnings == []
    assert min(samples) < 2.0, f"scan samples: {[f'{s * 1000:.1f}ms' for s in samples]}"
