from __future__ import annotations

import pytest
from textual.binding import Binding

from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import ListScreen
from endpaper.tui.preview_screen import PreviewScreen
from endpaper.tui.status_bar import (
    EDIT_HELP,
    LINKS_SECTION_HELP,
    LIST_HELP,
    PREVIEW_HELP,
    TASK_LIST_HELP,
)

# The only shown-binding key whose footer spelling differs from its Binding.key.
_KEY_DISPLAY = {"escape": "esc"}


def _shown_keys(screen_cls: type) -> set[str]:
    keys = set()
    for entry in screen_cls.BINDINGS:
        binding = entry if isinstance(entry, Binding) else Binding(*entry)
        if not binding.show:
            continue
        keys.update(binding.key.split(","))
    return keys


@pytest.mark.parametrize(
    ("screen_cls", "help_text"),
    [
        # ListScreen is one screen shared by three collections; "space"/"a" (task
        # toggles) only make sense when the tasks collection is active, so they're
        # advertised in TASK_LIST_HELP rather than LIST_HELP. Check against the
        # union of both footers this single screen can show.
        (ListScreen, f"{LIST_HELP}   {TASK_LIST_HELP}"),
        (PreviewScreen, PREVIEW_HELP),
        (EditScreen, EDIT_HELP),
    ],
)
def test_footer_advertises_every_shown_binding(screen_cls: type, help_text: str) -> None:
    for key in _shown_keys(screen_cls):
        display = _KEY_DISPLAY.get(key, key)
        assert display in help_text, (
            f"{screen_cls.__name__} binds {key!r} with show=True, "
            f"but {display!r} is not in its footer {help_text!r}"
        )


# --- US7: the Links section footer ---------------------------------------------


def test_preview_help_advertises_the_links_toggle() -> None:
    assert "b backlinks" in PREVIEW_HELP


def test_links_section_help_advertises_move_open_and_close() -> None:
    assert "↑↓" in LINKS_SECTION_HELP
    assert "enter/o open" in LINKS_SECTION_HELP
    assert "esc" in LINKS_SECTION_HELP
    assert "ctrl+q" in LINKS_SECTION_HELP


@pytest.mark.parametrize("help_text", [PREVIEW_HELP, LINKS_SECTION_HELP])
def test_footer_strings_fit_80_columns(help_text: str) -> None:
    assert len(help_text) <= 80


def test_task_list_footer_names_e_for_editing_a_tasks_body() -> None:
    # `e` on a task row went from a no-op to opening the body editor (007) --
    # it must be spelled out in the tasks footer, not merely covered by the
    # weak substring check every other binding gets above (FR-024).
    assert "e edit" in TASK_LIST_HELP
