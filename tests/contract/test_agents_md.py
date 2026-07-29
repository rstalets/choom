from __future__ import annotations

from endpaper.core.models import Workspace


def test_agents_md_is_short_and_documents_tag_flag(tmp_workspace: Workspace) -> None:
    agents_md = tmp_workspace.root / "AGENTS.md"
    text = agents_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert len(lines) <= 62
    assert "--tag" in text
