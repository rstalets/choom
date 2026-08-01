from __future__ import annotations

import random
from collections.abc import Sequence

from textual.widgets import Static

from choom import __version__

LIST_HELP = (
    "tab collection   / filter   ↑↓/jk move   h/l pane   "
    "enter open   e edit   b backlinks   ctrl+d delete   ctrl+q quit"
)
TASK_LIST_HELP = (
    "tab collection   / filter   ↑↓/jk move   h/l pane   e edit   "
    "space toggle   b backlinks   ctrl+d delete   ctrl+q quit"
)
PREVIEW_HELP = "e edit   b backlinks   esc back   ↑↓/pgup/pgdn scroll   ctrl+q quit"
#: Swapped in for PREVIEW_HELP while the Links section has focus, the same way
#: EDIT_HELP is a whole separate string rather than an append -- the footer must
#: never grow past what fits, so the two never concatenate (research R10).
LINKS_SECTION_HELP = "↑↓ move   enter/o open   esc close   ctrl+q quit"
EDIT_HELP = "ctrl+o save   ctrl+x save & back   esc discard   ctrl+q quit"

#: Shown in the status bar while `/ai` is in flight (contracts/editor-commands.md). One
#: phrase is picked per request and held for its whole duration -- no cycling, no timer.
BREADCRUMBS: tuple[str, ...] = (
    "Circling back",
    "Double-clicking",
    "Taking it offline",
    "Leveraging synergies",
    "Boiling the ocean",
    "Peeling the onion",
    "Running it up the flagpole",
    "Socialising the doc",
    "Moving the needle",
    "Unpacking that",
    "Actioning",
    "Aligning stakeholders",
    "Workshopping",
    "Whiteboarding",
    "Ideating",
    "Operationalising",
    "Sharpening the pencil",
    "Putting a pin in it",
    "Closing the loop",
    "Touching base",
    "Gut-checking",
    "Blue-skying",
    "Right-sizing",
    "Sunsetting",
    "Herding cats",
)

_CANCEL_HINT = "— ctrl+c to cancel"


def pick_breadcrumb() -> str:
    return random.choice(BREADCRUMBS)


def in_flight_status(breadcrumb: str, width: int) -> str:
    """Status bar text for the in-flight `/ai` state.

    Falls back to a bare ellipsis when `width` cannot hold the breadcrumb -- it is
    dropped whole rather than truncated, so the cancel hint is always intact and never
    reads as a bug (Principle V).
    """
    full = f"{breadcrumb}… {_CANCEL_HINT}"
    if width and len(full) > width:
        return f"⋯ {_CANCEL_HINT}"
    return full


def collection_indicator(active: str) -> str:
    return f"[{active}]"


def link_no_match_status(query: str) -> str:
    """`/link` found nothing matching `query` (FR-044). The line is left exactly
    as typed; this just names the failure."""
    return f"no record matches {query!r}"


def link_ambiguous_status(candidates: Sequence[str]) -> str:
    """`/link` matched more than one record. Names every candidate so the user
    can retype with more specific terms rather than facing a picker (FR-044)."""
    return f"{len(candidates)} records match -- retype with more terms: {', '.join(candidates)}"


def render_version() -> str:
    """The same string both front-ends show for the running version (FR-042):
    `choom --version` prints `choom {__version__}`, this renders `v{__version__}`."""
    return f"v{__version__}"


class StatusBar(Static):
    """A single-line bar with help text on the left and the version pinned to the
    bottom-right (FR-042). Right-alignment is computed against the widget's own
    width so it holds regardless of how long the left-hand text is."""

    def __init__(self, content: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.update(content)

    def update(self, content: str = "", *, layout: bool = True) -> None:  # type: ignore[override]
        text = str(content)
        version = render_version()
        width = self.size.width
        if width and width > len(text) + len(version) + 1:
            pad = width - len(text) - len(version)
            rendered = f"{text}{' ' * pad}{version}"
        else:
            rendered = f"{text}   {version}" if text else version
        super().update(rendered, layout=layout)
