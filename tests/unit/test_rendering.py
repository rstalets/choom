from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from choom.core.meetings import create_meeting
from choom.core.models import LinkCandidate, LinkTarget, Task, Workspace
from choom.tui.rendering import render_candidate_row, render_preview_markdown, render_task_markdown


def _candidate(
    *, title: str = "Q3 planning", collection: str = "meeting", when: str | None = "2026-07-28"
) -> LinkCandidate:
    target = LinkTarget(
        id="meeting_20260728_a1b2c3d4", path=Path("x"), title=title, kind="meeting", line=None
    )
    return LinkCandidate(target=target, collection=collection, date=when)


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


def _task(**overrides: object) -> Task:
    defaults: dict[str, object] = dict(
        id="t_a1b2",
        text="call the vendor",
        done=False,
        type="",
        tags=(),
        created=None,
        line=1,
        body="",
    )
    defaults.update(overrides)
    return Task(**defaults)  # type: ignore[arg-type]


def test_heading_is_the_task_text() -> None:
    rendered = render_task_markdown(_task(text="call the vendor"))
    assert rendered.startswith("# call the vendor\n")


def test_metadata_line_carries_created_type_and_tags() -> None:
    rendered = render_task_markdown(
        _task(created=date(2026, 7, 30), type="followup", tags=("procurement",))
    )
    assert "*2026-07-30 · followup · #procurement*" in rendered


def test_absent_metadata_fields_are_omitted() -> None:
    rendered = render_task_markdown(_task(created=None, type="", tags=()))
    assert "*" not in rendered


def test_completed_task_is_marked_in_the_metadata_line() -> None:
    rendered = render_task_markdown(_task(done=True, created=date(2026, 7, 30)))
    assert "done" in rendered.split("\n\n")[1]


def test_task_with_no_body_renders_heading_and_metadata_only() -> None:
    rendered = render_task_markdown(_task(created=date(2026, 7, 30), body=""))
    assert rendered == "# call the vendor\n\n*2026-07-30*\n"


def test_body_is_appended_after_the_metadata_line() -> None:
    rendered = render_task_markdown(
        _task(created=date(2026, 7, 30), body="Need the Q3 comparison.\n\n- called")
    )
    assert rendered == ("# call the vendor\n\n*2026-07-30*\n\nNeed the Q3 comparison.\n\n- called")


# --- render_candidate_row (015-link-picker, contracts/tui.md C3) ----------------


def test_a_long_title_truncates_while_collection_and_date_survive() -> None:
    candidate = _candidate(title="A" * 60, collection="meeting", when="2026-07-28")
    rendered = render_candidate_row(candidate, 40)

    assert len(rendered) <= 40
    assert "…" in rendered
    assert rendered.endswith("meeting · 2026-07-28")


def test_an_undated_candidate_renders_an_em_dash() -> None:
    candidate = _candidate(title="call Terry", collection="task", when=None)
    rendered = render_candidate_row(candidate, 40)

    assert rendered == "call Terry · task · —"


def test_a_zero_width_returns_a_string_rather_than_raising() -> None:
    candidate = _candidate()
    assert render_candidate_row(candidate, 0) == ""


def test_a_blank_title_returns_a_string_rather_than_raising() -> None:
    candidate = _candidate(title="")
    rendered = render_candidate_row(candidate, 40)

    assert rendered == " · meeting · 2026-07-28"


def test_a_short_title_is_not_truncated() -> None:
    candidate = _candidate(title="Q3 planning", collection="note", when="2026-01-05")
    rendered = render_candidate_row(candidate, 80)

    assert rendered == "Q3 planning · note · 2026-01-05"
