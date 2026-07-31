from __future__ import annotations

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
