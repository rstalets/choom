# Implementation Plan: Read From Disk on View Load

**Branch**: `010-read-on-load` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-read-on-load/spec.md`

## Summary

Delete the TUI's session-lifetime workspace snapshot and read from disk instead. Every list load, every
return to a list, and every document open takes a fresh scoped read; an open list re-reads on a 2-second
timer and re-renders only when a rendered field actually changed; the one path that reads per keystroke —
filtering — hydrates on a thread worker when the command bar opens and holds that result for the bar session.

The work is confined to `src/choom/tui/`. Every read it needs already exists in `choom.core` (`scan_month`,
`scan_unfiled`, `load_tasks`, `get_task`, `_read_document`), so no core function is added, changed, or
removed. Net effect is a deletion: four cache dictionaries, two lazy-load guards, three refresh methods and
their six call sites — 38 sites in all — come out, and nothing replaces them but the reads that were always
available.

## Technical Context

**Language/Version**: Python 3.11+ (CI runs 3.11 and 3.13)

**Primary Dependencies**: `textual==8.2.8` (TUI only). No new dependency.

**Storage**: Markdown files in the workspace. No index, no database, no cache — that is the point of the
feature.

**Testing**: `pytest` with `pytest-asyncio`; Textual's `run_test()` pilot for TUI integration tests. Layers
per Principle VI: `integration/` for the user-visible paths, `unit/` for change detection, `performance/`
for the SC-003/SC-004 budgets. No `contract/` change — the CLI's AI-facing surface is untouched.

**Target Platform**: Windows, macOS, Linux terminals; no network, no admin rights.

**Project Type**: Single project — a CLI plus a TUI over a shared core library.

**Performance Goals**: List load under 200 ms and task list under 100 ms at 1,000 documents (SC-003);
command-bar open never delays the keypress, first filter term under 500 ms (SC-004); periodic refresh every
2 s with no render when nothing changed (FR-009, FR-010).

**Constraints**: The refresh tick runs on Textual's main thread, so its cost is frame budget, not just CPU.
Measured, `scan_month` is ~0.14 ms per document, crossing one 60 fps frame at roughly 100 documents in the
displayed month; the read stays on the main thread with the tick split into read and apply steps so a worker
can be retrofitted without rewriting tests (research R5). Tests must not depend on the wall clock
(Principle VI), which shapes how the timer is tested (research R9).

**Scale/Scope**: Hundreds to low thousands of files. Three source files change substantially
(`app.py`, `list_screen.py`, `edit_screen.py`); `preview_screen.py` itself needs no change — only its
caller does.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The initial evaluation and the post-design re-check agree; the Phase 1 design added no gate concern that the
initial pass did not anticipate, and the two Complexity Tracking entries below were identified at the
initial gate and confirmed unchanged after design.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — no core change at all. The feature calls existing core reads from `tui/`; what is being deleted was TUI-side caching that should never have been a second source of truth. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — the CLI already reads from disk on every invocation, so this closes a gap where the TUI diverged from its peer rather than opening one. No CLI code, `--json` schema, or exit code is touched. Periodic refresh is inherently interactive and has no CLI counterpart. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS, with two entries in Complexity Tracking** — the feature removes the only cache in the app. Two short-lived structures remain and are justified below: the command-bar filter snapshot and the last-render comparison key. Neither survives the interaction that creates it. No new dependency; the 2-second interval is a constant, not a setting. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS** — no parser or writer changes. Reading more often exercises the existing skip-and-warn path more often, which FR-007 turns into a benefit: the warning count now describes the workspace as it is rather than as it was at mount. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — no new binding, screen, or dialog. The refresh is invisible when nothing changed (FR-010) and never takes focus or interrupts typing (FR-013). |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS** — no new public `core` function. Tests are chosen by failure mode, not per acceptance scenario, and the timer is tested by invoking its callback directly plus one registration assertion; nothing sleeps or waits for a tick (research R9). |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no network, no new files written anywhere, no new paths constructed. Reading more often does not change path handling. |

## Project Structure

### Documentation (this feature)

```text
specs/010-read-on-load/
├── plan.md              # This file
├── research.md          # Phase 0 output — R1..R10 and resolved unknowns
├── data-model.md        # Phase 1 output — state removed, retained, introduced
├── quickstart.md        # Phase 1 output — how to validate the feature
├── contracts/
│   └── view-refresh.md  # Phase 1 output — the TUI read/render contract
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/choom/
├── core/                     # UNCHANGED — every read this feature needs already exists
│   ├── documents.py          #   scan_month, scan_unfiled, list_months, _read_document
│   └── tasks.py              #   load_tasks, get_task, set_task_state
└── tui/
    ├── app.py                # CHANGED — cache dicts, lazy-load guards, reload_tasks,
    │                         #   refresh_document, _refresh_document_in all deleted;
    │                         #   visible_* now scan; _track_created stops inserting
    ├── list_screen.py        # CHANGED — refresh timer, change detection, filter
    │                         #   hydration worker, preview opened from a fresh read
    ├── edit_screen.py        # CHANGED — four refresh call sites deleted
    ├── preview_screen.py     # UNCHANGED — already re-reads on resume
    └── command_bar.py        # UNCHANGED — existing messages suffice (research R6)

