# Implementation Plan: UI Refinements

**Branch**: `011-ui-refinements` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-ui-refinements/spec.md`

## Summary

Five items from issue #32. One adds a capability — records can be deleted, from the list with `ctrl+d`
and from the command line with `<type> delete <id> --force` — and four sharpen surfaces the user meets
constantly: one confirmation component with two named keys, four labelled list columns, the workspace
path in the top-right corner, and a cursor that starts where the next words go.

The deletion work lands in `core` as three functions (`delete_document`, `delete_task`, `delete_by_id`),
with both front-ends calling the same entry point so neither can drift. Everything else is adapter-side:
a `ConfirmDialog` replacing `DiscardDialog`, a pure column-layout module the row renderers call, a
right-aligned path in `CollectionBar`, and a padded editor buffer whose dirty baseline moves with it.

`010-read-on-load` has landed and is merged into this branch, which makes the delete stories smaller than
they were specified: there is no snapshot to invalidate and no view to notify, so a delete writes to disk
and asks the list to re-read.

## Technical Context

**Language/Version**: Python 3.11+ (CI runs 3.11 and 3.13)

**Primary Dependencies**: `textual==8.2.8` (TUI only). No new dependency.

**Storage**: Markdown files in the workspace. Deletion removes a file or a line span; nothing else is
written, and no record of the deletion is kept anywhere.

**Testing**: `pytest` with `pytest-asyncio`, run via `scripts/dev-tests.sh` per the repo's `CLAUDE.md`.
Textual's `run_test()` pilot for TUI integration tests. Layers per Principle VI: `unit/` for the pure
functions (column layout, path shortening, cursor padding, task-line removal), `contract/` for the CLI's
AI-facing delete surface, `integration/` for one end-to-end path per story. No `performance/` change —
this feature adds no budget to protect.

**Target Platform**: Windows, macOS, Linux terminals; no network, no admin rights.

**Project Type**: Single project — a CLI plus a TUI over a shared core library.

**Performance Goals**: None new. Deletion is one file operation; column layout and path shortening are
string work on the rows already being rendered, inside the frame budget `010-read-on-load` established
for a list render.

**Constraints**: 80 columns is the layout target the spec names, and four columns plus a right-aligned
path have to survive it (FR-032, FR-036). Tests must not depend on the wall clock (Principle VI) — none
here does. The confirmation must consume every keystroke (FR-025), which constrains it to a modal screen.

**Scale/Scope**: Hundreds to low thousands of files. Three new source modules (`core/deletion.py`,
`tui/confirm_dialog.py`, `tui/columns.py`), one deleted (`tui/discard_dialog.py`), and edits to
`core/documents.py`, `core/tasks.py`, `cli/main.py`, `tui/list_screen.py`, `tui/edit_screen.py`,
`tui/collection_bar.py`, `tui/status_bar.py`, and `tui/app.tcss`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The initial evaluation and the post-design re-check agree. Phase 1 sharpened gate I — the initial pass
had the TUI deleting a document by path, and the design moved both front-ends onto `delete_by_id` so the
ambiguity and wrong-collection checks cannot be skipped by one caller (research R1).

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS.** Reads: `links.resolve_id` (id → record), `tasks.parse_tasks` / `_body_span` (the span to remove), `documents.scan_month` / `scan_unfiled` and `tasks.load_tasks` (the re-read after a delete, already called by `ListScreen`). Writes: three new core functions — `documents.delete_document`, `tasks.delete_task`, `deletion.delete_by_id` — plus the existing `tasks._atomic_write`. No adapter assembles what core already does: the TUI does **not** unlink a path it happens to hold, it calls `delete_by_id` like the CLI, so the ambiguity check (R4) runs for both. Adapter-side code is presentation only — column layout, path shortening, dialog wording, cursor position — none of which is a workspace operation, and all of which needs a width or a widget to mean anything. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS.** Deletion ships in both front-ends in the same feature (US2 and US3), through one core function. The CLI requires `--force` rather than prompting, so it has no interactive branch to reach (R5); success prints nothing, errors go to stderr, exit codes are the existing 0/1/2/3 with none added or renamed. No `--json` surface changes — `delete` is not a read command. The four presentation stories are inherently interactive and have no CLI counterpart. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS.** No trash, no undo stack, no tombstone — FR-004 forbids exactly the state that would need keeping correct. No new dependency. No new setting: column widths, drop order, and the path form are fixed defaults. Nothing touches the directory tree. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS**, and this is the gate the feature is most exposed to. `delete_task` reuses `set_task_body`'s write path — locate by id, remove exactly the parsed span, preserve the file's line-ending convention and trailing-newline state, leave every other line byte-identical (R2). A malformed line elsewhere in `tasks.md` is skipped with a warning and does not block or corrupt the delete. Deleting a task writes to no other file, so a mirror's line in a document is left exactly as the user typed it (R3). No frontmatter is written by this feature at all. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS.** One new binding, `ctrl+d`, added to the footer where it is active and inert when no record is highlighted (FR-014). `ctrl` is the only modifier used; `ctrl+c` and `ctrl+q` are untouched. Exactly one new confirmation point, deletion, which is the definition of something to lose. The dialog gets *slimmer*, and cursor placement is specified so that opening the editor and leaving raises no confirmation at all (FR-042) — a net reduction in the dialogs a user is taught to dismiss. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS.** The three new core functions carry type hints and docstrings stating what they raise. Tests are chosen by failure mode (R12): the pure layout and removal functions get unit tests where the edge cases actually live, the CLI surface gets contract tests, each story gets one integration path. Six existing tests change because they name `DiscardDialog` or assert the top bar's text; they are updated, not duplicated. Nothing sleeps or reads the wall clock. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS.** No network, no admin rights, no new state outside the workspace. The workspace path is rendered as text with `os.path` string operations and never resolved on the filesystem during a redraw (R9); spaces and non-ASCII render as-is and are covered by an integration case. Deletion removes paths, so it cannot create one that is too long. |

## Project Structure

### Documentation (this feature)

```text
specs/011-ui-refinements/
├── plan.md              # This file
├── research.md          # Phase 0 output — R1..R12
├── data-model.md        # Phase 1 output — entities, what a delete removes, what it never touches
├── quickstart.md        # Phase 1 output — how to validate each story
├── contracts/
│   ├── cli-delete.md    # Phase 1 output — the three delete commands, exit codes, streams
│   └── tui-chrome.md    # Phase 1 output — confirmation, columns, top bar, cursor placement
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── deletion.py           # NEW — delete_by_id: resolve, refuse ambiguity, dispatch
│   ├── documents.py          # CHANGED — delete_document(path)
│   ├── tasks.py              # CHANGED — delete_task(workspace, task_id)
│   ├── links.py              # UNCHANGED — resolve_id already returns what deletion needs
│   └── mirrors.py            # UNCHANGED — the `dead` outcome already covers a deleted task
├── cli/
│   └── main.py               # CHANGED — three `delete` subparsers, --force, three handlers
└── tui/
    ├── confirm_dialog.py     # NEW — ConfirmDialog(ModalScreen[bool]); Esc stops, Enter proceeds
    ├── discard_dialog.py     # DELETED — replaced by ConfirmDialog
    ├── columns.py            # NEW — column_widths / render_row / render_header (pure)
    ├── list_screen.py        # CHANGED — ctrl+d, header row, rows via columns.py
    ├── edit_screen.py        # CHANGED — padded buffer + cursor, ConfirmDialog call site
    ├── collection_bar.py     # CHANGED — right-aligned workspace path
    ├── status_bar.py         # CHANGED — ctrl+d in the footer help strings
    └── app.tcss              # CHANGED — #confirm-dialog replaces #discard-dialog/#discard-buttons

