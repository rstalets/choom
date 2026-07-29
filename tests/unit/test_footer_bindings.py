from __future__ import annotations

from textual.binding import Binding

from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import ListScreen
from endpaper.tui.preview_screen import PreviewScreen
from endpaper.tui.status_bar import EDIT_HELP, LIST_HELP, PREVIEW_HELP, TASK_LIST_HELP

# Keys bound outside a screen's own BINDINGS but legitimately advertised in its
# footer: "enter" is handled via a ListView.Selected message, not a Screen action;
# "ctrl+q" is bound once, app-wide, in EndpaperApp.BINDINGS.
_NOT_SCREEN_LOCAL = {"enter", "ctrl+q"}

_KEY_DISPLAY = {
    "escape": "esc",
    "up": "↑",
    "down": "↓",
    "pageup": "pgup",
    "pagedown": "pgdn",
    # ListScreen's left/right are arrow-key aliases for h/l (pane focus); the
    # footer names the letter keys only, so check for the letter they alias.
    "left": "h",
    "right": "l",
}


def _shown_keys(screen_cls: type) -> set[str]:
    keys = set()
    for entry in screen_cls.BINDINGS:
        binding = entry if isinstance(entry, Binding) else Binding(*entry)
        if not binding.show:
            continue
        keys.update(binding.key.split(","))
    return keys


def _assert_footer_advertises_every_shown_binding(screen_cls: type, help_text: str) -> None:
    for key in _shown_keys(screen_cls):
        display = _KEY_DISPLAY.get(key, key)
        assert display in help_text, (
            f"{screen_cls.__name__} binds {key!r} with show=True, "
            f"but {display!r} is not in its footer {help_text!r}"
        )


def test_list_screen_footer_advertises_every_shown_binding() -> None:
    # ListScreen is one screen shared by three collections; "space"/"a" (task
    # toggles) only make sense when the tasks collection is active, so they're
    # advertised in TASK_LIST_HELP rather than LIST_HELP. Check against the
    # union of both footers this single screen can show.
    combined_help = f"{LIST_HELP}   {TASK_LIST_HELP}"
    _assert_footer_advertises_every_shown_binding(ListScreen, combined_help)


def test_preview_screen_footer_advertises_every_shown_binding() -> None:
    _assert_footer_advertises_every_shown_binding(PreviewScreen, PREVIEW_HELP)


def test_edit_screen_footer_advertises_every_shown_binding() -> None:
    _assert_footer_advertises_every_shown_binding(EditScreen, EDIT_HELP)


def test_edit_help_names_no_key_edit_screen_does_not_bind() -> None:
    bound = _shown_keys(EditScreen) | _NOT_SCREEN_LOCAL
    displayed = {_KEY_DISPLAY.get(k, k) for k in bound}
    for token in ("ctrl+o", "ctrl+x", "esc", "ctrl+q"):
        assert token in EDIT_HELP
        assert token in displayed


def test_preview_help_names_no_key_preview_screen_does_not_bind() -> None:
    bound = _shown_keys(PreviewScreen) | _NOT_SCREEN_LOCAL
    displayed = {_KEY_DISPLAY.get(k, k) for k in bound}
    for token in ("e", "esc", "ctrl+q"):
        assert token in PREVIEW_HELP
        assert token in displayed
