# Implementation Plan: Inline Task Capture

**Branch**: `009-inline-task-capture` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-inline-task-capture/spec.md`

## Summary

Typing `/task.followup call Terry about the renewal #procurement` on its own line in the editor creates a
task and leaves a working checkbox in the document pointing at it. The task records the document it came
from as an ordinary link; the checkbox is a control surface onto the task's state, not a copy of it, and
ticking either end updates the other.

The technical approach is one new core module, `endpaper/core/mirrors.py`, holding everything about that
edge: recognising a checkbox-link as a mirror, writing one, pushing a task's state into a document, and
resolving which side wins when they disagree. Recognition composes `find_links()` from `008-document-links`
(which already excludes code fences, spans, images, and URL destinations) with a checklist-prefix match.
Every write into a document is a one-character splice located by the task's id — never a re-render, never
a line number, never a text match.

Two properties do most of the work. First, there are two write paths, not one: a user save stamps
`updated` and runs through the existing `save_buffer`; a sync write (from a toggle in the tasks list, or
from reconcile-on-open) stamps nothing and uses its own atomic writer. Second, "since they last agreed" is
a session baseline held in the `EditScreen` and passed into a stateless core function, which makes the
both-sides-changed case detectable while persisting nothing.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: standard library, plus `textual` for the TUI adapter only. No new dependency.

**Storage**: markdown files in the workspace — `tasks.md` at the root and the documents under `meetings/`
and `notes/`. No new file, no index, no cache.

**Testing**: `pytest`. New tests in `tests/unit/` (mirror recognition, splice writing, the conflict
matrix, `parse_line`'s dotted suffix), `tests/integration/` (capture, toggle propagation, reconcile on
open and save — parametrized across adapters where both have the behaviour), `tests/contract/` (the
`--link` option, exit codes, `--json` schema, stream separation), and one `tests/performance/` test for
reconcile-on-open.

**Target Platform**: Windows, macOS, Linux. Windows is first-class.

**Project Type**: single Python package — a library core with two thin adapters (CLI and TUI).

**Performance Goals**: reconcile-on-open adds under 50 ms on a workspace holding several years of
documents (SC-008), and reads no file at all when the document has no mirrors (SC-007). Capture completes
in under 200 ms keypress to cursor (SC-012).

SC-008's 50 ms is a claim about a user's machine and it holds — roughly 5 ms measured serially on
5,840 tasks. It is deliberately not asserted as a wall-clock bound in CI, which runs `pytest -n auto`
on a shared runner where the same code measured 0.055 s and 0.174 s on two runners of one build. The
test asserts the engineering claim instead: reconciling costs within a small multiple of the single
`tasks.md` read it cannot avoid, measured in the same process under the same load, with a loose
absolute backstop. The regression it guards against — scanning the workspace instead of reading one
file — is orders of magnitude, not a fraction, so the relative bound catches it and does not flake.

**Constraints**: offline; no admin rights; no new external binary; the mirror's destination path is
derived by 008's `relative_destination`, which already produces forward slashes on every platform and
round-trips from every depth the layout produces.

**Scale/Scope**: hundreds to low thousands of documents; a `tasks.md` of hundreds of lines; zero to a
handful of links per task.

