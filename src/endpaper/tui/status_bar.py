from __future__ import annotations

from textual.widgets import Static

LIST_HELP = "/ filter or command   ↑↓/jk move   h/l pane   enter open   ctrl+q quit"
PREVIEW_HELP = "esc back   ↑↓/pgup/pgdn scroll   ctrl+q quit"


def collection_indicator(active: str) -> str:
    return f"[{active}]"


class StatusBar(Static):
    pass
