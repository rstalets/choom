from __future__ import annotations

import datetime
from datetime import date

from endpaper.core.documents import _read_document
from endpaper.core.models import Workspace, YearMonth
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import ListScreen
from tests.helpers import type_command


def _todays_cache(app: EndpaperApp) -> list:  # type: ignore[type-arg]
    today = date.today()
    return app.month_cache[("notes", YearMonth(today.year, today.month))]


async def test_bare_note_creates_and_opens_todays_daily_note(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")

        assert isinstance(app.screen, EditScreen)
        document = _read_document(app.screen.target.display_path)
        assert document is not None
        assert document.type == "daily"
        assert _todays_cache(app)[0].path == app.screen.target.display_path


async def test_bare_note_second_time_reopens_same_note_without_creating(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")
        first_path = app.screen.target.display_path  # type: ignore[union-attr]

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)

        await type_command(app, pilot, "note")

        assert isinstance(app.screen, EditScreen)
        assert app.screen.target.display_path == first_path
        assert len(_todays_cache(app)) == 1


async def test_bare_note_with_unparseable_existing_file_still_opens_the_editor(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.datetime.now()
    path = tmp_workspace.daily_dir / f"{now:%Y/%m}" / f"{now:%Y-%m-%d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not frontmatter at all", encoding="utf-8")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")

        # The editor works on raw text regardless of whether frontmatter parses
        # (FR-022) -- a malformed existing daily note is still editable.
        assert isinstance(app.screen, EditScreen)
        assert app.screen.target.display_path == path
        assert app.screen.target.text == "not frontmatter at all"
