from __future__ import annotations

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "endpaper" / "core" / "templates"

_FORBIDDEN_SUBSTRINGS = (
    "meetings/",
    "notes/",
    "tasks.md",
    "frontmatter",
    "endpaper meeting",
    "endpaper note",
    "endpaper task",
)


def test_claude_md_template_is_short_and_points_at_agents_md() -> None:
    text = (_TEMPLATES_DIR / "CLAUDE.md.tmpl").read_text(encoding="utf-8")
    lines = text.splitlines()

    assert len(lines) <= 12
    assert "AGENTS.md" in text
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in text, f"CLAUDE.md.tmpl duplicates a convention: {forbidden!r}"


def test_agents_md_template_stays_under_60_lines() -> None:
    text = (_TEMPLATES_DIR / "AGENTS.md.tmpl").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) <= 60
