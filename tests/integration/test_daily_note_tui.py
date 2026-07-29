from __future__ import annotations

from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.list_screen import ListScreen
from endpaper.tui.preview_screen import PreviewScreen


async def test_bare_note_creates_and_previews_todays_daily_note(tmp_workspace: Workspace) -> None:
    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        await pilot.press("n", "o", "t", "e")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.document is not None
        assert app.screen.document.type == "daily"
        assert app.documents["notes"][0] is app.screen.document


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
        first_path = app.screen.document.path  # type: ignore[union-attr]

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, ListScreen)

        await pilot.press("/")
        await pilot.pause()
        await pilot.press("n", "o", "t", "e")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.document is not None
        assert app.screen.document.path == first_path
        assert len(app.documents["notes"]) == 1


async def test_bare_note_with_unparseable_existing_file_previews_with_no_document(
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

        assert isinstance(app.screen, PreviewScreen)
        assert app.screen.document is None
        assert app.screen.path == path
        assert len(app.documents["notes"]) == 0

        status = app.screen.query_one("#status-bar")
        assert "could not be read" in str(status.content)
