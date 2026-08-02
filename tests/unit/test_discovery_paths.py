"""Path resolution for the assistant discovery file (013-assistant-discovery-file,
research R3, R13). The guard test in this file exists to prove, before any install code
is written, that the test suite's autouse fixture actually redirects `profile_root()`
away from the developer's real home directory -- everything downstream depends on that
being true.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath

from choom.core import discovery
from choom.core.assistants import PROFILES
from choom.core.models import AssistantProfile

#: Captured at import time, before any test's autouse fixture has run, so this is the
#: developer's real home directory regardless of what the isolation fixture does to
#: `Path.home()`/`$HOME` for the duration of a test (the fixture patches both, so
#: `Path.home()` *inside* a test is no longer a reliable way to name "the real one").
_REAL_HOME = Path.home()


def test_profile_root_is_redirected_under_the_test_fixture() -> None:
    root = discovery.profile_root()
    assert root != _REAL_HOME
    assert root.is_dir()


def test_subprocess_cli_invocation_is_also_isolated(tmp_path: Path) -> None:
    """The in-process guard above cannot catch the hole that actually bit this
    feature during development: `tests/contract/` runs choom as a real child process
    (`subprocess.run([sys.executable, "-m", "choom", ...])`), which gets a fresh
    interpreter that never sees `monkeypatch.setattr` -- only environment variables
    cross that boundary. A child that resolved `Path.home()` for real would write a
    live file into the developer's actual `~/.claude`, exactly as happened once
    before this test existed. This proves the autouse fixture's `HOME`/`USERPROFILE`
    env vars close that hole, not just the in-process patch.
    """
    real_claude_skill = _REAL_HOME / ".claude" / "skills" / "choom" / "SKILL.md"
    existed_before = real_claude_skill.exists()

    subprocess.run(
        [sys.executable, "-m", "choom", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    result = subprocess.run(
        [sys.executable, "-m", "choom", "config", "assistant", "claude"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    # Nothing landed in the real home directory -- the file existing or not is
    # unchanged from before this subprocess ran either way.
    assert real_claude_skill.exists() == existed_before

    # And the file *did* land somewhere -- under this test's own fake profile root,
    # proving the redirection actually took effect rather than the install silently
    # no-op'ing.
    installed = discovery.profile_root() / ".claude" / "skills" / "choom" / "SKILL.md"
    assert installed.is_file()


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
