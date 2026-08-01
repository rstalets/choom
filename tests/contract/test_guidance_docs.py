"""Linting for the guidance files `init` writes into a workspace.

Not CLI surface -- these assert that the docs an assistant reads stay short and
keep naming the conventions it has to follow.
"""

from __future__ import annotations

from pathlib import Path

from endpaper.core.models import Workspace

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "endpaper" / "core" / "templates"

# CLAUDE.md points at AGENTS.md; it must not restate any convention, or the two
# drift apart and the assistant gets two answers.
_FORBIDDEN_IN_CLAUDE_MD = (
    "meetings/",
    "notes/",
    "tasks.md",
    "frontmatter",
    "endpaper meeting",
    "endpaper note",
    "endpaper task",
)

_REQUIRED_IN_AGENTS_MD = (
    "--tag",
    "note today",
    "note new",
    "note list",
    "notes/daily/",
    "notes/",
    "task add",
    "task list",
    "task done",
    "task undone",
    "tasks.md",
    "YYYY",
    "Links",
    "links:",
    "meeting_",
    "note_",
    "endpaper links",
    "links check",
    "links heal",
)


def test_claude_md_template_is_short_and_points_at_agents_md() -> None:
    text = (_TEMPLATES_DIR / "CLAUDE.md.tmpl").read_text(encoding="utf-8")

    assert len(text.splitlines()) <= 12
    assert "AGENTS.md" in text
    for forbidden in _FORBIDDEN_IN_CLAUDE_MD:
        assert forbidden not in text, f"CLAUDE.md.tmpl duplicates a convention: {forbidden!r}"


def test_agents_md_stays_within_line_budget(tmp_workspace: Workspace) -> None:
    # init_workspace writes AGENTS.md verbatim from AGENTS.md.tmpl (no
    # substitution -- see workspace.py's `_write_guidance_file`), so the
    # generated copy and the source template share one line budget. 008
    # tightened this from 63 to <= 60 while adding link content (research R9).
    text = (tmp_workspace.root / "AGENTS.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 60


def test_agents_md_documents_the_conventions_an_assistant_needs(
    tmp_workspace: Workspace,
) -> None:
    text = (tmp_workspace.root / "AGENTS.md").read_text(encoding="utf-8")

    missing = [needle for needle in _REQUIRED_IN_AGENTS_MD if needle not in text]
    assert not missing, f"AGENTS.md no longer documents: {missing}"
    assert "- [ ]" in text or "- [x]" in text, "AGENTS.md does not show the task line format"
