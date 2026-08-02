"""`should_offer_discovery`'s suppression matrix (013-assistant-discovery-file, US2,
FR-022, FR-029, data-model.md's launch-offer state machine). Every row is a distinct
test so a future change to one condition cannot silently widen or narrow another.
"""

from __future__ import annotations

from choom.core.assistants import PROFILES
from choom.core.config import set_assistant, set_launch_offer_made
from choom.core.discovery import install_discovery_file, should_offer_discovery
from choom.core.models import ResolvedAssistant, Workspace

_CLAUDE = next(p for p in PROFILES if p.name == "claude")
_COPILOT = next(p for p in PROFILES if p.name == "copilot")


def _resolved(*, profile=None, source: str, available: tuple[str, ...] = ()) -> ResolvedAssistant:
    return ResolvedAssistant(profile=profile, source=source, available=available)


# --- offered -----------------------------------------------------------------------


def test_offered_when_detected_with_exactly_one_installed(tmp_workspace: Workspace) -> None:
    resolved = _resolved(profile=_CLAUDE, source="detected", available=("claude",))
    assert should_offer_discovery(tmp_workspace, resolved) is _CLAUDE


def test_offered_when_explicitly_configured_and_file_missing(tmp_workspace: Workspace) -> None:
    set_assistant(tmp_workspace, "claude")
    resolved = _resolved(profile=_CLAUDE, source="configured", available=("claude",))
    assert should_offer_discovery(tmp_workspace, resolved) is _CLAUDE


# --- suppressed ----------------------------------------------------------------------


def test_not_offered_when_discovery_file_already_installed(tmp_workspace: Workspace) -> None:
    install_discovery_file(tmp_workspace, _CLAUDE)
    resolved = _resolved(profile=_CLAUDE, source="detected", available=("claude",))
    assert should_offer_discovery(tmp_workspace, resolved) is None


def test_not_offered_when_assistant_is_none(tmp_workspace: Workspace) -> None:
    resolved = _resolved(profile=None, source="none", available=())
    assert should_offer_discovery(tmp_workspace, resolved) is None


def test_not_offered_when_ambiguous(tmp_workspace: Workspace) -> None:
    resolved = _resolved(profile=None, source="ambiguous", available=("claude", "copilot"))
    assert should_offer_discovery(tmp_workspace, resolved) is None


def test_not_offered_when_no_assistant_installed(tmp_workspace: Workspace) -> None:
    resolved = _resolved(profile=None, source="unset", available=())
    assert should_offer_discovery(tmp_workspace, resolved) is None


def test_not_offered_when_already_made(tmp_workspace: Workspace) -> None:
    set_launch_offer_made(tmp_workspace, True)
    resolved = _resolved(profile=_CLAUDE, source="detected", available=("claude",))
    assert should_offer_discovery(tmp_workspace, resolved) is None


def test_not_offered_when_already_made_by_declining(tmp_workspace: Workspace) -> None:
    # FR-027: what's recorded is that the offer was made, not which key was pressed --
    # a decline suppresses exactly the same as an install.
    set_launch_offer_made(tmp_workspace, True)
    resolved = _resolved(profile=_CLAUDE, source="detected", available=("claude",))
    assert should_offer_discovery(tmp_workspace, resolved) is None


# --- a same-named file without the marker does not count as "installed" ------------


def test_a_marker_less_file_at_the_path_does_not_suppress_the_offer(
    tmp_workspace: Workspace,
) -> None:
    from choom.core.discovery import discovery_path

    path = discovery_path(_CLAUDE)
    assert path is not None
    path.parent.mkdir(parents=True)
    path.write_text("someone else's file, not choom's\n", encoding="utf-8")

    resolved = _resolved(profile=_CLAUDE, source="detected", available=("claude",))
    assert should_offer_discovery(tmp_workspace, resolved) is _CLAUDE
