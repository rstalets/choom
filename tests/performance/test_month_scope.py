from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest

from endpaper.core.documents import scan_month
from endpaper.core.meetings import MEETINGS
from endpaper.core.models import YearMonth
from tests.fixtures.generate import generate, generate_notes


@contextmanager
def _counting_read_text(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Path]]:
    """Wrap `Path.read_text` to record every path whose contents were opened, so a
    test can assert exactly which files a scoped read touched (research R11)."""
    read_paths: list[Path] = []
    original_read_text = Path.read_text

    def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        read_paths.append(self)
        return original_read_text(self, *args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    yield read_paths


def test_opening_collection_reads_only_current_month(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now()
    workspace = generate(tmp_path, 400, spread_months=12, now=now, current_month_count=5)

    current_month = YearMonth(now.year, now.month)
    expected_dir = workspace.meetings_dir / f"{now:%Y}" / f"{now:%m}"

    with _counting_read_text(monkeypatch) as read_paths:
        documents, warnings = scan_month(workspace, MEETINGS, current_month)

    assert warnings == []
    assert len(documents) == 5
    assert read_paths, "expected scan_month to read at least one file"
    assert all(p.parent == expected_dir for p in read_paths)
    assert len(read_paths) == len(documents)


def test_notes_month_scope_also_reads_only_the_current_month(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from endpaper.core.notes import NOTES

    now = datetime.now()
    workspace = generate_notes(tmp_path, 400, spread_months=12, now=now, current_month_count=5)

    current_month = YearMonth(now.year, now.month)
    expected_dir = workspace.notes_dir / f"{now:%Y}" / f"{now:%m}"

    with _counting_read_text(monkeypatch) as read_paths:
        documents, warnings = scan_month(workspace, NOTES, current_month)

    assert warnings == []
    assert len(documents) == 5
    assert all(p.parent == expected_dir for p in read_paths)


def test_filter_reads_each_month_at_most_once_per_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-035: once a filter has loaded every month into the session cache, a
    second, different filter term must not re-read any file (research R7)."""
    from endpaper.tui.app import EndpaperApp

    now = datetime.now()
    workspace = generate(tmp_path, 60, spread_months=6, now=now, current_month_count=5)

    app = EndpaperApp(workspace)
    app.active = "meetings"

    with _counting_read_text(monkeypatch) as read_paths:
        app.set_filter("generated")
        first_matches = app.visible_documents()
        reads_after_first_filter = len(read_paths)

        app.set_filter("meeting 1")
        app.visible_documents()
        reads_after_second_filter = len(read_paths)

    assert first_matches
    assert reads_after_first_filter > 0
    assert reads_after_second_filter == reads_after_first_filter
