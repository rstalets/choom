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

from datetime import date, datetime
from pathlib import Path
from typing import Any

from textual.widgets import Input, TextArea

from choom.core.meetings import create_meeting
from choom.core.models import Document, Task, Workspace
from choom.core.notes import create_note
from choom.core.tasks import set_task_state
from choom.tui.edit_screen import EditScreen
from choom.tui.list_screen import DocumentRow, ListView, TaskRow

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


async def submit_editor_line(pilot: Any, editor: TextArea, line_text: str) -> int:
    """Put `line_text` on a new last line of the editor's buffer, place the
    cursor at its end, and press Enter -- exercising the same `_on_key` path a
    real keystroke would, without typing one character at a time. Reuses an
    already-blank trailing line rather than adding a redundant one, the way a
    user placing their cursor there and typing would. Returns the new line's
    index."""
    text = editor.text
    editor.text = text + line_text if text.endswith("\n") else text + "\n" + line_text
    line_index = editor.document.line_count - 1
    editor.cursor_location = (line_index, len(line_text))
    await pilot.press("enter")
    await pilot.pause()
    return line_index


#: --- out-of-process mutation helpers (010-read-on-load) --------------------
#
# These call `choom.core` directly rather than driving the running app through
# a `pilot`. That is the point: the running `ChoomApp` under test receives no
# notification either way, exactly as if a separate process -- an AI
# assistant sharing the workspace -- had made the change. They are still
# in-process Python calls (there is no real second process, no subprocess),
# but from the app-under-test's perspective the workspace changed with no
# announcement, which is the condition US1 exists to handle.


def create_document_out_of_process(
    workspace: Workspace, collection: str, description: str, *, type: str = ""
) -> Document:
    """Create a meeting or note as an outside process would, bypassing the app."""
    if collection == "meetings":
        return create_meeting(workspace, description, type=type)
    return create_note(workspace, description, type=type)


def complete_task_out_of_process(workspace: Workspace, task_id: str) -> Task:
    """Mark a task done as an outside process would, bypassing the app."""
    return set_task_state(workspace, task_id, done=True)


def delete_file_out_of_process(path: Path) -> None:
    """Remove a file as an outside process would, bypassing the app."""
    path.unlink()


def write_malformed_document_out_of_process(
    path: Path, *, text: str = "not frontmatter at all, and not a task file either"
) -> None:
    """Write a file that cannot be parsed as a document, as an outside process
    would -- the shape of a half-written or corrupted file. Any date this or a
    sibling fixture needs should come from `in_scope_month`/`date.today()`
    (Principle VI), the same clock the month-scoped read uses."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def in_scope_month(day: int, hour: int = 9) -> datetime:
    """A datetime inside the month the list scopes to by default.

    The list shows the current month (005), so a fixture pinned to a literal
    month drops out of the default scope the moment real time moves past it --
    which is exactly what happened at the 2026-07/08 boundary, breaking tests
    that had not been touched. Days must be <= 28 to exist in every month.
    """
    today = date.today()
    return datetime(today.year, today.month, day, hour, 0, 0)
