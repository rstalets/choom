# Implementation Plan: Tasks

**Branch**: `003-tasks` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-tasks/spec.md`

## Summary

Add standalone tasks: markdown checkbox lines in a single `tasks.md`, created and completed from
both front doors, and parsed in a way that survives the user editing the file by hand.

The new module is `endpaper.core.tasks`, and it is deliberately split in two. A **pure layer**
(`parse_tasks(text) -> ParsedTasks`, `render_task_line(...) -> str`) turns a string into records and
back with no filesystem in sight; a **three-function I/O layer** (`load_tasks`, `add_task`,
`set_task_state`) reads, repairs, and writes. Every classification and preservation rule in the spec
is therefore a string-in, data-out unit test.

Three properties drive the design, and all three come from the same fact — this is the first file
endpaper shares with the user's own editor:

1. **Writes are atomic and line-preserving.** Read with newline translation off, rebuild the line
   list, write a temporary file beside the original, `os.replace` over it. Untouched lines are
   re-joined byte-for-byte, `\r\n` and all.
2. **Damage is classified, not assumed.** An unterminated comment is skipped and warned. A bad
   `created` value degrades that one field and keeps the task. The difference is whether the parser
   can still tell where the user's words end.
3. **Writers locate by identifier, never by cached line number**, because the user may have
   rearranged the file since the list was drawn.

The TUI gains a `TaskListScreen` reached by `/tasks`, with `space` to toggle and `a` to show
completed. **No new dependency**, no new state, no configuration.

## Technical Context

**Language/Version**: Python 3.11+ (unchanged; `requires-python = ">=3.11"`)

**Primary Dependencies**: None added. `textual>=8.2` and `PyYAML>=6.0` are already present; this
feature touches neither YAML nor markdown rendering. New code uses `re`, `secrets`, `os`, `pathlib`.

**Storage**: One markdown file per workspace, `tasks.md`. No database, no index, no cache.

**Testing**: `pytest` + `pytest-asyncio`, TUI driven headless via `App.run_test()` / `Pilot`, as in
feature 001. The pure parse layer needs neither.

**Target Platform**: Windows, macOS, Linux. Windows is first-class — and materially so here, because
`tasks.md` is the first file endpaper rewrites, which makes CRLF preservation a correctness
requirement rather than a nicety.

**Project Type**: Single project — installable CLI + TUI application, `src/` layout.

**Performance Goals**: 1,000-task file lists in under 1s (SC-007); TUI toggle reflected on disk
within 1s (SC-002). Both have roughly two orders of magnitude of headroom.

**Constraints**: No network. No external binaries. Never opens an editor, prompts, or writes ANSI to
a non-TTY. A write must never truncate or reorder the user's file.

**Scale/Scope**: Hundreds to low thousands of tasks in one file; one file per workspace.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Mark each gate PASS / FAIL / N/A with a one-line justification. Any FAIL must appear in
Complexity Tracking below with a rejected simpler alternative, or the plan does not proceed.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — all behaviour is in `core/tasks.py`; the parse half is testable without even a filesystem ([research.md R4](./research.md#r4-parsing-is-a-pure-text-to-data-function)). The existing import-direction test covers the new module automatically. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — `add_task` and `set_task_state` are the single write paths for both front doors; `space` in the TUI and `task done` on the CLI call the same function, and a test diffs their output (FR-026). `task list --json` fixes seven keys; exit codes reuse the existing `EndpaperError` mapping. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — `tasks.md` is the only state; every read is a fresh parse, and no parse is cached across a write ([R7](./research.md#r7-locate-by-identifier-at-write-time-never-by-cached-line-number)). Zero new dependencies. No new flags beyond those the spec names. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — this is the feature's centre of gravity. Classification table in [R2](./research.md#r2-the-metadata-comment-and-what-malformed-means); atomic write strategy in [R6](./research.md#r6-writing-without-losing-anything). A round-trip test asserts that parsing and re-rendering an untouched file is byte-identical, including mixed line endings. `created` is never rewritten and never invented ([R8](./research.md#r8-a-hand-written-task-has-no-creation-date-and-endpaper-does-not-invent-one)). Task lines carry no `updated` field, by design — the checkbox is the state. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS, with the deviation stated** — tasks get a second list screen rather than sharing the meetings screen. Justified in [R9](./research.md#r9-the-task-surface-in-the-tui): same list surface, preview pane omitted because a one-line task has no preview state; transitions stay one keystroke through the existing command bar. `space` and `a` are unbound by `ListView`, so nothing is rebound and no priority binding is needed. No confirmations — a toggle is reversible with the same key. See Complexity Tracking. |
| VI | Type hints and docstrings on new public `core` functions; every acceptance criterion maps to a test; public API changes recorded in the changelog. | **PASS** — `mypy --strict` already covers `src`; [contracts/core-api.md](./contracts/core-api.md) is the signature source of truth; the task line format, the four new commands, and the JSON schema go into CHANGELOG.md as part of 0.0.1, which has not shipped. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no install, network, or path-length change; `tasks.md` sits at the workspace root, one segment long. CRLF and non-ASCII round-trip tests are part of the acceptance set. No per-user state is introduced. |

**Post-Phase-1 re-check**: still PASS on all seven. Phase 1 added no dependency, no persistent state,
and no binding beyond the two named at gate time. Gate V's deviation was identified before research
and is unchanged after design. One spec refinement surfaced during design — appending to a file with
no final newline must add the terminator — and is recorded under Follow-ups rather than left
implicit.

## Project Structure

### Documentation (this feature)

```text
specs/003-tasks/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — 11 decisions
├── data-model.md        # Phase 1 output — entities, line grammar, classification, sorting
├── quickstart.md        # Phase 1 output — runnable validation guide
├── contracts/           # Phase 1 output
│   ├── cli.md           #   task command surface, exit codes, JSON schema
│   ├── core-api.md      #   endpaper.core.tasks public API
│   └── tui.md           #   task screen, bindings, command-bar grammar additions
├── checklists/
│   └── requirements.md  # spec quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

