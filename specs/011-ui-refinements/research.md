# Phase 0 Research: UI Refinements

**Feature**: `011-ui-refinements` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

Twelve decisions. Every `NEEDS CLARIFICATION` from Technical Context is resolved here; none remain.

---

## R1 — Deletion is a `core` capability, not two adapter implementations

**Decision**: three new public functions in `core`, and both front-ends go through the same one.

- `documents.delete_document(path: Path) -> None` — removes a meeting or note file.
- `tasks.delete_task(workspace: Workspace, task_id: str) -> Task` — removes a task's line and body span,
  returning the task as it was.
- `deletion.delete_by_id(workspace: Workspace, record_id: str, *, expect: str | None = None) -> Deleted`
  — resolves an id to a record and dispatches to one of the two above. New module `core/deletion.py`.

The CLI's three `delete` commands and the TUI's `ctrl+d` all call `delete_by_id`. The TUI has a path in
hand for documents and could delete the file directly, and that is exactly the divergence Principle I
exists to prevent — the id path performs the ambiguity check (R4) and the wrong-collection check that a
raw `path.unlink()` would skip.

**Rationale**: Gate I asks both halves. Deletion is workspace logic — locating a record, removing lines
without disturbing neighbours, refusing an ambiguous id — none of which needs a terminal, and all of which
must behave identically in both front-ends.

**Alternatives considered**: *`Path.unlink()` in the TUI and a core function only for the CLI* — two
implementations of one behaviour, and the TUI's would silently skip the checks. *One `delete_record`
handling both kinds inline* — it would re-implement `tasks.py`'s span logic outside `tasks.py`; the split
above keeps each file's own writer in the file that owns its format.

---

## R2 — Task deletion mirrors `set_task_body`'s write path exactly

**Decision**: `delete_task` re-reads and re-parses `tasks.md`, locates the task **by id** among
`parsed.tasks`, takes its body span from `parsed.bodies[index]`, and writes back
`lines[:checkbox_idx] + lines[span.end:]` through the shared `_atomic_write`.

It inherits four properties from `set_task_body`, which is the closest existing writer:

1. Locate by id, never by a cached line number.
2. Ambiguous id → `UsageError` naming the conflicting line numbers; missing id → `NotFoundError`.
3. The file's own line-ending convention is preserved, taken from the first line that has one.
4. The file's trailing-newline state is restored when the deleted block was at the end of the file.

**Rationale**: FR-003 requires every other line to survive byte-for-byte, and `_body_span` already
computes exactly the span a delete must remove — it is the same span `set_task_body` replaces. Reusing it
means indented bodies, blank lines inside bodies, and hand-edited neighbours are handled by code that is
already tested against those cases.

**Alternatives considered**: *Delete the checkbox line only* — orphans the body as stray indented text
under the previous task, which is worse than not deleting. *Re-render the whole file from parsed tasks* —
would normalise the user's formatting everywhere, violating Principle IV for lines nobody asked to touch.

---

## R3 — Mirrors need no code, only a test

**Decision**: deleting a task ships **no** change to `core/mirrors.py`. The dead-mirror path already
exists — `reconcile_on_open` and `reconcile_on_save` emit a `link_dead` warning and a `MirrorResolution`
with outcome `dead` when a mirror's task cannot be found — and a deleted task is exactly "cannot be
found". Story 4 is covered by an integration test proving the mirroring document is untouched, not by new
behaviour.

**Rationale**: The spec asked for the existing resolution to be reused rather than a new one invented,
and the code already treats "the task is gone" as a normal state rather than an error. Adding a
delete-time hook that visited mirroring documents would be the opposite of Principle IV — it would make a
delete write to files the user did not ask to touch.

**Alternatives considered**: *Rewrite mirror lines to plain text on delete* — silently edits the user's
words. *Refuse to delete a mirrored task* — makes the common case (capture a followup, change your mind)
impossible.

---

## R4 — Id resolution refuses ambiguity, and `expect` guards the collection

**Decision**: `delete_by_id` calls `links.resolve_id`, which never raises and returns
`(target | None, warnings)`. `delete_by_id` converts that into the contract deletion needs:

- `target is None` → `NotFoundError`, naming the id.
- any `link_ambiguous` warning → `UsageError`, naming every path that carries the id. `resolve_id`
  returns the first candidate in path-sort order and warns; for reading a link that is a reasonable
  guess, for deleting a file it is not.
- `expect` set and `target.kind` different → `NotFoundError` (`no meeting with id 'note_...'`), so
  `choom meeting delete <note-id>` cannot delete a note.

**Rationale**: FR-007 and FR-008 both say "fail without deleting anything", and FR-008 additionally says
name the ambiguity. `resolve_id`'s warning already carries every conflicting path, so the message is a
re-wrapping rather than a second scan.

**Alternatives considered**: *Accept `resolve_id`'s first candidate* — deletes one of two files the user
did not distinguish between, unrecoverably. *Add an `--all` flag* — bulk deletion is out of scope.