**Dependency, now satisfied**: `008-document-links` merged into `main` (PR #40) and into this branch at
`e166ae8`. This feature consumes `find_links`, `format_link`, `resolve_id`, `relative_destination`, the
`links` field on task lines and on `Task`, the `ScanWarningReason` additions, and the `write_text_atomic`
primitive 008 landed in `core/atomic_write.py`. None of that is reimplemented here.

Four things in the shipped code differ from what this plan assumed while 008 was still in flight, and the
tasks follow the code: `find_links` takes no `in_tasks_field` argument (it is a field on `Link`);
`add_task` did **not** gain `links`, so adding it is still this feature's job; `format_link` exists and the
mirror is built through it rather than assembled by hand; and `write_text_atomic` replaces the temp-file
sequence the sync writer would otherwise have repeated. The full delta is at the head of
[tasks.md](tasks.md#-prerequisite-met).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Mark each gate PASS / FAIL / N/A with a one-line justification. Any FAIL must appear in
Complexity Tracking below with a rejected simpler alternative, or the plan does not proceed.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — recognition, splicing, conflict resolution, and both write paths live in `core/mirrors.py` and take plain strings, paths, and a `Workspace`. The adapters supply the baseline and place the cursor. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — capture with a link is reachable both ways (`/task` in the editor, `task add --link`); completion propagates from both (`space`, `task done`/`undone`). Reconcile-on-open has no CLI counterpart because the CLI has no command that opens or reads a document (research R6); the typing gesture itself is inherently interactive. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — nothing new is persisted. The session baseline is in-memory for the life of one screen and is discarded on close; it describes the editing session, not the workspace. No new dependency, no new setting. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS with one documented deviation** — a sync write deliberately does not stamp `updated` (FR-029); see Complexity Tracking. Everything else holds: recognition never raises, a malformed task line is skipped and warned, a dead mirror is left byte-identical, and every write is a one-character splice that touches no other byte. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — no new key binding at all. `/task` is typed, and it appears in the editor's command list the same way `/ai` does, so discoverability comes from the existing surface. No new screen and no new confirmation. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock; public API changes recorded in the changelog. | **PASS** — every new public function is typed and documented with what it raises. Coverage is concentrated on the conflict matrix, the splice's byte preservation, and recognition edge cases, which is where this can actually break; one performance test guards the only new hot path. **Wall clock (added in v1.2.0)**: re-audited after the amendment. Six of this feature's test files carry date literals; all six are synthetic paths handed to pure string or parsing functions, or `created:` values on task lines. None reaches a month-scoped view, and `tasks.md` is not month-partitioned, so none can fall out of a listing as the calendar moves. `--link`, the `--json` additions, and the reconciliation behaviour are in the changelog. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no network, no install requirement, no per-user state. Mirror destinations are link text inside a file, so they do not consume filesystem path budget; separator and space handling are 008's `relative_destination` contract. |

**Post-design re-check (after Phase 1)**: unchanged. The contracts in `contracts/` introduce no new
persisted state, no new dependency, and no new binding; the one deviation under IV is the same one
identified before design and is argued in Complexity Tracking rather than widened.

**Re-check against constitution v1.2.0 (post-implementation)**: still passing. Two amendments landed
after this plan was written and both were re-audited against the built code rather than assumed.
Amendment 1 adds the wall-clock rule to VI — audited above; no test of this feature violates it.
Amendment 2 raises the `AGENTS.md` cap from 60 to 100 and reframes it as the backstop to a content
rule; the template sits at 74 lines, and the content added here is the `/task` gesture, `--link`, and
the mirror's control-surface semantics, none of which an assistant could infer from the workspace and
none of which restates the README.

## Project Structure

### Documentation (this feature)

```text
specs/009-inline-task-capture/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── core-api.md      # endpaper.core public surface
│   ├── mirror-format.md # what a mirror is, and the state machine
│   ├── cli.md           # --link, propagation, exit codes, --json
│   └── tui.md           # the /task gesture and the open/save hooks
├── checklists/
│   └── requirements.md  # spec quality checklist (from /speckit-specify)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/endpaper/
├── core/
│   ├── mirrors.py          # NEW -- recognition, splice, conflict resolution, sync write
│   ├── tasks.py            # add_task gains links=; unchanged otherwise (008 adds the field)
│   ├── editor_commands.py  # /task registered; parse_line gains the dotted suffix split
│   ├── models.py           # Mirror, MirrorReport, MirrorResolution, ParsedCommand.suffix
│   ├── links.py            # (from 008) consumed, not modified
│   └── editing.py          # (from 008) consumed, not modified
├── cli/
│   └── main.py             # task add --link; done/undone propagate; --json additions
└── tui/
    ├── edit_screen.py      # /task dispatch, capture sequence, baseline, reconcile on open/save
    ├── preview_screen.py   # reconcile on open
    └── app.py              # toggle_task_and_track propagates to linked documents

tests/
├── contract/               # --link exit codes, --json schema, stream separation
├── integration/            # capture, propagation, reconcile on open and save
├── unit/                   # recognition, splice, conflict matrix, parse_line suffix
└── performance/            # reconcile-on-open budget and the no-read assertion
```

**Structure Decision**: The existing single-package layout is unchanged — one new core module and edits to
four existing files. `core/mirrors.py` is a new module rather than an extension of `tasks.py` or `links.py`
because it is a third concern: `links` owns the grammar, `tasks` owns `tasks.md`, and `mirrors` owns the
edge between them. Adding document I/O to `tasks.py` would invert the layering (`links` resolves *into*
`tasks.md` today), and adding completion state to `links.py` would compromise the pure-splice guarantee
008 built that module around. Full argument in [research.md](research.md#r1-where-the-reconciliation-logic-lives).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principle IV** — a sync write updates neither `created` nor `updated`, where IV says a write updates `updated`. | FR-029. Ticking a box in the tasks list is not an edit to the meeting note. Stamping it would move that document to the top of every recency-sorted list because of an action taken in a different collection, which is a visible, daily wrongness. The principle's purpose is that a real edit never leaves `updated` stale and never clobbers `created`; a sync write is not a real edit, and it preserves `created` untouched. | *Stamp `updated` on sync writes too* — rejected: it makes the meeting list reorder itself when the user completes an unrelated task, and it destroys the signal `updated` carries. *Do not write the document at all, and correct only what is displayed* — rejected: it leaves a stale checkbox on disk for every other reader and for the assistant, which defeats the reason the checkbox is there (spec Assumptions). |

No other gate fails. The single deviation is bounded to the sync path: a user save goes through
`save_buffer` and stamps exactly as it does today.