tests/
├── integration/              # US1/US2/US3 end-to-end paths; three existing tests updated (R10)
├── unit/                     # change-detection key
└── performance/              # SC-003 view load, SC-004 filter hydration
```

**Structure Decision**: Single project, existing layout, no new modules. The feature is a deletion plus
three behaviours added to `ListScreen`, so it lands in the files that already own those concerns rather than
introducing a "refresh" module that would only hold what `ListScreen` already does.

## Implementation Sequence

The spec's sequencing (US1 first, US2 and US3 following) maps to three independently shippable slices:

1. **US1 — read on load.** Make `visible_documents` / `visible_tasks` / `visible_warnings` scan; delete the
   four dictionaries, two lazy-load guards, `reload_tasks`, `refresh_document`, `_refresh_document_in` and
   the six call sites; read the document fresh when opening the preview from `_on_selected`; have
   `action_toggle_task` refresh the rows it just changed. Update the three tests in R10. **At this point the
   bug is fixed and the feature is releasable.**
2. **US2 — refresh timer.** Add `REFRESH_SECONDS = 2.0`, the interval registration, pause/resume on screen
   suspend/resume, the guards for command bar and active filter, and the change-detection key. Split the
   tick into a read step and an apply step (research R5) so that moving the read to a worker thread later
   does not require rewriting the tick's tests. Add the scan-cost performance test with its one-frame
   ceiling.
3. **US3 — filter hydration.** Add the thread worker started from `action_open_command_bar`, await it in
   `_on_filter_changed`, drop it in `_on_command_bar_closed`, delete the unread `app.filter_loading` flag.

Slice 1 is a prerequisite for 2 and 3; 2 and 3 are independent of each other.

## Phase 0: Research

Complete — see [research.md](./research.md). Ten decisions (R1–R10), all unknowns resolved, no
`NEEDS CLARIFICATION` markers remain. Notable outcomes:

- The scoped read stays scoped: a list load reads one month; only filtering reads the collection (R2).
- Change detection compares rendered fields, not mtimes or hashes (R4).
- Hydration starts from `action_open_command_bar`, not the `ModeChanged` handler the issue suggested —
  `ModeChanged` fires per keystroke (R6).
- The refresh interval is 2 s rather than the issue's ~10 s; the constraint is main-thread frame budget, not
  disk (R5).
- Three existing tests assert cache behaviour and change with it (R10).

## Phase 1: Design

Complete. Artifacts:

- [data-model.md](./data-model.md) — what state is deleted, what is retained, what is introduced and for how
  long.
- [contracts/view-refresh.md](./contracts/view-refresh.md) — the read/render contract: what triggers a read,
  what triggers a render, and what must never trigger either.
- [quickstart.md](./quickstart.md) — how to reproduce the bug, verify the fix, and run each test layer.

## Complexity Tracking

Principle III requires a documented justification for anything that holds workspace-derived state. Two
structures qualify. Both are scoped to a single interaction and cannot be observed stale by the user.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Filter hydration snapshot** — documents read when the command bar opens, held until it closes | Filtering fires on `Input.Changed`, i.e. per keystroke, and matches across every month. At 1,000 documents a full collection read is 144 ms, so reading per character makes the feature unusable | *Read on every keystroke*: 144 ms per character, measured. *Cancel and restart per keystroke*: worse — throws away work the next character needs, and breaks the type-`/task`-backspace-type-`/filter` case (FR-018). The snapshot's lifetime is one command-bar session; closing the bar drops it and the next open reads again, so the longest it can be stale is one filter interaction (FR-019) |
| **Last-render comparison key** — a tuple of rendered fields per row, kept from one render to the next | FR-010 requires that a refresh finding nothing new produces no visible change. Without a comparison the 2-second timer would rebuild the `ListView` every tick, resetting scroll and flickering | *Rebuild unconditionally*: visible redraw every 2 s and lost scroll position. *Compare mtimes or hash file contents*: a second notion of freshness that can disagree with what is rendered — the "wrong while looking authoritative" failure Principle III names and issue #27 rejected an index over. The key is derived from the read and never consulted in place of it: the scan still happens every tick, and the key only gates the redraw |

Neither structure is consulted to answer "what is in the workspace" — that question always goes to disk.
They gate work, not truth, which is the distinction Principle III draws.
