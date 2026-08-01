from __future__ import annotations

import time
from pathlib import Path

import pytest

from choom.tui.app import ChoomApp
from choom.tui.list_screen import ListScreen
from tests.fixtures.generate import generate
from tests.helpers import row_titles, to_collection, type_command


@pytest.mark.performance
async def test_command_bar_open_does_not_block_on_the_collection_read_it_starts(
    tmp_path: Path,
) -> None:
    """FR-016, research R6: `/` starts a ~150 ms (at 1,000 documents,
    measured) collection read on a worker thread and must not wait for it.
    Measures `action_open_command_bar` directly rather than through
    `pilot.press` -- Textual's pilot drains pending work, including the
    worker's wrapper task, before `press()` returns, which would fold the
    read's duration back into the measurement and defeat the point; a bound
    key's action is what actually has to return quickly for the keypress to
    feel instant, and that is what this calls."""
    workspace = generate(tmp_path, 1000, spread_months=12)

    app = ChoomApp(workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")
        screen = app.screen
        assert isinstance(screen, ListScreen)

        start = time.perf_counter()
        screen.action_open_command_bar()
        elapsed = time.perf_counter() - start

        assert elapsed < 0.05
        assert screen._filter_hydration is not None


@pytest.mark.performance
async def test_first_filter_term_resolves_within_500ms(tmp_path: Path) -> None:
    """SC-004, FR-017: the first filter term waits for the hydration read to
    finish rather than matching a partial set, but must still land well
    inside the interactive budget on a 1,000-document workspace. Filters to a
    single match rather than the "generated meeting N" term every generated
    document shares -- rendering all 1,000 matched rows is a real cost, but a
    separate one from the read this budget protects."""
    workspace = generate(tmp_path, 1000, spread_months=12)

    app = ChoomApp(workspace)
    async with app.run_test(size=(100, 30)) as pilot:
        await to_collection(app, pilot, "meetings")

        start = time.perf_counter()
        await type_command(app, pilot, "filter meeting 999")
        first_term_elapsed = time.perf_counter() - start

        assert row_titles(app) == ["generated meeting 999"]
        assert first_term_elapsed < 0.5
