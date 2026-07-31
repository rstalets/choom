from __future__ import annotations

from endpaper.core.documents import _read_document
from endpaper.core.models import Workspace, YearMonth
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import ListScreen


async def test_bare_note_creates_and_opens_todays_daily_note(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await pilot.press("n", "o", "t", "e")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        document = _read_document(app.screen.file.path)
        assert document is not None
        assert document.type == "daily"

        from datetime import date

        today = date.today()
        month = YearMonth(today.year, today.month)
        cached = app.month_cache[("notes", month)]
        assert cached[0].path == app.screen.file.path


async def test_bare_note_second_time_reopens_same_note_without_creating(
    tmp_workspace: Workspace,
) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await pilot.press("n", "o", "t", "e")
        await pilot.press("enter")
        await pilot.pause()
        first_path = app.screen.file.path  # type: ignore[union-attr]

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)

        await pilot.press("/")
        await pilot.pause()
        await pilot.press("n", "o", "t", "e")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, EditScreen)
        assert app.screen.file.path == first_path

        from datetime import date

        today = date.today()
        month = YearMonth(today.year, today.month)
        assert len(app.month_cache[("notes", month)]) == 1


async def test_bare_note_with_unparseable_existing_file_still_opens_the_editor(
    tmp_workspace: Workspace,
) -> None:
    import datetime

    now = datetime.datetime.now()
    path = tmp_workspace.daily_dir / f"{now:%Y/%m}" / f"{now:%Y-%m-%d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not frontmatter at all", encoding="utf-8")

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await pilot.press("n", "o", "t", "e")
        await pilot.press("enter")
        await pilot.pause()

        # The editor works on raw text regardless of whether frontmatter parses
        # (FR-022) -- a malformed existing daily note is still editable.
        assert isinstance(app.screen, EditScreen)
        assert app.screen.file.path == path
        assert app.screen.file.text == "not frontmatter at all"
