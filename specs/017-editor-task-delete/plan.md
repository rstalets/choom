# Implementation Plan: Delete a Task From the Line It Lives On

**Branch**: `017-editor-task-delete` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-editor-task-delete/spec.md`

## Summary

With the cursor on a task line in the document editor, `ctrl+t` removes that task from the document and
from `tasks.md` after one confirmation.

The feature is two new functions in `choom.core.mirrors` and one new action on `EditorPane`, with a hard
line between them. Core decides **what** a deletion means; the TUI decides **when to ask** and applies
what core computed.

- `plan_mirror_deletion(workspace, text, line, *, source, body_task_id)` reads the buffer and `tasks.md`,
  **writes nothing**, and returns either `None` (this line is not a task line — FR-008's no-op) or a
  `MirrorDeletion` carrying the outcome, the description to quote, the resulting document text, and the
  character span to remove.
- `commit_mirror_deletion(workspace, plan)` performs the `tasks.md` write, through the existing
  `tasks.delete_task`. It never touches the document.

Three decisions carry the design:

1. **The removal is a character-offset splice, and the same splice serves both consumers.**
   `MirrorDeletion` carries `text` *and* `span`, related by
   `plan.text == original[:span[0]] + original[span[1]:]`. Core's `text` is what a test or any non-widget
   caller uses; the TUI converts `span` to widget coordinates with Textual's own
   `Document.get_location_from_index` and calls `TextArea.delete`. There is one definition of what gets
   removed, and a single assertion — `editor.text == plan.text` — that proves the adapter did not invent
   a second one. Offsets are already this module's idiom: `Mirror.state_offset` and `Link.start`/`end`
   exist for exactly this reason.
2. **The line is removed with `TextArea.delete`, never by assigning `editor.text`.** The `text` setter is
   an alias of `load_text`, which clears the whole session's undo history. `delete` records one undoable
   `Edit`. This is what settles the undo question: **undo restores the line in the buffer, the task stays
   deleted, and the restored line is reported as dead** — the state `reconcile_on_open`/`reconcile_on_save`
   and `tests/integration/test_delete_mirrors.py` already handle. Research R2.
3. **The plan step refuses rather than guesses.** When the id resolves to nothing *and* `tasks.md`
   contains a line `parse_tasks` could not read, nothing is written and the message names the line. choom
   cannot tell "already deleted" from "unreadable" by id alone, and the wrong guess removes the user's
   document line permanently. Scoped precisely — the blocking set is exactly
   `{task_unterminated_comment, task_malformed_comment}`, the two reasons that skip a line *without*
   producing a `Task`; `task_invalid_value` still yields a task and never blocks (FR-022). Research R6.

The plan step also uses `parse_tasks`, not `load_tasks`, because `load_tasks` backfills ids and **writes**
— and a step that runs before the user has confirmed must leave the disk alone (FR-014).

**No new dependency, no new module, no new setting, no new CLI surface.** `choom task delete --force`
already exists and is unchanged, including its documented behaviour of leaving task lines in documents
pointing at nothing; that asymmetry is deliberate and argued in spec.md §"Interface parity".

## Technical Context

**Language/Version**: Python 3.11+ (repo targets 3.11; CI runs 3.11 and 3.13)

**Primary Dependencies**: `textual==8.2.8`, unchanged. **No new dependency.** The one new library call is
`textual.document._document.Document.get_location_from_index`, which ships with the pinned version
(verified).

**Storage**: Markdown files only. Two files are written per successful gesture — `tasks.md` through the
existing `tasks.delete_task`, and the open document through the existing `editing.save_buffer`. No index,
no cache, no per-user state.

**Testing**: `pytest` via `scripts/dev-tests.sh`. One new `tests/unit/` file for the removal rules and the
outcome matrix, one new `tests/integration/` file for the gesture, plus a small extension to
`tests/unit/test_mirror_recognition.py`. No contract or performance test — see research R13.

**Target Platform**: macOS, Linux, Windows. Verified before release on the terminals in
`docs/REQUIREMENTS.md` §4.3.

**Project Type**: Single project — `src/choom/{core,cli,tui}` over `tests/{unit,contract,integration}`.

**Performance Goals**: One `parse_tasks` over `tasks.md` and one scan of a buffer already in memory, per
keypress on a task line — the same cost `/task` pays today. Nothing runs per keystroke or per frame. No
budget to protect, so no performance test is added.

**Constraints**: No admin rights, no network. The document must survive byte-identical outside the removed
line, including its line-ending convention and trailing-newline state. `ctrl+d` must remain unbound by
this feature. `ctrl+c` must remain unbound entirely.

**Scale/Scope**: Roughly 90 lines of new source in `core/mirrors.py`, two fields on `Mirror`, one new
result type and one new `Literal` in `core/models.py`, one binding plus one action (~45 lines) in
`tui/edit_screen.py`, one field on `EditTarget`, and one string in `tui/status_bar.py`.

No NEEDS CLARIFICATION remain: every open question in the spec was resolved in
[research.md](./research.md) against the installed source.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution v2.1.0. **Result: all gates PASS. Complexity Tracking is empty because no
gate failed** — not because the table was skipped.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS.** *Reads*: `mirrors.find_mirrors` (which line is a task line, and which link on it is the task — reused, not re-derived), `tasks.parse_tasks` (the `tasks.md` read; deliberately **not** `load_tasks`, which writes). *Writes*: `tasks.delete_task` for the record — the same function `deletion.delete_by_id`, `choom task delete`, and `ListScreen`'s `ctrl+d` all call — and `editing.save_buffer` for the document, through the pane's existing `_save()`. **No new write primitive.** New in core: `plan_mirror_deletion` and `commit_mirror_deletion` in `src/choom/core/mirrors.py` (the module whose docstring already claims this edge), plus `MirrorDeletion`/`MirrorDeletionOutcome` in `core/models.py`. Both functions take a `Workspace` and a `str` and return a dataclass; neither imports `textual`, touches a stream, or needs an event loop, so Ruff's TID251 ban on `argparse`/`textual`/`rich` in core and `tests/unit/test_core_imports.py` both still hold. **Answering the second half of the gate — is any logic being left in the adapter?** Four candidate decisions were audited and all four are in core: *which line is a task line* (`plan_mirror_deletion` → `find_mirrors`), *what a removal spans* including the last-line-without-a-terminator case (`MirrorDeletion.span`), *whether the line carries extra text* (`extra_text`, from `Mirror.link_start`/`link_end`), and *which of the five drift outcomes applies* (`outcome`). What is left in `EditorPane` is genuinely adapter work: reading `cursor_location`, converting core's offsets with Textual's own `get_location_from_index`, pushing the existing `ConfirmDialog`, and rendering strings. The adapter computes nothing about what to remove, and the assertion `editor.text == plan.text` (contracts/tui.md C6) fails the suite if it ever starts to. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS, with an inherently-interactive carve-out argued in spec.md §"Interface parity".** The gesture decomposes into three parts: deleting a task record (`choom task delete <id> --force`, shipped, non-blocking, flag-not-prompt); removing a checklist line from a markdown document (an assistant edits the body directly — the workflow this constitution's *own* rationale for Principle II names as the reason the CLI has no line-editing surface); and composing the two with the cursor naming the line, which is inherently interactive because the cursor *is* the argument and has no id. **No CLI change at all**: no command, no flag, no `--json` key, no exit code (contracts/core-api.md §4). `choom task delete` keeps its current behaviour of leaving task lines pointing at nothing, which `tests/integration/test_delete_mirrors.py` pins today and which this feature must not change — the asymmetry is deliberate and recorded, not an oversight. Nothing added here prompts, blocks, or writes to a stream. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. Any new setting has a sensible default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS.** No index, database, or cache: `MirrorDeletion` lives for the length of one keystroke and is never persisted, serialised, or written anywhere (data-model.md §5). No new third-party dependency — `get_location_from_index` is a method on the already-pinned `textual==8.2.8`. No new external binary. **No new setting**, so the sensible-default rule is satisfied by there being nothing to configure; the binding is unconditional. Directory layout untouched — no file is created, moved, or renamed. Simplicity was also the deciding factor on three sub-choices: no new core module (two functions in the module that already owns this edge), no new dialog class (the existing `ConfirmDialog`, with wording as the only variable), and no new gating mechanism (one more term in the `check_action` the pane already has). |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS — the dominant gate here, so the mechanisms are named rather than asserted.** *Never re-render, never match text*: the removal is `original[:start] + original[end:]` at offsets `find_mirrors` computed, the same discipline `Mirror.state_offset` exists to enforce (FR-017, FR-018). Exactly one line's terminator is inside the span, so adjacent blank lines, indented continuation beneath the line, and the task line's own indentation are outside it by construction, not by a rule that could be forgotten. *Line endings and the trailing newline*: no new code handles them. `load_for_edit` normalises the buffer to LF and records `newline`/`trailing_newline`; `_apply_line_ending_policy` restores both on every write. A CRLF document survives for the same reason it already survives `/task` (research R5), and a second implementation of that policy is exactly what is avoided. *Malformed input is skipped, not fatal*: `parse_tasks` is unchanged and still logs-and-continues; `plan_mirror_deletion` never raises. FR-021's refusal does not contradict this — it is scoped to the one case where the id genuinely cannot be resolved, and FR-022 keeps an unreadable line from blocking any delete that *can* be resolved. *Never truncate*: `delete_task`'s existing byte guarantee is reused unmodified, and the document write goes through `save_buffer`'s atomic temp-file-and-replace. Every failure path leaves at least one file byte-identical and none leaves a file short (research R8). *`created`/`updated`*: `save_buffer` stamps `updated` and never touches `created`; the record's own removal takes its `created` with it, which is what deletion means. *CommonMark*: removing a whole list item leaves valid CommonMark; nothing is inserted. *No file moved, no tag dropped*: no path is constructed and no tag is parsed anywhere in this feature. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; `ctrl+c` is never bound to anything, `ctrl+q` quits immediately unless something is dirty (in which case it MAY raise the existing confirmation); no non-`ctrl` modifier. | **PASS.** One new binding, `ctrl+t` — `ctrl` only, no other modifier, and not `ctrl+s` (no XOFF concern). It is advertised in `EDIT_HELP` (contracts/tui.md C2), which `tests/unit/test_footer_bindings.py` already enforces mechanically for `EditorPane`, so a hidden key fails the suite. No new screen and no new state: the editor stays the editor. **Confirmations fire only when there is something to lose** — the dialog appears only when core returns a plan; on a line that is not a task line `plan_mirror_deletion` returns `None` and the action renders a status note and stops, so the reflex-dismissal failure the principle warns about cannot occur (FR-008, SC-003). One dialog, the existing `ConfirmDialog`, with Esc changing nothing and Enter proceeding. `ctrl+c` is not bound, inspected, or relied on. `ctrl+q` is untouched, including issue #64's dirty-buffer confirmation. `ctrl+d` is untouched (FR-003) — the whole reason the binding is `ctrl+t`. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS.** Both new core functions carry full type hints and docstrings stating what they do and what they raise — `plan_mirror_deletion` raises nothing, `commit_mirror_deletion` raises `NotFoundError`/`UsageError`/`WorkspaceError`. Coverage is chosen by what can plausibly break, not generated from the spec's 14 acceptance scenarios (research R13): `unit/` carries the weight, because every Principle IV guarantee is decidable against a string — span rules, blank-line and indentation preservation, extra-text detection, and the five-outcome matrix; `integration/` gets one file for the gesture end to end, including cancel-writes-nothing, no-dialog-off-a-task-line, the undo behaviour, and the `editor.text == plan.text` bridge, parametrized across the two hosts only where the host could matter. No `contract/` change (no CLI surface) and no `performance/` change (no budget). No test reads the wall clock; date-bearing fixtures derive dates the way the existing task fixtures do. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS.** No elevation, no network, no subprocess. No path is constructed, joined, or written, so the 260-character Windows budget is untouched — `source` is passed through to `find_links` for link resolution and never opened by the new code. Spaces and non-ASCII in the workspace path and in a task's description are carried verbatim: the description is sliced out of the buffer by offset, never re-encoded or slugified. Offsets are character offsets into a Python `str`, so a multi-byte description cannot be split mid-character. No per-user state is created or read. |

**Post-Phase-1 re-check**: re-evaluated after research.md, data-model.md, contracts/, and quickstart.md
were written. No gate changed status. Phase 1 added no module, no dependency, no setting, and no second
binding beyond the one gate V already covers. Two additive field-level changes surfaced during design —
`Mirror.link_start`/`link_end` and `EditTarget.body_task_id` — and both were re-checked: the first keeps
FR-005/FR-007's "one definition of a task line" true by carrying evidence `find_mirrors` already computes
rather than re-deriving it (gate I), and the second is adapter state describing what the adapter has open,
passed *into* core as an argument with core storing nothing (gate I). Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/017-editor-task-delete/
├── spec.md                    # Approved
├── plan.md                    # This file
├── research.md                # Phase 0 — R1–R13
├── data-model.md              # Phase 1
├── quickstart.md              # Phase 1
├── contracts/
│   ├── core-api.md            # Phase 1 — the two new core functions
│   └── tui.md                 # Phase 1 — binding, footer, dialog, gesture
└── tasks.md                   # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── mirrors.py             # MODIFIED: + plan_mirror_deletion, + commit_mirror_deletion,
│   │                          #           find_mirrors populates the new Mirror fields
│   ├── models.py              # MODIFIED: + MirrorDeletion, + MirrorDeletionOutcome,
│   │                          #           Mirror gains link_start / link_end
│   └── __init__.py            # MODIFIED: export the two functions and the result type
└── tui/
    ├── edit_screen.py         # MODIFIED: + ctrl+t binding, + action_delete_task,
    │                          #           check_action gate, EditTarget.body_task_id,
    │                          #           _save() takes an optional leading note
    └── status_bar.py          # MODIFIED: EDIT_HELP gains "ctrl+t delete task"

tests/
├── unit/
│   ├── test_mirror_deletion.py      # NEW: span rules, preservation, outcome matrix
│   └── test_mirror_recognition.py   # MODIFIED: link_start / link_end
└── integration/
    └── test_editor_task_delete_tui.py  # NEW: the gesture, both hosts, undo, refusals
```

**Structure Decision**: The existing single-project layout is kept and **no new module is added**. The two
core functions go into `src/choom/core/mirrors.py` because that module's docstring already claims exactly
this domain — *"everything about that edge: recognising a mirror, writing one at capture time, pushing a
task's state into a document, and resolving which side wins when a mirror and its task disagree"* — and
because its own plan warns that splitting this grammar across files is "how a byte-preservation guarantee
gets quietly broken", which is the guarantee this feature leans on hardest. `core/deletion.py` was
considered and rejected: it is the by-id record-delete entry point shared by both front-ends and knows
nothing about document text, so putting document-span logic there would give it two unrelated jobs.

On the TUI side the binding and action go on `EditorPane`, not on `EditScreen` or `ListScreen`. The pane is
what both hosts mount, so FR-001's "identical inline and full-screen" holds by construction — the same
reason 014 moved the editor's bindings there, and the reason `tests/unit/test_footer_bindings.py` checks
`EditorPane` against `EDIT_HELP`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*Empty. Every gate above is PASS, so there is no violation to justify. No row here is a placeholder or an
"N/A" — the table has no rows because the design adds no dependency, no setting, no source of truth, no
module, no dialog style, and no CLI surface, and because the one destructive write it performs is an
existing core function called unmodified.*
