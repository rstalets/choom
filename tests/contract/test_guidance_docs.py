"""Linting for the guidance files `init` writes into a workspace.

Not CLI surface -- these assert that the docs an assistant reads stay short and
keep naming the conventions it has to follow.
"""

from __future__ import annotations

from pathlib import Path

from choom.core.models import Workspace

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "choom" / "core" / "templates"

# CLAUDE.md points at AGENTS.md; it must not restate any convention, or the two
# drift apart and the assistant gets two answers.
_FORBIDDEN_IN_CLAUDE_MD = (
    "meetings/",
    "notes/",
    "tasks.md",
    "frontmatter",
    "choom meeting",
    "choom note",
    "choom task",
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
    "task show",
    "task done",
    "task undone",
    "tasks.md",
    "YYYY",
    "Links",
    "links:",
    "meeting_",
    "note_",
    "choom links",
    "links check",
    "links heal",
    "blank line",
    "--link",
    "/task",
    "control surface",
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
    # generated copy and the source template share one line budget.
    #
    # The binding rule is content, not length: nothing an assistant could infer
    # from the workspace itself, and no restating the README. This bound is the
    # checkable backstop for that rule, raised from 60 to 100 by constitution
    # v1.2.0. At 60 the cap had twice forced real instructions out of the file
    # (007's `task show`, 008's link syntax), which inverts what it is for.
    # Failing here means reviewing the whole file for content that has stopped
    # earning its place -- not deleting whatever was added last.
    text = (tmp_workspace.root / "AGENTS.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 100


def test_agents_md_documents_the_conventions_an_assistant_needs(
    tmp_workspace: Workspace,
) -> None:
    text = (tmp_workspace.root / "AGENTS.md").read_text(encoding="utf-8")

    missing = [needle for needle in _REQUIRED_IN_AGENTS_MD if needle not in text]
    assert not missing, f"AGENTS.md no longer documents: {missing}"
    assert "- [ ]" in text or "- [x]" in text, "AGENTS.md does not show the task line format"


def test_agents_md_names_the_task_body_format_and_task_show(tmp_workspace: Workspace) -> None:
    """007: a task's optional body -- indented lines beneath the checkbox line,
    separated by a blank line -- and `task show` (the command that reads one
    back) must be part of the guidance an assistant gets at init time."""
    text = (tmp_workspace.root / "AGENTS.md").read_text(encoding="utf-8")

    assert "body" in text
    assert "task show" in text
    # The example shows the actual shape: a task line, then a blank line, then
    # an indented continuation -- not just the word "body" in passing.
    lines = text.splitlines()
    task_line_index = next(i for i, line in enumerate(lines) if line.startswith("- [ ]"))
    assert lines[task_line_index + 1].strip() == ""
    assert lines[task_line_index + 2].startswith("  ")
