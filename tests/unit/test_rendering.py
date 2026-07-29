from __future__ import annotations

from datetime import datetime

from endpaper.core.meetings import create_meeting
from endpaper.core.models import Workspace
from endpaper.tui.rendering import render_preview_markdown


def test_preview_markdown_strips_frontmatter_and_headings_the_title(
    tmp_workspace: Workspace,
) -> None:
    meeting = create_meeting(
        tmp_workspace,
        "Q3 planning",
        type="standup",
        tags=("platform",),
        now=datetime(2026, 7, 28, 9, 14, 0),
    )

    rendered = render_preview_markdown(meeting.path, meeting)

    assert rendered.startswith("# Q3 planning\n")
    assert "id:" not in rendered
    assert "created:" not in rendered
    assert "---" not in rendered
    assert "standup" in rendered
    assert "#platform" in rendered


def test_preview_markdown_includes_body_content(tmp_workspace: Workspace) -> None:
    meeting = create_meeting(tmp_workspace, "hallway chat")
    meeting.path.write_text(
        meeting.path.read_text(encoding="utf-8") + "Some notes go here.\n",
        encoding="utf-8",
    )

    rendered = render_preview_markdown(meeting.path, meeting)
    assert "Some notes go here." in rendered