tests/
├── unit/                     # columns, path shortening, cursor padding, delete_task spans
├── contract/                 # the three CLI delete commands
└── integration/              # one path per story; six existing tests updated (R12)
```

**Structure Decision**: Single project, existing layout. Three new modules, each because a pure function
wants a home outside a widget (`columns.py`), a shared component wants one place (`confirm_dialog.py`), or
a core operation spans two record types (`deletion.py`). Nothing else moves.

## Implementation Sequence

The spec's story order is the build order, and one dependency is binding rather than convenient.

1. **US1 — the confirmation.** `ConfirmDialog`, the CSS, the editor call site, the six-test sweep for
   `DiscardDialog` references. **Must land before step 2**: deletion is this feature's only new
   confirmation point, and building it against today's dialog means building it twice (FR-026).
2. **US2 — delete from the list.** `delete_document`, `delete_task`, `delete_by_id`, then `ctrl+d` →
   `ConfirmDialog` → delete → re-read, with the highlight moving to the next record.
3. **US3 — delete from the command line.** Three subparsers and handlers over the same core function.
   No dependency on step 1 — the CLI never confirms.
4. **US4 — mirrors stay in the user's words.** Test-only (R3), against the code from step 2.
5. **US5 — columns.** `columns.py`, the header, the two `_row_text` call sites.
6. **US6 — workspace path.** `CollectionBar` renders it right-aligned.
7. **US7 — cursor placement.** The padded buffer and the moved dirty baseline in `EditScreen`.

Steps 5, 6, and 7 are independent of each other and of steps 1–4, and may be built in any order.

## Phase 0: Research

Complete — see [research.md](./research.md). Twelve decisions (R1–R12), no `NEEDS CLARIFICATION`
markers remain. Notable outcomes:

- Both front-ends delete through `delete_by_id`, so the TUI cannot skip the ambiguity check (R1, R4).
- `delete_task` reuses `set_task_body`'s span-and-write path rather than inventing a second one (R2).
- Mirrors need no code at all — the `dead` outcome already covers it (R3).
- Columns stay in `ListView` with a pure layout function; `DataTable` would rewrite the selection model
  the whole screen is built on (R8).
- Cursor placement pads the buffer *and* moves the dirty baseline, which is what makes "no confirmation
  on an untouched exit" fall out instead of needing a special case (R10).
- The refresh timer already pauses under a modal, and capturing the record id when the dialog is raised
  makes FR-010 true regardless (R11).

## Phase 1: Design

Complete. Artifacts:

- [data-model.md](./data-model.md) — the entities a delete touches, exactly what it removes, and the
  files it must never write to.
- [contracts/cli-delete.md](./contracts/cli-delete.md) — the three delete commands: arguments, streams,
  exit codes, and the non-blocking guarantee.
- [contracts/tui-chrome.md](./contracts/tui-chrome.md) — the confirmation's two keys, the column layout
  and drop order, the top bar's right-aligned path, and the editor's opening cursor.
- [quickstart.md](./quickstart.md) — how to validate each story by hand and which tests cover it.

## Complexity Tracking

No gate failed, and nothing in this feature requires a justification under Principle III. There is no new
source of truth: deletion removes state rather than adding it, and the spec explicitly rules out the
trash, undo, and tombstone mechanisms that would have introduced some.

One judgement worth recording, though it is not a violation: `ConfirmDialog` is parametrised (question and
two labels) rather than hard-coded per call site. That is one class with two arguments instead of two
classes, and FR-026 requires the single component — the alternative is the drift the requirement forbids.
