from __future__ import annotations

import os
import re

from textual import events
from textual.widgets import Static

COLLECTIONS = ("tasks", "notes", "meetings")
_LABELS = {"tasks": "Tasks", "notes": "Notes", "meetings": "Meetings"}
_MARKUP_TAG = re.compile(r"\[/?[a-z]+\]")


def _apply_home(path: str) -> str:
    """Replace a leading `$HOME` with `~` (FR-035). String comparison only --
    `os.path.expanduser` reads the `HOME` environment variable, never the
    filesystem, so this never touches disk (research R9)."""
    home = os.path.expanduser("~")
    if home and home != "~" and (path == home or path.startswith(home + os.sep)):
        return "~" + path[len(home) :]
    return path


def shorten_workspace_path(path: str, available: int) -> str:
    """`path`, shortened to fit `available` characters for the top bar's
    right-hand corner (FR-034--FR-037).

    `$HOME` is replaced with `~` first. If it still does not fit, the path is
    elided from the left with `…/`, dropping whole leading components one at
    a time -- never a partial one -- until what remains fits or only the
    final component (the part that identifies the workspace) is left. That
    final component is always kept whole, however narrow `available` is: a
    path that vanishes on a narrow terminal is worse than one that overflows
    it (spec edge case).

    Pure string arithmetic -- no filesystem access, so it is safe to call on
    every redraw (research R9). Never raises.
    """
    homed = _apply_home(path)
    if available <= 0 or len(homed) <= available:
        return homed

    sep = "/" if "/" in homed else os.sep
    parts = [p for p in homed.split(sep) if p]
    if len(parts) <= 1:
        return homed

    best = parts[-1]
    for count in range(2, len(parts) + 1):
        candidate = "…" + sep + sep.join(parts[-count:])
        if len(candidate) <= available:
            best = candidate
        else:
            break
    return best


class CollectionBar(Static):
    """Non-focusable top bar: `Choom >>   Tasks   Notes   Meetings`, with the
    active collection styled, and the workspace path flush right (US6).
    Tab/shift+Tab move between collections; this widget only renders the
    result (research R1).

    Below the width the full form needs, the collections fall back to a
    one-letter-per-collection form so the highlighted collection never
    scrolls out of view (spec edge case: "a terminal too narrow for three
    panes plus the top bar"). That fallback decision is made from the
    collections' own width alone, never from whether a path would also fit
    -- the collection names keep their position and full text; the path is
    what gives way (FR-036)."""

    can_focus = False

    def __init__(self, active: str, workspace_path: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._active = active
        self._workspace_path = workspace_path
        self.update(self._render_bar())

    def set_active(self, active: str) -> None:
        self._active = active
        self.update(self._render_bar())

    def on_resize(self, event: events.Resize) -> None:
        self.update(self._render_bar())

    def _render_bar(self) -> str:
        collections_text = self._render_full()
        width = self.size.width
        if width and len(_MARKUP_TAG.sub("", collections_text)) > width:
            collections_text = self._render_compact()

        if not self._workspace_path or not width:
            return collections_text

        plain_len = len(_MARKUP_TAG.sub("", collections_text))
        available = width - plain_len - 1  # at least one column of gap
        if available <= 0:
            return collections_text

        path_text = shorten_workspace_path(self._workspace_path, available)
        pad = max(1, width - plain_len - len(path_text))
        return f"{collections_text}{' ' * pad}{path_text}"

    def _render_full(self) -> str:
        parts = []
        for name in COLLECTIONS:
            label = _LABELS[name]
            if name == self._active:
                parts.append(f"[reverse] {label} [/reverse]")
            else:
                parts.append(f" {label} ")
        return "Choom >>  " + "  ".join(parts)

    def _render_compact(self) -> str:
        parts = []
        for name in COLLECTIONS:
            letter = _LABELS[name][0]
            if name == self._active:
                parts.append(f"[reverse]{letter}[/reverse]")
            else:
                parts.append(letter)
        return " ".join(parts)