Files this feature **adds** are marked `+`; files it **edits** are marked `~`. Everything else is
existing structure shown for context.

```text
src/endpaper/
├── core/
│   ├── __init__.py          ~ re-export Task, TaskFilter, load_tasks, add_task, set_task_state
│   ├── models.py            ~ + Task, TaskFilter, ParsedTasks; + Workspace.tasks_file property;
│   │                          ~ ScanWarningReason gains the task reasons
│   ├── text.py              ~ + new_task_id(taken: Container[str])
│   ├── tasks.py             + the feature: parse/render (pure) + load/add/set (I/O)
│   └── templates/
│       └── AGENTS.md.tmpl   ~ task line format + task commands; stays <= 60 lines
├── cli/
│   ├── main.py              ~ + `task` subparser: add, list, done, undone
│   └── output.py            ~ + print_tasks_table, print_tasks_json
└── tui/
    ├── app.py               ~ + task state, load_tasks on mount, toggle_task_and_track
    ├── task_list_screen.py  + list of tasks, space toggle, `a` show-completed
    ├── command_bar.py       ~ VERBS += {task, tasks}; + task create / navigate messages
    ├── list_screen.py       ~ route `/tasks` to the task screen
    └── status_bar.py        ~ + TASK_LIST_HELP

tests/
├── unit/
│   ├── test_task_parse.py        + line grammar, classification table, round-trip byte equality
│   ├── test_task_render.py       + rendered line shape, tag/type omission when empty
│   └── test_task_id.py           + t_ format, in-file collision retry
├── integration/
│   ├── test_task_cli.py          + add/list/done/undone, exit codes, empty and missing file
│   ├── test_task_tui.py          + Pilot: space toggles, `a` shows completed, list refreshes
│   ├── test_task_parity.py       + CLI toggle and TUI toggle produce identical files (FR-026)
│   └── test_task_handedit.py     + bare-line backfill, broken comment, CRLF, no trailing newline
├── contract/
│   ├── test_json_schema.py       ~ + the seven task keys
│   └── test_exit_codes.py        ~ + not-found, duplicate id, read-only file
└── performance/
    └── test_task_scan.py         + 1,000 tasks list in < 1s (SC-007)
```

**Structure Decision**: Unchanged from feature 001 — single project, `src/` layout, three packages
with `core` importing neither adapter. This feature adds exactly one core module, one TUI screen, and
one CLI subparser group; the shape it slots into already exists and is enforced by the
import-direction test described in gate I.

`core/tasks.py` is one module rather than a `tasks/` package: the pure and I/O halves are roughly 120
and 60 lines, and splitting them across files would hide the boundary that matters more than it would
enforce it.

## Implementation Sequencing

Ordered so each stage is independently verifiable, matching the spec's user story priorities.

