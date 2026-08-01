from __future__ import annotations

import datetime

from choom.core.documents import _read_document
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import ListScreen
from tests.helpers import type_command


def _todays_notes(app: ChoomApp) -> list:  # type: ignore[type-arg]
    """The notes currently visible -- a fresh read, not a cache lookup
    (010-read-on-load). Callers land here right after creating today's daily
    note, so `app.active` is already "notes" and scoped to the current month."""
    return app.visible_documents()


async def test_bare_note_creates_and_opens_todays_daily_note(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")

        assert isinstance(app.screen, EditScreen)
        document = _read_document(app.screen.target.display_path)
        assert document is not None
        assert document.type == "daily"
        assert _todays_notes(app)[0].path == app.screen.target.display_path


async def test_bare_note_second_time_reopens_same_note_without_creating(
    tmp_workspace: Workspace,
) -> None:
    app = ChoomApp(tmp_workspace)
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
        assert len(_todays_notes(app)) == 1


async def test_bare_note_with_unparseable_existing_file_still_opens_the_editor(
    tmp_workspace: Workspace,
) -> None:
    now = datetime.datetime.now()
    path = tmp_workspace.daily_dir / f"{now:%Y/%m}" / f"{now:%Y-%m-%d}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not frontmatter at all", encoding="utf-8")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await type_command(app, pilot, "note")

        # The editor works on raw text regardless of whether frontmatter parses
        # (FR-022) -- a malformed existing daily note is still editable.
        assert isinstance(app.screen, EditScreen)
        assert app.screen.target.display_path == path
        assert app.screen.target.text == "not frontmatter at all"
