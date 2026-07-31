from __future__ import annotations

import random

from textual.widgets import Static

from endpaper import __version__

LIST_HELP = (
    "tab collection   / filter or command   ↑↓/jk move   h/l pane   "
    "enter open   e edit   ctrl+q quit"
)
TASK_LIST_HELP = (
    "tab collection   / filter or command   ↑↓/jk move   h/l pane   space toggle   ctrl+q quit"
)
PREVIEW_HELP = "e edit   esc back   ↑↓/pgup/pgdn scroll   ctrl+q quit"
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


def render_version() -> str:
    """The same string both front-ends show for the running version (FR-042):
    `endpaper --version` prints `endpaper {__version__}`, this renders `v{__version__}`."""
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
