"""Path resolution for the assistant discovery file (013-assistant-discovery-file,
research R3, R13). The guard test in this file exists to prove, before any install code
is written, that the test suite's autouse fixture actually redirects `profile_root()`
away from the developer's real home directory -- everything downstream depends on that
being true.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from choom.core import discovery
from choom.core.assistants import PROFILES
from choom.core.models import AssistantProfile


def test_profile_root_is_redirected_under_the_test_fixture() -> None:
    root = discovery.profile_root()
    assert root != Path.home()
    # tmp_path-based: any real filesystem tmp root qualifies, so assert it is *some*
    # path other than the developer's home rather than hardcoding a tmp prefix.
    assert root.is_dir()


def test_discovery_path_joins_profile_root_with_the_profiles_relpath() -> None:
    claude = next(p for p in PROFILES if p.name == "claude")
    copilot = next(p for p in PROFILES if p.name == "copilot")

    root = discovery.profile_root()
    assert discovery.discovery_path(claude) == root / ".claude" / "skills" / "choom" / "SKILL.md"
    assert (
        discovery.discovery_path(copilot)
        == root / ".copilot" / "instructions" / "choom.instructions.md"
    )


def test_discovery_path_is_none_for_a_profile_with_no_location() -> None:
    profile = AssistantProfile(
        name="future-assistant",
        display_name="Future Assistant",
        binary="future-assistant",
        build_args=lambda prompt: [prompt],
        parse_reply=lambda stdout: stdout,
        discovery_relpath=None,
    )
    assert discovery.discovery_path(profile) is None


def test_discovery_relpath_is_profile_relative_not_absolute() -> None:
    for profile in PROFILES:
        if profile.discovery_relpath is None:
            continue
        assert isinstance(profile.discovery_relpath, PurePosixPath)
        assert not profile.discovery_relpath.is_absolute()