---

## R5 — CLI surface: `<type> delete <id> --force`

**Decision**: three peer subcommands — `choom meeting delete`, `choom note delete`, `choom task delete` —
each taking a positional `id` and requiring `--force`. Without the flag: nothing is deleted, a message on
stderr naming the flag, exit 2. With it and on success: nothing on stdout, exit 0. No `--json`; there is
no data to return, and Principle II requires `--json` on read commands, which this is not.

Exit codes come from the existing `ChoomError` hierarchy with no additions: `NotFoundError` → 1,
`UsageError` → 2, `WorkspaceError` → 3. `main()` already maps them and prints to stderr.

**Rationale**: Principle II requires destructive operations to take an explicit flag rather than prompt.
Making the flag mandatory rather than "prompt unless `--force`" is what keeps the command non-blocking by
construction — there is no interactive branch to accidentally reach.

**Alternatives considered**: `--yes` (reads like an answer to a prompt this command never asks);
`choom delete <id>` as one command (loses the wrong-collection guard from R4, and breaks the pattern where
each record type owns its verbs).

---

## R6 — One `ConfirmDialog` replaces `DiscardDialog`

**Decision**: a new `tui/confirm_dialog.py` holding `ConfirmDialog(ModalScreen[bool])`, parametrised with
the question and the two option labels. `discard_dialog.py` is deleted; both call sites — the editor's
discard and the new delete — construct `ConfirmDialog` with their own wording. `#discard-dialog` and
`#discard-buttons` CSS is replaced by a slim `#confirm-dialog` rule.

The widget is a `Label` for the question and a `Label` for the options, no `Button` at all. Bindings:
`escape` → `dismiss(False)`, `enter` → `dismiss(True)`.

**Rationale**: FR-026 requires that no two confirmations look or behave differently, which is a
statement about there being one component. Removing `Button` is what removes the highlight the spec
objects to — with no focusable child there is nothing to move between, and the two keys are the only
interaction.

**Alternatives considered**: *Keep `DiscardDialog` and add a second dialog for delete* — two components
drift; FR-026 exists to forbid exactly this. *Keep buttons but preselect one* — still teaches the user to
look for a highlight, and still leaves `tab` meaningful inside a two-key dialog.

---

## R7 — A modal screen already gives key capture and centring

**Decision**: `ConfirmDialog` stays a `ModalScreen`, centred with `align: center middle` on the screen
rule and `width: auto; height: auto` on the dialog. FR-025 (no keystroke reaches the screen underneath)
needs no new code: a modal screen does not pass keys to the screen below, and with no focusable child,
`tab` and arrow keys do nothing.

**Rationale**: FR-021's "centred on the whole screen regardless of which pane raised it" is a property of
being a screen rather than a widget inside a pane — the existing `DiscardDialog` already had it, and it
is the one thing about today's dialog worth keeping.

**Alternatives considered**: *An inline bar docked inside the active pane* — would need its own key
capture, its own focus save/restore, and would sit over one pane rather than centred, contradicting
FR-021.

---

## R8 — Columns are computed text in the existing `ListView`, not a `DataTable`

**Decision**: keep `ListView` with one `ListItem` per record. Add a pure function in a new
`tui/columns.py`:

```python
def column_widths(total: int) -> ColumnLayout      # which columns survive, and how wide
def render_row(cells: Sequence[str], layout: ColumnLayout) -> str
def render_header(layout: ColumnLayout) -> str
```

`DocumentRow._row_text` and `TaskRow._row_text` become calls to `render_row`. A `Static` header sits above
the `ListView` inside `#list-pane`, so it does not scroll. Both re-render on `Resize`.

Truncation is by character count with a `…` in the final cell position. Drop order is tags, then type
(FR-032); date and title always survive.

**Rationale**: `DataTable` gives columns for free but replaces the row-selection model the whole screen is
built on — `ListView.Highlighted`/`Selected` drive the preview, the links pane, edit, toggle, and the
refresh timer's selection-preserving re-render. Swapping it would rewrite behaviour this feature is not
about, and would put `DocumentRow`/`TaskRow` — which carry `document`/`record` and are read by name in
tests and in `list_screen` — out of reach.

A pure layout function is also the only part of this story with real edge-case density (widths, drop
order, ellipsis), so it belongs where it can be unit-tested without a terminal.

**Alternatives considered**: *`DataTable`* — above. *Rich `Table` rendered into each `ListItem`* — a
table per row cannot align across rows, which is the entire point. *Fixed column widths* — breaks at
80 columns, which is the target the spec names.

---

## R9 — The workspace path renders inside `CollectionBar`, right-aligned

**Decision**: `CollectionBar` takes the workspace path and renders it flush right, padding between the
collections and the path so the path ends at the bar's last column. Shortening, in order:

