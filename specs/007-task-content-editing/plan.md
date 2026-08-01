# Implementation Plan: Task Content Editing

**Branch**: `007-task-content-editing` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-task-content-editing/spec.md`

## Summary

Give every task an optional markdown body, stored as indented continuation lines directly beneath
its checkbox line in `tasks.md`. The body renders in the TUI preview pane when the task is
highlighted and is edited with `e`; the CLI gains a read-only `task show` and reports bodies in
`task list --json`.

The whole feature rests on one core capability: locating a task's body span in the parsed file, and
splicing a replacement in without touching any other byte. `parse_tasks` already walks every line
and already returns the file's lines verbatim, so the span is computed in the pass that is already
happening. Writes reuse the atomic-write and locate-by-id machinery that `set_task_state`
established. The TUI reuses `EditScreen` unchanged in behaviour, opened on a buffer instead of a
file; the CLI adds one subcommand and one JSON key.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Textual (TUI); standard library elsewhere. No new dependency.

**Storage**: `tasks.md` in the workspace root — plain markdown, the only source of truth. No index,
no sidecar file, no cache.

**Testing**: pytest, with the existing `tmp_workspace` / `cli` / `write_tasks` fixtures and the
shared TUI pilot helpers in `tests/helpers.py`.

**Target Platform**: Windows, macOS, Linux terminals. Windows is first-class.

**Project Type**: Single Python package with two peer adapters (CLI and TUI) over a shared core.

**Performance Goals**: Highlighting a task updates the preview from memory — no file read per
keystroke. Cursor movement through 500 tasks stays as responsive as it is today (SC-005).

**Constraints**: Offline; no admin rights; no new external binary. `tasks.md` stays valid
CommonMark (SC-008). CRLF and missing-trailing-newline states are preserved (FR-021). A no-op save
must not rewrite the file (SC-003).

**Scale/Scope**: Hundreds to low thousands of tasks in one file; bodies of a few lines typically,
several hundred lines at the extreme (FR-010, edge case "very long details").

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated before Phase 0 and re-checked after Phase 1 design — unchanged, no gate fails.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — body span detection, dedent/indent, `get_task`, and `set_task_body` all live in `core/tasks.py` and are callable without a TTY. The TUI adds screen wiring only; the CLI adds argument parsing and printing only. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — reading a body is available in both (`task show` / preview pane). Editing one is inherently interactive, so it stays TUI-only and the CLI gains no editor. `body` is an added key, which the constitution classifies as a minor change; no key is renamed or removed. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **PASS** — the body lives in the file that already holds the task. No new dependency, no new setting. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — body scanning cannot raise; every line stays in `ParsedTasks.lines`; a write replaces only the target span. Tasks carry no `updated` field, so that clause is N/A for this file; `created` lives on the task line, which a body write never touches. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS** — `e` already exists and is already in the footer; this feature makes it work on tasks rather than adding a key. The discard confirmation is the existing one, which already fires only when the buffer is dirty. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; public API changes recorded in the changelog. | **PASS** — see `research.md` R6 for the layer-by-layer coverage choice. The `--json` key and the task line format extension are changelog entries (FR-030). |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no new paths are created, so the path budget is unaffected. CRLF preservation and non-ASCII bodies are covered by tests. |

## Project Structure

### Documentation (this feature)

```text
specs/007-task-content-editing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── task-file-format.md
│   ├── cli.md
│   └── tui.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/endpaper/
├── core/
│   ├── models.py        # Task gains `body`
│   └── tasks.py         # body span scan, dedent/indent, get_task, set_task_body
├── cli/
│   ├── main.py          # `task show` subcommand + dispatch
│   └── output.py        # `body` in the JSON listing; task show renderers
└── tui/
    ├── app.py           # reload tasks after a body save
    ├── edit_screen.py   # open the editor on a buffer, not only a file
    ├── list_screen.py   # task preview rendering; `e` on a task row
    └── rendering.py     # render_task_markdown for the preview pane

tests/
├── contract/            # task show exit codes, streams, JSON schema
├── integration/         # one end-to-end path per user story
└── unit/                # span scan, dedent/indent, splice writer
```

**Structure Decision**: No new modules and no new package. Every change lands in a file that
already exists, which is the strongest available signal that the feature fits the current shape:
core owns the file format, the two adapters stay thin, and there is no third place for task
behaviour to live.

## Complexity Tracking

No constitution gate fails, so there is nothing to justify here.
