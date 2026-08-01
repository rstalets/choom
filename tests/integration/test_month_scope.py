from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
from textual.widgets import Input

from choom.core.documents import scan_month
from choom.core.meetings import MEETINGS
from choom.core.models import Collection, Workspace, YearMonth
from choom.core.notes import NOTES
from choom.tui.app import ChoomApp
from tests.fixtures.generate import generate, generate_notes
from tests.helpers import to_collection


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


@pytest.mark.parametrize(
    ("descriptor", "make_workspace", "dir_attr"),
    [
        (MEETINGS, generate, "meetings_dir"),
        (NOTES, generate_notes, "notes_dir"),
    ],
    ids=["meetings", "notes"],
)
def test_opening_collection_reads_only_current_month(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    descriptor: Collection,
    make_workspace: Callable[..., Workspace],
    dir_attr: str,
) -> None:
    now = datetime.now()
    workspace = make_workspace(tmp_path, 400, spread_months=12, now=now, current_month_count=5)

    current_month = YearMonth(now.year, now.month)
    expected_dir = getattr(workspace, dir_attr) / f"{now:%Y}" / f"{now:%m}"

    with _counting_read_text(monkeypatch) as read_paths:
        documents, warnings = scan_month(workspace, descriptor, current_month)

    assert warnings == []
    assert len(documents) == 5
    assert read_paths, "expected scan_month to read at least one file"
    assert all(p.parent == expected_dir for p in read_paths)
    assert len(read_paths) == len(documents)


@contextmanager
def _counting_scan_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Count calls into `scan_month`/`scan_unfiled` -- the collection-wide scan
    a filter hydration performs -- rather than raw file reads, so the count is
    not muddied by the one, unrelated file the preview pane reads on every
    render (`render_preview_markdown`, wholly outside the cache this test
    protects)."""
    import choom.tui.list_screen as list_screen_module

    calls: list[str] = []
    original_scan_month = list_screen_module.scan_month
    original_scan_unfiled = list_screen_module.scan_unfiled

    def counting_scan_month(*args: object, **kwargs: object) -> object:
        calls.append("scan_month")
        return original_scan_month(*args, **kwargs)  # type: ignore[arg-type]

    def counting_scan_unfiled(*args: object, **kwargs: object) -> object:
        calls.append("scan_unfiled")
        return original_scan_unfiled(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(list_screen_module, "scan_month", counting_scan_month)
    monkeypatch.setattr(list_screen_module, "scan_unfiled", counting_scan_unfiled)
    yield calls


async def test_filter_reads_each_month_at_most_once_per_command_bar_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Narrowed by 010-read-on-load from spec 005's FR-035 ("at most once per
    app session") to "at most once per command-bar session": the session-
    lifetime cache that property used to describe is gone, replaced by the
    hydration snapshot started when the bar opens (research R6). A second,
    different filter term within one bar opening still reads nothing new
    (contract C5); a new bar opening reads again, since the snapshot's
    lifetime is exactly one session (FR-019)."""
    now = datetime.now()
    workspace = generate(tmp_path, 60, spread_months=6, now=now, current_month_count=5)

    app = ChoomApp(workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        with _counting_scan_calls(monkeypatch) as calls:
            await pilot.press("/")
            await pilot.pause()
            bar = app.screen.query_one("#bar-input", Input)
            bar.value = "filter generated"
            bar.cursor_position = len(bar.value)
            await pilot.pause()
            calls_after_first_filter = len(calls)

            bar.value = "filter meeting 1"
            bar.cursor_position = len(bar.value)
            await pilot.pause()
            calls_after_second_filter = len(calls)

        assert calls_after_first_filter > 0
        assert calls_after_second_filter == calls_after_first_filter

        await pilot.press("escape")
        await pilot.pause()

        with _counting_scan_calls(monkeypatch) as new_session_calls:
            await pilot.press("/")
            await pilot.pause()
            bar = app.screen.query_one("#bar-input", Input)
            bar.value = "filter generated"
            bar.cursor_position = len(bar.value)
            await pilot.pause()

        assert len(new_session_calls) > 0
