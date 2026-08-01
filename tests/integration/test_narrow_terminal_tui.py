from __future__ import annotations

from choom.core.meetings import create_meeting
from choom.core.models import Workspace
from choom.tui.app import ChoomApp
from choom.tui.collection_bar import CollectionBar
from tests.helpers import to_collection


async def test_narrow_terminal_does_not_crash_and_keeps_active_collection_visible(
    tmp_workspace: Workspace,
) -> None:
    # Spec edge case: "a terminal too narrow for three panes plus the top bar"
    # must degrade without truncating the collection names into ambiguity, and
    # the highlighted collection must remain identifiable.
    create_meeting(tmp_workspace, "Q3 planning")

    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(20, 24)) as pilot:
        await to_collection(app, pilot, "meetings")

        bar = app.screen.query_one(CollectionBar)
        rendered = str(bar.content)
        assert "[reverse]" in rendered  # the active collection is still marked
        assert len(rendered.replace("[reverse]", "").replace("[/reverse]", "")) <= 20


async def test_extremely_narrow_terminal_still_boots(tmp_workspace: Workspace) -> None:
    app = ChoomApp(tmp_workspace)
    async with app.run_test(size=(10, 24)) as pilot:
        await pilot.pause()
        assert app.active == "tasks"
