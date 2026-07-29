from __future__ import annotations

from pathlib import Path

from textual.widgets import TextArea

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.app import EndpaperApp
from endpaper.tui.edit_screen import EditScreen


def _rewrite_externally(path: Path) -> None:
    """Simulate a file touched outside endpaper: field order shuffled, single-quoted
    values, CRLF line endings, no trailing newline. Still schema-valid -- exactly the
    six required keys -- so it still shows up in the list like any other document."""
    externally_written = (
        "---\r\n"
        "title: 'Q3 planning'\r\n"
        "id: m_20260101_aaaa\r\n"
        "type: standup\r\n"
        "tags: []\r\n"
        "created: 2026-01-01T09:00:00\r\n"
        "updated: 2026-01-01T09:00:00\r\n"
        "---\r\n"
        "\r\n"
        "Body written by another program.\r\n"
        "Second line, no trailing newline at the very end."
    )
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(externally_written)


async def test_externally_modified_document_opens_edits_and_saves_indistinguishably(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(tmp_workspace, "placeholder", type="standup")
    _rewrite_externally(meeting.path)
    before_bytes = meeting.path.read_bytes()

    app = EndpaperApp(tmp_workspace)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert isinstance(app.screen, EditScreen)

        editor = app.screen.query_one("#editor", TextArea)
        assert editor.text.startswith("---\n")
        assert "title: 'Q3 planning'" in editor.text

        # Round-trip with no textual change at all: escape should not even prompt.
        await pilot.press("escape")
        await pilot.pause()
        assert meeting.path.read_bytes() == before_bytes

        # Now actually edit and save; everything but updated: must survive.
        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#editor", TextArea)
        editor.text = editor.text.replace(
            "Body written by another program.", "Body written by another program, edited."
        )

        await pilot.press("ctrl+o")
        await pilot.pause()

    after_bytes = meeting.path.read_bytes()
    assert after_bytes != before_bytes
    after_text = after_bytes.decode("utf-8")
    assert "\r\n" in after_text
    assert "title: 'Q3 planning'" in after_text
    assert "id: m_20260101_aaaa" in after_text
    assert "created: 2026-01-01T09:00:00" in after_text
    assert "Body written by another program, edited." in after_text
