# Implementation Plan: The Terminal Tab Names the Workspace

**Branch**: `016-terminal-tab-title` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-terminal-tab-title/spec.md`

## Summary

Set the terminal tab/window title to `choom — <workspace name>` once when the interactive interface
starts, and put the title back when it leaves.

The whole feature is two pieces with a hard line between them. `choom.core` gains **one pure function**,
`workspace_title(workspace: Workspace) -> str`, which derives the name, strips anything unprintable,
bounds the length, and returns the finished text. `choom.tui` gains **one context manager**,
`terminal_title(title)`, which wraps `ChoomApp.run()` and is the only code that knows what an escape
sequence is.

Wrapping `run()` — rather than hooking `on_mount`/`on_unmount`, and rather than binding any key — is
the load-bearing design choice. A `with` block's `finally` runs on every way out of the app that Python
can observe: a clean `ctrl+q`, a `ctrl+q` that went through the discard confirmation, an unhandled
exception, and a `KeyboardInterrupt`. It requires **no `ctrl+c` binding**, which constitution
Principle V forbids outright, and it makes FR-012 (a *cancelled* quit must not restore) true by
construction rather than by a check — a cancelled quit never leaves `run()`, so `finally` never fires.

Three findings from reading the installed `textual==8.2.8` source shaped the rest, and are recorded in
[research.md](./research.md):

1. Textual does not set the terminal title at any point, so there is nothing to collide with.
2. Textual's Windows driver already enables `ENABLE_VIRTUAL_TERMINAL_PROCESSING`, and on exit restores
   the console mode it *snapshotted at startup*. Because choom enables VT **before** `run()`, that
   snapshot includes choom's VT bit, so the console is still escape-capable when the restore is written
   after `run()` returns. Ordering is what makes the Windows path work.
3. Textual binds `ctrl+c` to its own `action_help_quit` ("Press ctrl+q to quit"), so **`ctrl+c` is not
   an exit path inside a running choom at all.** Where a `SIGINT` does terminate the process, the
   context manager already covers it. Nothing in this feature binds, rebinds, or inspects `ctrl+c`.

No new dependency: the Windows console-mode call is `ctypes` from the standard library. `colorama`,
floated as an option in issue #47, is rejected — see research R3.

## Technical Context

**Language/Version**: Python 3.11+ (repo targets 3.11, CI runs 3.11 and 3.13)

**Primary Dependencies**: `textual==8.2.8` (unchanged). **No new dependency.** The Windows console-mode
call uses `ctypes` from the standard library.

**Storage**: None. This feature reads `Workspace.root` (already in memory) and writes no file anywhere —
not in the workspace, not in per-user state. See FR-024.

**Testing**: `pytest` via `scripts/dev-tests.sh`. New coverage in `tests/unit/` (the core function and
the emitter), one extension to `tests/contract/test_no_ansi.py` (FR-016), and one
`tests/integration/` case for the launcher wiring.

**Target Platform**: macOS, Linux, Windows. Verified before release on Windows Terminal, iTerm2, macOS
Terminal, PuTTY, and inside tmux (`docs/REQUIREMENTS.md` §4.3).

**Project Type**: Single project — `src/choom/{core,cli,tui}` over `tests/{unit,contract,integration}`.

**Performance Goals**: Two short writes and one flush at startup, the same at exit. No measurable
change to either; nothing runs during the session (FR-009). SC-004 is satisfied by there being no
per-frame or per-keystroke work at all, so no performance test is added.

**Constraints**: Title bounded to 64 characters (FR-005). No admin rights, no network, no new
third-party dependency. Must be silent when stdout is not a TTY and on a console that cannot interpret
escape sequences.

**Scale/Scope**: Roughly 40 lines of new source across two files, plus the launcher wiring. One new
public `core` function.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution v2.1.0. **Result: all gates PASS. Complexity Tracking is empty because
no gate failed** — not because the table was skipped.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS.** Exactly one new core function: `workspace_title(workspace: Workspace) -> str` in `src/choom/core/workspace.py`, exported from `choom.core.__all__`. It performs **no reads and no writes** — it takes an in-memory `Workspace` and returns a string, so no file-access function is involved and there is no existing core function whose job an adapter could duplicate. It owns every decision worth testing: name derivation, the empty-root fallback, unprintable-character removal, and the 64-character bound. It imports nothing new (`str.isprintable`, `str.join`, slicing — all builtins) and nothing terminal-shaped; `workspace.py`'s existing imports are `os`, `tomllib`, `datetime`, `pathlib` and core siblings. Ruff's TID251 ban on `argparse`/`textual`/`rich` in core still holds, and `tests/unit/test_core_imports.py::test_core_does_not_reference_sys_stdout` still passes because the function never mentions a stream. The adapter side holds only what core may not: the escape sequences, the `isatty()` check, the `ctypes` console call, and the lifecycle. Precedent for user-facing text in core: `find_workspace` already raises `"no workspace found in this directory or any parent. Run 'choom init' to create one."` — core owns wording, adapters own devices. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS, as an explicit inherently-interactive carve-out**, argued in spec.md §"Interface parity": a sub-second CLI invocation does not own the tab, so labelling it is either a flicker or a permanently false claim on the user's shell tab, and escape bytes in a stream an assistant parses is exactly the corruption Principle II's non-TTY rule exists to prevent. Structurally enforced, not merely promised: the emitting module is `src/choom/tui/terminal_title.py` and its only importer is `_run_tui()`, which `main()` reaches solely when `argv` is empty — no argparse dispatch path imports it. `tests/contract/test_no_ansi.py` already asserts `"\x1b" not in` stdout/stderr across the subcommand surface and is extended here to the commands it does not yet reach. No `--json` key changes, no exit code is added or altered (FR-018), and nothing prompts or blocks. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. Any new setting has a sensible default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS.** No index, database, or cache — no state of any kind is stored, including the previous title, which the terminal's own title stack holds instead of choom (research R2). No new third-party dependency: `ctypes` is stdlib, and `colorama` is rejected in research R3. No new setting at all, so the sensible-default rule is satisfied by there being nothing to configure (FR-017); the behaviour is unconditional whenever stdout is a TTY. Directory layout untouched. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS, vacuously and deliberately.** No file is opened, parsed, written, moved, or deleted (FR-024). The one adversarial input in range — a workspace directory whose name contains control characters — is handled in core by dropping unprintable characters before composition (FR-004), which protects the *terminal* from the directory name; the directory itself is never touched or renamed. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; `ctrl+c` is never bound to anything, `ctrl+q` quits immediately unless something is dirty (in which case it MAY raise the existing confirmation); no non-`ctrl` modifier. | **PASS.** This feature adds **no key binding of any kind**, so the footer is unchanged and there is no hidden key. `ctrl+c` is emphatically not bound by this feature — restoration is process teardown via the `with` block's `finally`, never a handler (research R4). `ctrl+q` is untouched: `ChoomApp.action_quit` is not modified, the discard confirmation from issue #64 still fires only when something is dirty, and restoration adds no keystroke and no delay because it is two buffered writes and a flush after `run()` has already returned (FR-013). *Observation, not a change:* Textual's own framework defaults bind `ctrl+c` (`App.BINDINGS` → `action_help_quit`, and `Screen` → `screen.copy_text`). That predates this feature, is not introduced or relied upon by it, and is left exactly as it is; it is flagged in research R4 as a separate matter. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS.** `workspace_title` carries full type hints and a docstring stating what it returns and that it raises nothing. Coverage is chosen by what can plausibly break, not generated from the 15 acceptance scenarios: `unit/` for the composition rules (the truncation boundary, the unprintable-character strip, the rootless fallback, non-ASCII passthrough) and for the emitter's four branches (non-TTY silence, exact enter/exit bytes, restore-on-exception, swallowed write failure); `contract/` for the FR-016 prohibition; one `integration/` case for the launcher wiring. Nothing reads the clock, so no wall-clock dependency is possible. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS.** `GetConsoleMode`/`SetConsoleMode` on the process's own stdout handle need no elevation and no network. No path is constructed or written, so the 260-character budget is untouched. Spaces and non-ASCII in the workspace name survive verbatim (FR-006) and are covered by a unit test; the 64-character bound counts characters, not bytes, so a multi-byte name is not mangled mid-character. No per-user state is created — nothing is persisted anywhere (FR-019). |

**Post-Phase-1 re-check**: re-evaluated after the Phase 1 artifacts below were written. No gate changed
status. The design added no module beyond the two named in gate I, no setting, no dependency, and no
binding. Complexity Tracking remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/016-terminal-tab-title/
├── spec.md                    # Approved
├── plan.md                    # This file
├── research.md                # Phase 0
├── data-model.md              # Phase 1
├── quickstart.md              # Phase 1
├── contracts/
│   ├── core-api.md            # Phase 1 — workspace_title's contract
│   └── terminal.md            # Phase 1 — exact bytes and emission rules
├── checklists/
│   └── requirements.md
└── tasks.md                   # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── workspace.py           # MODIFIED: + workspace_title(), + 2 private helpers
│   └── __init__.py            # MODIFIED: export workspace_title in __all__
├── tui/
│   └── terminal_title.py      # NEW: terminal_title() context manager, Windows VT enable
└── cli/
    └── main.py                # MODIFIED: _run_tui() wraps ChoomApp.run() in the context manager

tests/
├── unit/
│   ├── test_workspace_title.py    # NEW: the core composition rules
│   └── test_terminal_title.py     # NEW: the emitter's branches, against a fake stream
├── contract/
│   └── test_no_ansi.py            # MODIFIED: extend to the remaining subcommands (FR-016)
└── integration/
    └── test_tui_launch.py         # MODIFIED: launcher wiring — title set around run(), restored after
```

**Structure Decision**: The existing single-project layout is kept unchanged. The feature adds exactly
one new source file, `src/choom/tui/terminal_title.py`, placed under `tui/` rather than `cli/` even
though `_run_tui()` calls it: putting the escape-sequence code inside the TUI package is what makes the
Principle II claim structural rather than a promise — no module reachable from argparse dispatch imports
it. The core change is a function added to the existing `core/workspace.py` rather than a new module,
because a workspace's own display label is workspace logic and a one-function module would be a name
without a domain (`core/titles.py` would also collide confusingly with `Document.title`).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*Empty. Every gate above is PASS, so there is no violation to justify. No entry here is a placeholder
or an "N/A" — the table has no rows because the design introduces no new dependency, no new setting, no
new source of truth, no new key binding, and no new state.*
