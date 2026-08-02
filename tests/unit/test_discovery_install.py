"""Installing, finding, and removing the assistant discovery file
(013-assistant-discovery-file). Covers US1 (T016), US3's repointing and removal
(T029), and US5's install-at-init (T037) -- one file per the risks they share:
computing the wrong path, overwriting rather than merging, and never touching a file
choom did not write.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from choom.core import discovery
from choom.core.assistants import PROFILES
from choom.core.discovery import (
    MARKER,
    discovery_path,
    install_discovery_file,
    installed_discovery_path,
    remove_discovery_files,
)
from choom.core.errors import WorkspaceError
from choom.core.models import AssistantProfile, Workspace
from choom.core.workspace import init_workspace

_CLAUDE = next(p for p in PROFILES if p.name == "claude")
_COPILOT = next(p for p in PROFILES if p.name == "copilot")


# --- US1: install --------------------------------------------------------------


def test_install_writes_the_expected_path_and_content(tmp_workspace: Workspace) -> None:
    path = install_discovery_file(tmp_workspace, _CLAUDE)
    assert path == discovery_path(_CLAUDE)
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert str(tmp_workspace.root) in text
    assert MARKER in text


def test_install_creates_missing_parent_directories(tmp_workspace: Workspace) -> None:
    path = discovery_path(_CLAUDE)
    assert path is not None
    assert not path.parent.exists()
    install_discovery_file(tmp_workspace, _CLAUDE)
    assert path.is_file()


def test_install_overwrites_an_existing_file_in_full(tmp_workspace: Workspace) -> None:
    path = discovery_path(_CLAUDE)
    assert path is not None
    path.parent.mkdir(parents=True)
    path.write_text("stale content that should be replaced entirely\n", encoding="utf-8")

    install_discovery_file(tmp_workspace, _CLAUDE)

    text = path.read_text(encoding="utf-8")
    assert "stale content" not in text
    assert str(tmp_workspace.root) in text


def test_profile_with_no_location_writes_nothing_and_does_not_raise(
    tmp_workspace: Workspace,
) -> None:
    profile = AssistantProfile(
        name="futuristic",
        display_name="Futuristic Assistant",
        binary="futuristic",
        build_args=lambda prompt: [prompt],
        parse_reply=lambda stdout: stdout,
        discovery_relpath=None,
    )
    result = install_discovery_file(tmp_workspace, profile)
    assert result is None
    # No stray file anywhere under the fake profile root.
    assert list(discovery.profile_root().rglob("*")) == []


def test_installed_discovery_path_is_none_when_nothing_installed() -> None:
    assert installed_discovery_path() is None


def test_installed_discovery_path_finds_the_installed_file(tmp_workspace: Workspace) -> None:
    path = install_discovery_file(tmp_workspace, _CLAUDE)
    assert installed_discovery_path() == path


def test_installed_discovery_path_ignores_a_same_named_file_without_the_marker() -> None:
    path = discovery_path(_CLAUDE)
    assert path is not None
    path.parent.mkdir(parents=True)
    path.write_text("some unrelated file that happens to share our path\n", encoding="utf-8")
    assert installed_discovery_path() is None


# --- US3: repointing and removal -------------------------------------------------


def test_repointing_from_one_workspace_to_another_leaves_no_trace_of_the_first(
    tmp_path: Path,
) -> None:
    workspace_a = init_workspace(tmp_path / "workspace-a").workspace
    workspace_b = init_workspace(tmp_path / "workspace-b").workspace

    install_discovery_file(workspace_a, _CLAUDE)
    path = install_discovery_file(workspace_b, _CLAUDE)

    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert str(workspace_b.root) in text
    assert str(workspace_a.root) not in text


def test_switching_assistants_leaves_exactly_one_file(tmp_workspace: Workspace) -> None:
    claude_path = install_discovery_file(tmp_workspace, _CLAUDE)
    copilot_path = install_discovery_file(tmp_workspace, _COPILOT)

    assert claude_path is not None
    assert not claude_path.exists()
    assert copilot_path is not None
    assert copilot_path.is_file()


def test_remove_discovery_files_with_no_keep_removes_everything(
    tmp_workspace: Workspace,
) -> None:
    install_discovery_file(tmp_workspace, _CLAUDE)
    install_discovery_file(tmp_workspace, _COPILOT)  # leaves only copilot's

    removed, warnings = remove_discovery_files()

    assert warnings == []
    assert len(removed) == 1
    assert installed_discovery_path() is None


def test_remove_discovery_files_is_idempotent(tmp_workspace: Workspace) -> None:
    install_discovery_file(tmp_workspace, _CLAUDE)
    first_removed, _ = remove_discovery_files()
    second_removed, second_warnings = remove_discovery_files()

    assert len(first_removed) == 1
    assert second_removed == []
    assert second_warnings == []


def test_remove_discovery_files_with_nothing_installed_succeeds(tmp_workspace: Workspace) -> None:
    removed, warnings = remove_discovery_files()
    assert removed == []
    assert warnings == []


def test_a_file_without_the_marker_is_left_alone_and_warned_about(
    tmp_workspace: Workspace,
) -> None:
    path = discovery_path(_CLAUDE)
    assert path is not None
    path.parent.mkdir(parents=True)
    path.write_text("a file the user made themselves, no marker here\n", encoding="utf-8")

    removed, warnings = remove_discovery_files()

    assert removed == []
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == "a file the user made themselves, no marker here\n"
    assert len(warnings) == 1
    assert str(path) in warnings[0]


def test_install_never_touches_a_marker_less_file_at_a_different_assistants_path(
    tmp_workspace: Workspace,
) -> None:
    copilot_path = discovery_path(_COPILOT)
    assert copilot_path is not None
    copilot_path.parent.mkdir(parents=True)
    copilot_path.write_text("hand-made file, not choom's\n", encoding="utf-8")

    install_discovery_file(tmp_workspace, _CLAUDE)

    assert copilot_path.read_text(encoding="utf-8") == "hand-made file, not choom's\n"


def test_install_failure_does_not_delete_the_previously_working_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = init_workspace(tmp_path / "ws").workspace
    install_discovery_file(workspace, _CLAUDE)
    claude_path = discovery_path(_CLAUDE)
    assert claude_path is not None
    original_text = claude_path.read_text(encoding="utf-8")

    def _boom(path: Path, text: str) -> None:
        raise WorkspaceError(f"simulated failure writing {path}")

    monkeypatch.setattr("choom.core.discovery.write_text_atomic", _boom)

    with pytest.raises(WorkspaceError):
        install_discovery_file(workspace, _COPILOT)

    # The install for copilot failed before any removal happened, so claude's
    # still-working file must still be there (research R8/R11 ordering).
    assert claude_path.read_text(encoding="utf-8") == original_text
