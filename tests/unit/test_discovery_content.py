"""Rendered content of the assistant discovery file (013-assistant-discovery-file,
contracts/discovery-file.md, research R10). Covers the risks named in tasks.md T009:
the marker's presence, verbatim rendering of a path with spaces and non-ASCII
characters, the line budget, determinism, and that nothing from `AGENTS.md.tmpl` is
restated.
"""

from __future__ import annotations

from pathlib import Path

import yaml

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


def test_every_profile_gets_the_same_skill_file() -> None:
    """Both supported assistants read the same artifact -- a `SKILL.md` carrying `name`
    and `description` frontmatter, dropped into a user-scope skills directory and
    discovered without registration -- so there is nothing left for the renderer to
    vary between them (research R1, R2). Asserted rather than assumed: a divergence
    here would mean one assistant silently receives a file it cannot parse.
    """
    workspace = _workspace(Path("/tmp/choom-example"))
    rendered = {p.name: render_discovery_file(workspace, p) for p in PROFILES}

    for name, text in rendered.items():
        assert text.startswith("---\n"), f"{name} lost its frontmatter"
        assert "name: choom" in text
        assert "description:" in text

    assert len(set(rendered.values())) == 1


def test_frontmatter_parses_as_yaml_and_says_when_to_use_the_skill() -> None:
    """The frontmatter is the skill's whole discovery mechanism: an assistant matches
    a request against `description` to decide whether to open the skill at all, so it
    has to parse, and it has to describe *when* choom is relevant rather than only what
    it is. A description naming the tool alone gives a request like "write this up"
    nothing to match, leaving the skill usable only when the user names it -- the manual
    instruction this feature exists to remove.

    Parsing is not a formality. The description is a plain YAML scalar, so a stray
    ": " or " #" inside it would silently truncate the value or end the document, and
    the failure would show up as a skill that never triggers rather than as an error.
    """
    workspace = _workspace(Path("/tmp/choom-example"))
    for profile in PROFILES:
        text = render_discovery_file(workspace, profile)

        _, _, rest = text.partition("---\n")
        block, _, _ = rest.partition("\n---\n")
        parsed = yaml.safe_load(block)

        # Both products require `name` to be a lowercase identifier.
        assert parsed["name"] == "choom"
        description = parsed["description"]
        # The whole sentence survived the scalar, not just its first clause.
        assert description.endswith("where its instructions are.")
        # It names the situations to use it in, not only the tool.
        assert "Use it whenever" in description
        for trigger in ("meeting", "note", "task"):
            assert trigger in description.lower()


def test_points_at_agents_md_and_names_what_choom_is() -> None:
    workspace = _workspace(Path("/tmp/choom-example"))
    for profile in PROFILES:
        text = render_discovery_file(workspace, profile)
        assert "AGENTS.md" in text
        assert "choom" in text.lower()
