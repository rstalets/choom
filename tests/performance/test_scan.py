from __future__ import annotations

import time
from pathlib import Path

import pytest

from endpaper.core.meetings import scan_meetings
from endpaper.core.notes import scan_notes
from tests.fixtures.generate import generate, generate_notes


@pytest.mark.performance
def test_scan_both_collections_at_mount_completes_under_2_seconds(tmp_path: Path) -> None:
    """SC-004/SC-005: both collections are scanned at TUI mount, so the doubled
    2,000-file walk must stay inside the same 2-second budget as a single
    1,000-file scan."""
    workspace = generate(tmp_path, 1000)
    generate_notes(workspace.root, 1000)

    start = time.perf_counter()
    meetings, meeting_warnings = scan_meetings(workspace)
    notes, note_warnings = scan_notes(workspace)
    elapsed = time.perf_counter() - start

    assert len(meetings) == 1000
    assert len(notes) == 1000
    assert meeting_warnings == []
    assert note_warnings == []
    assert elapsed < 2.0
