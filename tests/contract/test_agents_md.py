from __future__ import annotations

from endpaper.core.models import Workspace


def test_agents_md_is_short_and_documents_tag_flag(tmp_workspace: Workspace) -> None:
    agents_md = tmp_workspace.root / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert len(lines) <= 62
    assert "--tag" in text


def test_agents_md_documents_the_three_note_commands(tmp_workspace: Workspace) -> None:
    agents_md = tmp_workspace.root / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert len(lines) <= 62
    assert "note today" in text
    assert "note new" in text
    assert "note list" in text
    assert "notes/daily/" in text
    assert "notes/" in text


def test_agents_md_documents_task_commands_and_line_format(tmp_workspace: Workspace) -> None:
    agents_md = tmp_workspace.root / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert len(lines) <= 62
    assert "task add" in text
    assert "task list" in text
    assert "task done" in text
    assert "task undone" in text
    assert "tasks.md" in text
    assert "- [ ]" in text or "- [x]" in text


def test_agents_md_documents_the_yyyy_mm_layout(tmp_workspace: Workspace) -> None:
    agents_md = tmp_workspace.root / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8")

    assert "YYYY/MM" in text or "YYYY" in text
