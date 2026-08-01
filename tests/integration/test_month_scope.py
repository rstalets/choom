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
from tests.helpers import to_collection, type_literally


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
    protects).

    Patches every scan entry point in **both** `choom.tui.list_screen` (the
    hydration worker's `scan_documents`) and `choom.tui.app` (the scoped
    `visible_documents()` reads and the `_filtered_documents()` fallback) --
    each module does its own `from choom.core.documents import ...`, which
    binds a separate name in each module's namespace at import time. Patching
    only one leaves the other's calls invisible to the counter, which would let
    exactly the regression this helper exists to catch -- `refresh_rows`
    falling back to a fresh scan instead of the hydrated pool -- pass
    unnoticed.

    Names absent from a module are skipped rather than asserted on, so moving a
    read between the two adapters does not silently blind the counter again."""
    import choom.tui.app as app_module
    import choom.tui.list_screen as list_screen_module

    calls: list[str] = []

    def _wrap(owner: object, name: str) -> None:
        original = getattr(owner, name, None)
        if original is None:
            return

        def counting(*args: object, **kwargs: object) -> object:
            calls.append(name)
            return original(*args, **kwargs)  # type: ignore[no-any-return,misc]

        monkeypatch.setattr(owner, name, counting)

    for owner in (list_screen_module, app_module):
        for name in ("scan_documents", "scan_month", "scan_unfiled"):
            _wrap(owner, name)

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


async def test_typing_a_filter_term_does_not_rescan_per_keystroke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The property the whole of US3 exists to protect, exercised the way a
    user actually triggers it: one `Input.Changed` (and one `FilterChanged`)
    per keystroke, not one `Input.Changed` for the whole term.

    The sibling test above (`..._at_most_once_per_command_bar_session`)
    proves the hydrated pool is reused across two *whole-value* assignments
    (`bar.value = "filter meeting 1"`), but a single assignment fires exactly
    one `Input.Changed` regardless of how many characters it represents --
    it cannot see a per-keystroke rescan even if one were happening. This
    test uses `type_literally`, which genuinely presses one key at a time,
    so it is the one place a regression that made `refresh_rows` fall back to
    `app.visible_documents()` while a filter is active -- turning every
    keystroke back into a full collection scan -- would actually be caught.
    Do not "simplify" this to `type_command`; that would silently delete the
    coverage.

    Not asserting "zero scans while typing": the verb `filter ` completes
    with an empty term one keystroke before the first character of the
    search text, and an empty filter term shows the plain month scope (FR-019)
    -- `_hydrated_pool()` returns `None` for it, on purpose, and the render
    falls through to `ChoomApp.visible_documents()`'s scoped single-month
    read. That is one call, not a collection-wide rescan, and it happens
    exactly once, at exactly that keystroke. Documented and asserted for
    explicitly, so it reads as expected behaviour rather than a leak; the
    property this test actually protects is what happens once the term is
    non-empty, where the hydrated pool must answer every further keystroke on
    its own -- no scan at all, scoped or collection-wide."""
    now = datetime.now()
    workspace = generate(tmp_path, 60, spread_months=6, now=now, current_month_count=5)

    app = ChoomApp(workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        with _counting_scan_calls(monkeypatch) as calls:
            await pilot.press("/")
            await pilot.pause()
            after_open = len(calls)
            assert after_open > 0  # the hydration itself scanned

            await type_literally(pilot, "filter ")
            await pilot.pause()
            # The verb just completed with an empty term -- exactly one
            # scoped month read, not a rescan of the collection.
            after_empty_term = len(calls)
            assert after_empty_term - after_open == 1

            await type_literally(pilot, "meeting 1")
            await pilot.pause()

            # Every keystroke from here on has a non-empty term: the
            # hydrated pool answers all of them, with no scan at all.
            assert len(calls) == after_empty_term
