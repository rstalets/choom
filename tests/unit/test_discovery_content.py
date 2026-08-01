"""Rendered content of the assistant discovery file (013-assistant-discovery-file,
contracts/discovery-file.md, research R10). Covers the risks named in tasks.md T009:
the marker's presence, verbatim rendering of a path with spaces and non-ASCII
characters, the line budget, determinism, and that nothing from `AGENTS.md.tmpl` is
restated.
"""

from __future__ import annotations

from pathlib import Path

from choom.core.assistants import PROFILES
from choom.core.discovery import MARKER, render_discovery_file
from choom.core.models import Workspace

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "choom" / "core" / "templates"

#: Distinctive strings from AGENTS.md.tmpl that must never appear in the discovery
#: file (FR-003) -- restating any of these would make the pointer a second copy of
#: AGENTS.md rather than a pointer to it.
_AGENTS_MD_DISTINCTIVE_STRINGS = (
    "meetings/YYYY/MM/",
    "id: meeting_",
    "choom task add",
    "Exit codes:",
)


def _workspace(path: Path) -> Workspace:
    return Workspace(root=path)


def test_marker_present_for_every_profile() -> None:
    workspace = _workspace(Path("/tmp/choom-example"))
    for profile in PROFILES:
        assert MARKER in render_discovery_file(workspace, profile)


def test_workspace_path_with_spaces_and_non_ascii_appears_verbatim() -> None:
    tricky = Path("/tmp/Équipe Notes 笔记/choom-workspace")
    workspace = _workspace(tricky)
    for profile in PROFILES:
        text = render_discovery_file(workspace, profile)
        assert str(tricky) in text
        # Alone on its own line, unquoted (FR-018) -- not embedded in a longer line
        # that would need escaping rules the reader has to know.
        lines = text.splitlines()
        assert str(tricky) in lines


def test_line_count_stays_within_the_twenty_line_backstop() -> None:
    workspace = _workspace(Path("/tmp/choom-example"))
    for profile in PROFILES:
        text = render_discovery_file(workspace, profile)
        assert len(text.splitlines()) <= 20


def test_rendering_is_deterministic() -> None:
    workspace = _workspace(Path("/tmp/choom-example"))
    for profile in PROFILES:
        first = render_discovery_file(workspace, profile)
        second = render_discovery_file(workspace, profile)
        assert first == second


def test_no_agents_md_content_is_restated() -> None:
    workspace = _workspace(Path("/tmp/choom-example"))
    for profile in PROFILES:
        text = render_discovery_file(workspace, profile)
        for needle in _AGENTS_MD_DISTINCTIVE_STRINGS:
            assert needle not in text, f"{profile.name}'s discovery file restates {needle!r}"


def test_claude_wrapper_carries_frontmatter_and_copilot_does_not() -> None:
    workspace = _workspace(Path("/tmp/choom-example"))
    claude = next(p for p in PROFILES if p.name == "claude")
    copilot = next(p for p in PROFILES if p.name == "copilot")

    claude_text = render_discovery_file(workspace, claude)
    assert claude_text.startswith("---\n")
    assert "name: choom" in claude_text
    assert "description:" in claude_text

    copilot_text = render_discovery_file(workspace, copilot)
    assert not copilot_text.startswith("---\n")
    assert copilot_text.startswith("# choom\n")


def test_points_at_agents_md_and_names_what_choom_is() -> None:
    workspace = _workspace(Path("/tmp/choom-example"))
    for profile in PROFILES:
        text = render_discovery_file(workspace, profile)
        assert "AGENTS.md" in text
        assert "choom" in text.lower()
