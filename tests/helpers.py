"""Shared test helpers for driving the two adapters.

The TUI helpers exist mostly for speed. Under `run_test()`, booting the app costs
~83ms but every `pilot.press()` costs 47ms idle and 84ms with the command bar
focused, so typing a 38-character command one key at a time costs ~3.4 seconds.
`type_command` sets the input's value in a single assignment instead, which is
~11x faster and produces byte-identical results -- `CommandBar` reacts only to
`Input.Changed` (posted by the reactive `value` watcher on any assignment) and
`Input.Submitted`.
"""

from __future__ import annotations

from typing import Any

from textual.widgets import Input

from endpaper.tui.edit_screen import EditScreen
from endpaper.tui.list_screen import DocumentRow, ListView, TaskRow

#: Collection verbs, in the order the collection bar cycles with `tab` from launch.
COLLECTIONS = ("tasks", "notes", "meetings")


async def open_bar(app: Any, pilot: Any) -> Input:
    """Open the command bar and return its `Input` widget."""
    await pilot.press("/")
    await pilot.pause()
    return app.screen.query_one("#bar-input", Input)


async def type_command(app: Any, pilot: Any, text: str, *, submit: bool = True) -> None:
    """Put `text` into the command bar in one assignment, then optionally submit.

    Equivalent to typing for any test that asserts on the *outcome*. Use
    `type_literally` when the test is about what happens *while* typing.

    The cursor is moved to the end explicitly: Textual's `Input` only snaps
    `cursor_position` to the end of the value on the first assignment after
    mount, so without this a following `backspace` would delete from wherever
    the cursor happened to be rather than from the end of `text`.
    """
    bar = await open_bar(app, pilot)
    bar.value = text
    bar.cursor_position = len(text)
    await pilot.pause()
    if submit:
        await pilot.press("enter")
        await pilot.pause()


async def type_literally(pilot: Any, text: str) -> None:
    """Type `text` one keystroke at a time.

    Slow, and deliberately so: this is kept for the tests that assert on
    incremental behaviour -- the undeletable `/` prefix, a retyped `/` being read
    as text rather than a mode switch, and filtering that narrows as you type.
    Those are the tests that would catch a regression in `type_command`'s
    shortcut, so they must not be converted to it.
    """
    for ch in text:
        await pilot.press("space" if ch == " " else ch)


async def to_collection(app: Any, pilot: Any, name: str) -> None:
    """Switch to the `name` collection ("tasks" | "notes" | "meetings")."""
    await type_command(app, pilot, name)


async def open_edit(app: Any, pilot: Any, *, collection: str = "meetings") -> EditScreen:
    """From the list, open the first row's preview and then its editor."""
    await to_collection(app, pilot, collection)
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("e")
    await pilot.pause()
    assert isinstance(app.screen, EditScreen)
    return app.screen


def list_view(app: Any) -> ListView:
    return app.screen.query_one("#meeting-list", ListView)


def row_titles(app: Any) -> list[str]:
    """Titles of the document rows currently listed, in display order."""
    return [r.document.title for r in list_view(app).children if isinstance(r, DocumentRow)]


def task_rows(app: Any) -> list[TaskRow]:
    """The task rows currently listed, in display order."""
    return [r for r in list_view(app).children if isinstance(r, TaskRow)]