| Stage | Delivers | Verified by |
|---|---|---|
| 1. Pure parse/render | `Task`, `ParsedTasks`, `parse_tasks`, `render_task_line`, `new_task_id` | Unit tests: grammar table, R2 classification table, byte-identical round-trip, id collision retry |
| 2. File layer | `load_tasks`, `add_task`, atomic write helper, `Workspace.tasks_file` | Append to a missing, empty, and prose-bearing file; CRLF and no-final-newline preservation |
| 3. Create (US1) | `endpaper task add`, `/task.<type>` in the command bar | US1 scenarios 1–4; empty-description usage error |
| 4. Read + toggle (US2, CLI) | `set_task_state`, `task list` + `--json` + filters, `task done` / `undone` | US2 scenarios 1, 2, 5, 6; contract test on the seven keys |
| 5. TUI (US2) | `TaskListScreen`, `space`, `a`, `/tasks` routing, footer text | US2 scenarios 3, 4; headless `Pilot` tests; FR-026 parity diff |
| 6. Hand-editing (US3) | Backfill write-back, read-only degradation, warning routing | US3 scenarios 1–5; SC-003 operation-sequence property test |
| 7. AI contract + hardening (US4) | `AGENTS.md` task section, changelog entry, performance fixture | US4 scenarios 1–4; SC-005, SC-007; AGENTS.md line-count test |

Stage 4 is the MVP boundary: after it, a user — or an assistant — can capture tasks and complete
them from the command line, which is the whole of REQUIREMENTS.md §3.3 minus the interactive surface.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No gate failed. One deviation is recorded here because it departs from the literal text of a
principle and should not be discovered later in review.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A second list screen (`TaskListScreen`), where Principle V says "the TUI is one screen: a filterable list and a preview pane" | Tasks are a second content type with no preview state — a task is one line, and REQUIREMENTS.md §3.3 gives it its own verbs (`/tasks`), its own default filter (open only), and its own binding (`space`). The screen keeps the principle's substance: one list, one-keystroke transitions, every binding in the footer, navigation through the command bar that already exists. | Branching inside `ListScreen` on row type was worked through on paper first: every method grows a conditional, the preview pane has to appear and disappear, and the two row types share no fields. It preserves the letter of "one screen" while making the code harder to read, which inverts Principle VI. |

## Follow-ups outside this plan

- **FR-037 needs one clause of refinement.** "Presence or absence of a final newline MUST be
  preserved by every write" cannot hold for `add_task` on a file whose last line has no terminator —
  the new task would be concatenated onto the end of the user's last line. The plan implements:
  toggles and backfill preserve exactly; append adds the terminator the previously-final line lacked.
  Worth amending the spec sentence to say so.
- **`--all` collides across §3.3 and §3.4.** REQUIREMENTS.md uses it for "include completed" here and
  for "every workspace" in the workspace feature. This plan claims it for the §3.3 meaning on
  `task list` ([R10](./research.md#r10---all-means-include-completed-and-nothing-else)); the
  cross-workspace feature will need a different flag on this command, or a scope option that is not
  `--all`.
- **AGENTS.md currently says `tasks.md` is "reserved for a future feature, currently empty".** This
  feature makes that line wrong; stage 7 replaces it. The layout block in the same template must also
  gain the `YYYY/MM/` partitions (see below), so stage 7 rewrites two sections against a ~60-line
  budget that has 3 lines of slack today. If it does not fit, the meetings frontmatter example is
  the block to shorten — an assistant can infer the schema from any file it opens.
- **REQUIREMENTS.md §3.3 lists `--all` on `task list` alongside `--tag` and `--type`** without saying
  whether completed tasks are filterable by tag. This plan applies the filters conjunctively to
  whatever set `--all` selected, which is the reading with no surprises.

## Also on this branch: the `YYYY/MM/` layout amendment

This branch carries a second, independent change that ships with the same feature: dated files are
partitioned by `YYYY/MM/` under their collection root (REQUIREMENTS.md §4.6, and feature 001's
[Amendments](../001-meeting-notes/spec.md#amendments)).

```
meetings/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
notes/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
notes/daily/YYYY/MM/YYYY-MM-DD.md
tasks.md                                      <- unchanged
```

**Tasks are unaffected.** `tasks.md` is a single file at the workspace root, with no date in its path
and nothing to partition. Every requirement, contract, and test in this feature stands unchanged, and
`Workspace.tasks_file` stays `root / "tasks.md"`.

**Two places the two changes touch each other**, both in stage 7:

1. `AGENTS.md.tmpl` documents the folder layout to assistants. It must gain the partitions *and* the
   task section in the same rewrite — see the follow-up above.
2. The layout amendment is spec-only: `create_meeting` and `scan_meetings` still write and read flat.
   If both ship as one feature, that code change belongs in this feature's task list, ahead of the
   AGENTS.md rewrite that describes it. `/speckit-tasks` should pick it up as its own stage rather
   than folding it into the task work, because it touches no task code and carries its own tests
   (recursive scan, on-demand partition creation, a meeting left directly under `meetings/` still
   listing).