1. Replace a `$HOME` prefix with `~` (FR-035).
2. If it still does not fit, elide from the left with `…/`, keeping whole path components and always the
   final one (FR-036).
3. If even the final component does not fit, the collections drop to their existing compact
   one-letter form first (that fallback already exists) and the path keeps its final component.

The path is computed with `os.path` string operations, not `Path.resolve()` — no filesystem access on a
resize.

**Rationale**: FR-034 wants a corner anchor, and `Static.update` with computed padding is how `StatusBar`
already pins the version to the bottom-right. Reusing that shape keeps two bars behaving the same way and
adds no layout container.

**Alternatives considered**: *A separate right-docked widget in the top bar* — a second widget to keep in
sync with the bar's compact-mode fallback. *Truncating from the right* — drops the workspace's own name,
which is the part that identifies it.

---

## R10 — Cursor placement pads the buffer and moves the dirty baseline with it

**Decision**: `EditScreen` computes the padded text once at construction: the file's text with trailing
blank lines normalised to exactly one, plus the line the cursor sits on. `original_text` is set to that
padded text, and the `TextArea` is loaded with it. The cursor goes to the last line, column 0.

Because `is_dirty` compares against `original_text`, the padding is not a change, so leaving without
typing raises no confirmation and writes nothing (FR-042).

**Rationale**: A `TextArea` cursor cannot be placed past the end of the buffer, so "one blank line below
the content" requires the lines to exist. The only question is what counts as the unedited state, and
answering "the buffer as opened" is both the simplest rule and the one that makes FR-042 fall out rather
than needing a special case.

**Consequence, accepted**: a user who enters edit mode and *saves* without typing writes a file with one
trailing blank line it did not have. That is a save the user asked for, it changes no content, and it is
idempotent — the second such save writes the same bytes. The alternative, stripping trailing blanks at
save time, changes what the editor saves, which the spec puts out of scope.

**Alternatives considered**: *Leave the buffer alone and place the cursor at the end of the last line* —
no blank line, contradicts FR-039. *Pad the buffer but keep `original_text` as the file text* — every
open would be dirty and every exit would raise a confirmation, which is precisely the reflex-dismissal
failure Principle V names.

---

## R11 — The refresh timer and the confirmation cannot collide

**Decision**: no coordination code. `ListScreen` pauses its refresh timer in `on_screen_suspend`, and
pushing a `ModalScreen` suspends the screen below, so the timer is already stopped while a confirmation
is up. FR-010 (the confirmation acts on the record it named) is satisfied by capturing the record's id
when the dialog is raised and passing it to the callback, rather than re-reading the highlight when the
dialog returns.

**Rationale**: The captured id costs one attribute and makes the requirement true independently of
whether the dialog suspends the screen — so a later change to the dialog's presentation cannot
reintroduce the bug.

**Alternatives considered**: *Explicitly pause the timer around the dialog* — duplicates what
suspend/resume already does, and would need undoing if the dialog ever stops being a screen. *Re-read the
highlight in the callback* — the bug itself.

---

## R12 — Test layers, and the six existing tests that change

**Decision**: tests run through `scripts/dev-tests.sh` (repo `CLAUDE.md`), which is
`uv run --extra dev pytest -n <2× cores>`. Coverage is risk-based per Principle VI:

| Layer | What it covers here |
|---|---|
| `unit/` | `column_widths`/`render_row` (drop order, ellipsis, empty cells), path shortening, cursor-placement padding, `delete_task` line preservation |
| `contract/` | the three CLI `delete` commands: exit codes, stderr-not-stdout, `--force` required, non-blocking with stdin closed |
| `integration/` | `ctrl+d` → confirm → gone, and → decline → unchanged; the discard confirmation on the new dialog; a deleted task's mirrors; the header and columns on a real screen; the path in the top bar |
| `performance/` | none. No new budget — deletion is one file operation and column layout is string work |

Existing tests that change:

1. `tests/integration/test_discard_tui.py` — imports `DiscardDialog` and calls `dialog.dismiss(True)`;
   moves to `ConfirmDialog` and to key presses.
2. `tests/integration/test_task_body_tui.py` and 3. `tests/integration/test_mirror_propagation.py` —
   both reference the discard dialog by name.
4. `tests/integration/test_chrome_tui.py` — asserts the top bar's rendered text, which now carries the
   path.
5. `tests/integration/test_narrow_terminal_tui.py` — asserts the compact collection fallback, which now
   shares the bar with the path.
6. `tests/integration/test_collection_menu_tui.py` — same bar, same reason.

`tests/helpers.py`'s `row_titles` reads `row.document.title`, not the rendered label, so the column change
does not touch it. `delete_file_out_of_process` already exists there (added by `010-read-on-load`) and is
what the stale-row test uses.

**Wall clock**: no test in this feature sleeps or reads the current date. The refresh-timer interaction
in R11 is asserted by pushing the dialog and checking the timer is paused, not by waiting for a tick.
