from __future__ import annotations

import re

from textual import events
from textual.widgets import Static

COLLECTIONS = ("tasks", "notes", "meetings")
_LABELS = {"tasks": "Tasks", "notes": "Notes", "meetings": "Meetings"}
_MARKUP_TAG = re.compile(r"\[/?[a-z]+\]")


class CollectionBar(Static):
    """Non-focusable top bar: `Choom >>   Tasks   Notes   Meetings`, with the
    active collection styled. Tab/shift+Tab move between collections; this widget
    only renders the result (research R1).

    Below the width the full form needs, it falls back to a one-letter-per-
    collection form so the highlighted collection never scrolls out of view
    (spec edge case: "a terminal too narrow for three panes plus the top bar")."""

    can_focus = False

    def __init__(self, active: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._active = active
        self.update(self._render_bar())

    def set_active(self, active: str) -> None:
        self._active = active
        self.update(self._render_bar())

    def on_resize(self, event: events.Resize) -> None:
        self.update(self._render_bar())

    def _render_bar(self) -> str:
        full = self._render_full()
        width = self.size.width
        if width and len(_MARKUP_TAG.sub("", full)) > width:
            return self._render_compact()
        return full

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
