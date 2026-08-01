# Quickstart: UI Refinements

**Feature**: `011-ui-refinements` | **Plan**: [plan.md](./plan.md)

How to validate each story by hand, and which tests cover it. Every command runs from the repository
root.

---

## Prerequisites

```bash
uv sync --extra dev
```

Tests always run through the repo's script, not a hand-rolled `pytest` (see `CLAUDE.md`):

```bash
scripts/dev-tests.sh                       # whole suite, parallel
scripts/dev-tests.sh tests/unit -k columns # args pass straight through
```

A scratch workspace to poke at:

```bash
mkdir -p /tmp/choom-011 && cd /tmp/choom-011
uv run --project <repo> choom init
uv run --project <repo> choom meeting new "standup" --type sync
uv run --project <repo> choom note new "reading list"
uv run --project <repo> choom task add "call Terry" --type followup
```

---

## US1 — Confirmations are a line with two named keys

1. Launch the TUI, highlight a note, press `e`, type a character.
2. Press `esc`.

**Expect**: a slim bar centred on screen, two options, each naming its key and its outcome. `Esc` returns
to the editor with the character still there; `Enter` leaves without saving. Pressing `tab`, arrow keys,
or any other key does nothing and does not reach the list underneath.

Repeat at 80 columns and at a wide width — it stays centred and readable.

**Tests**: `tests/integration/test_discard_tui.py` (updated to `ConfirmDialog` and key presses).

---

## US2 — Delete a record from the list

1. Highlight the standup meeting. Press `ctrl+d`. The dialog names it.
2. Press `Esc` → still there, highlight unmoved.
3. Press `ctrl+d`, then `Enter` → the row is gone and the file is gone from `meetings/`.
4. Switch to Tasks, delete a task with a multi-line body, then open `tasks.md`.

**Expect**: the task's line and its whole body are gone; every other task is byte-identical, in order,
with its own body intact. Deleting the last record moves the highlight up; deleting the only record shows
the empty state.

To check the stale-row path: delete a file outside the tool, then press `ctrl+d` on its row and confirm —
the status bar says the record no longer exists and the list refreshes.

**Tests**: `tests/integration/test_delete_tui.py`, `tests/unit/test_delete_task.py`.

---

## US3 — Delete from the command line

```bash
choom task list --json                      # copy an id
choom task delete <id> --force ; echo $?    # 0, nothing on stdout
choom task delete <id> --force ; echo $?    # 1, message on stderr
choom note delete <id>         ; echo $?    # 2, refuses without --force
choom meeting delete <note-id> --force      # 1, wrong collection
```

Non-blocking check:

```bash
choom task delete <id> --force < /dev/null > out.txt 2> err.txt ; echo $?
```

**Expect**: returns immediately, `out.txt` empty, no escape sequences anywhere.

**Tests**: `tests/contract/test_cli_delete.py`.

---

## US4 — A deleted task's mirrors stay in the user's words

1. From a note in the editor, capture a task with `/task.followup call Terry`.
2. Note the checkbox line the editor leaves behind. Copy the file's bytes.
3. Delete that task (either front-end).
4. Open the note again.

**Expect**: the checkbox line is byte-for-byte what it was; a dead-link warning is surfaced; ticking the
box still saves.

**Tests**: `tests/integration/test_delete_mirrors.py`.

---

## US5 — Four labelled columns

Create records with every combination of type present/absent and tags present/absent.

**Expect**: a header row above the list naming date, type, title, tags; titles starting at the same
column on every row; empty cells where a value is missing; long titles truncated with `…` and no wrapping.
Narrow the terminal — tags drop first, then type, each with its header; date and title stay.

**Tests**: `tests/unit/test_columns.py`, `tests/integration/test_list_columns_tui.py`.

---

## US6 — The top bar names the workspace

Launch in two different workspaces, including one whose path contains a space and a non-ASCII character,
and one under `$HOME`.

**Expect**: the path flush with the top-right corner, `~` for the home prefix, elided from the left with
`…/` when long, final component always readable. Resize — it stays in the corner. The bottom bar is
exactly as it was.

**Tests**: `tests/unit/test_workspace_path.py`, `tests/integration/test_chrome_tui.py` (updated).

---

## US7 — The cursor starts where the next words go

1. Open an existing multi-line note with `e`.

**Expect**: the cursor is on an empty line, one blank line below the last content. Type — the character
lands there.

2. Press `esc` immediately after opening, without typing.

**Expect**: no confirmation, and the file's bytes on disk are unchanged.

3. Open a note whose file already ends in several blank lines.

**Expect**: exactly one blank line above the cursor, not more.

**Tests**: `tests/unit/test_cursor_placement.py`, `tests/integration/test_edit_from_list_tui.py`.

---

## Full check before opening the PR

```bash
scripts/dev-tests.sh
uv run --extra dev ruff format --check .
uv run --extra dev ruff check .
uv run --extra dev mypy
```
