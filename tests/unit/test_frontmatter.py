from __future__ import annotations

from pathlib import Path

from endpaper.core.frontmatter import read_frontmatter, render_frontmatter
from endpaper.core.models import Meeting


def _block(body: str) -> str:
    return body


def test_yaml11_booleans_stay_strings() -> None:
    data = read_frontmatter(
        """
id: m_20260728_a1b2c3d4
type: standup
title: "Q3 planning"
tags: [no, on, off, y]
created: 2026-07-28T09:14:00
updated: 2026-07-28T09:14:00
"""
    )
    assert data["tags"] == ["no", "on", "off", "y"]


def test_bare_timestamp_stays_a_string() -> None:
    data = read_frontmatter(
        """
id: m_20260728_a1b2c3d4
type: standup
title: "Q3 planning"
tags: []
created: 2026-07-28T09:14:00
updated: 2026-07-28T09:14:00
"""
    )
    assert data["created"] == "2026-07-28T09:14:00"
    assert isinstance(data["created"], str)


def test_float_looking_title_stays_a_string() -> None:
    data = read_frontmatter(
        """
id: m_20260728_a1b2c3d4
type: standup
title: 3.10
tags: []
created: 2026-07-28T09:14:00
updated: 2026-07-28T09:14:00
"""
    )
    assert data["title"] == "3.10"


def test_emitter_is_deterministic() -> None:
    meeting = Meeting(
        id="m_20260728_a1b2c3d4",
        path=Path("meetings/2026-07-28-standup-q3-planning.md"),
        title="Q3 planning",
        type="standup",
        tags=("platform",),
        created="2026-07-28T09:14:00",
        updated="2026-07-28T09:14:00",
    )
    first = render_frontmatter(meeting)
    second = render_frontmatter(meeting)
    assert first == second
    assert first == (
        "---\n"
        "id: m_20260728_a1b2c3d4\n"
        'type: "standup"\n'
        'title: "Q3 planning"\n'
        'tags: ["platform"]\n'
        "created: 2026-07-28T09:14:00\n"
        "updated: 2026-07-28T09:14:00\n"
        "---\n"
        "\n"
    )


def test_long_title_round_trips_with_no_wrapping() -> None:
    long_title = "A" * 200
    meeting = Meeting(
        id="m_20260728_a1b2c3d4",
        path=Path("meetings/2026-07-28-standup-long.md"),
        title=long_title,
        type="",
        tags=(),
        created="2026-07-28T09:14:00",
        updated="2026-07-28T09:14:00",
    )
    rendered = render_frontmatter(meeting)
    for line in rendered.splitlines():
        assert "\n" not in line
    assert f'title: "{long_title}"' in rendered

    inner = rendered.split("---\n", 2)[1]
    data = read_frontmatter(inner)
    assert data["title"] == long_title
