from __future__ import annotations

from textual.widgets import Static

COLLECTIONS = ("tasks", "notes", "meetings")
_LABELS = {"tasks": "Tasks", "notes": "Notes", "meetings": "Meetings"}


class CollectionBar(Static):
    """Non-focusable top bar: `Endpaper >>   Tasks   Notes   Meetings`, with the
    active collection styled. Tab/shift+Tab move between collections; this widget
    only renders the result (research R1)."""

    can_focus = False

    def __init__(self, active: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._active = active
        self.update(self._render_bar())

    def set_active(self, active: str) -> None:
        self._active = active
        self.update(self._render_bar())

    def _render_bar(self) -> str:
        parts = []
        for name in COLLECTIONS:
            label = _LABELS[name]
            if name == self._active:
                parts.append(f"[reverse] {label} [/reverse]")
            else:
                parts.append(f" {label} ")
        return "Endpaper >>  " + "  ".join(parts)
