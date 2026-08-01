# Implementation Plan: Linked Task Syntax for AI Assistant

**Branch**: `012-assistant-task-syntax` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-assistant-task-syntax/spec.md`

## Summary

Issue #44, in two halves. The composed prompt learns to tell an assistant that it may emit a task by
writing `/task[.type] <description> [#tags]` on a line of its own, and the reply path learns to read those
lines instead of inserting them as text — capturing each one through the path a typed `/task` already
uses and substituting the mirror line it returns.

Almost nothing here is new behaviour. The grammar, the tag extraction, the id, the source link, the
mirror, and reconciliation in both directions all exist; this feature adds a classifier that decides which
lines of a reply are eligible, a loop that captures them, and one string in the prompt.

Two functions land in `core`, both in modules that already exist: `editor_commands.parse_reply_lines`
(pure, fence-aware) and `mirrors.capture_reply_tasks` (the walk and the writes). `edit_screen` calls one
function and replaces one span, as it does today. `compose_prompt` gains a required keyword-only
`task_capture` flag, and `EditTarget` gains the `captures_tasks` field that answers it — retiring an
overload of `stamps_frontmatter` that the existing `/task` guard already had to explain in a comment.

`011-ui-refinements` and the #69 reply fix are merged into this branch. The latter matters: each
assistant's stdout is already reduced to its final answer before anything inserts it, so this feature
reads that answer and no line of a transport format can reach the classifier.

## Technical Context

**Language/Version**: Python 3.11+ (CI runs 3.11 and 3.13)

**Primary Dependencies**: `textual==8.2.8` (TUI only). No new dependency, and none considered — the fence
rules are one variable and one comparison per line (research R2).

**Storage**: Markdown files in the workspace. This feature writes `tasks.md` through `capture_task`, once
per captured line, and writes nothing else. The reply's text lands in the editor buffer, unsaved, exactly
as today.

**Testing**: `pytest` with `pytest-asyncio`, run via `scripts/dev-tests.sh` per the repo's `CLAUDE.md`.
Textual's `run_test()` pilot for TUI integration. Layers per Principle VI and research R11: `unit/` for
the classifier and the capture walk, where every edge case in this feature lives; `integration/` for one
end-to-end path per story via the existing `stub_assistant` fixture; no `contract/` or `performance/`
change, because no CLI surface and no budget is added.

**Target Platform**: Windows, macOS, Linux terminals; no network, no admin rights.

**Project Type**: Single project — a CLI plus a TUI over a shared core library.

**Performance Goals**: None new. One atomic `tasks.md` write per captured line, on the UI thread after the
reply arrives (research R5, R7) — the same cost as typing `/task` that many times, against a reply the
assistant spent seconds producing.

**Constraints**: A capture failure may not cost any of the reply (FR-016, FR-017), which makes per-line
exception handling structural rather than defensive. A cancelled or superseded reply must create nothing
(FR-019), which fixes where the capture runs. Tests must not depend on the wall clock (Principle VI) —
none here does.

**Scale/Scope**: No new module. Two new `core` functions in existing files, two new dataclasses, one new
`ScanWarningReason` literal, and edits to `core/assistants.py`, `core/editor_commands.py`,
`core/mirrors.py`, `core/models.py`, `core/__init__.py`, and `tui/edit_screen.py`. Two new unit test
files, three new `stub_assistant` modes, and three integration tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The initial evaluation and the post-design re-check agree. Phase 1 changed one thing: the initial pass had
`edit_screen` splitting the reply and looping over `capture_task` itself, and gate I rejected it — the
walk is workspace logic and moved to `mirrors.capture_reply_tasks` (research R1).

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS.** Reads: `editor_commands.parse_line` (per line, via the new `parse_reply_lines`), `documents._read_document` (the source id, already called by the `/task` path). Writes: `mirrors.capture_task` per eligible line — unchanged — reached through the new `mirrors.capture_reply_tasks`, which is the only thing this feature adds to the write side. `assistants.compose_prompt` gains a flag, not a code path. The adapter assembles nothing core does: `edit_screen` calls one function, replaces one span, seeds the mirror baseline, and renders a status string. The classifier is pure and runs without a terminal (research R1). |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS.** Inherently non-CLI: the whole feature hangs off `/ai`, which is a TUI editor command with no CLI counterpart (006 settled that), and an assistant using the CLI has `choom task add --link` already. No `--json` schema changes and no exit code is added or renamed. One `ScanWarningReason` literal is added, which is additive under this gate's own rule. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS.** No new state of any kind: the classifier is pure, the capture writes through the existing path, and nothing is remembered between replies. No new dependency, no markdown parser (R2). No new setting — the instruction is unconditional for document targets, because a setting that could be a sensible default must be one, and the assistant is told the lines are optional. Nothing touches the directory tree. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS**, and this is the gate the feature is most exposed to. The classifier never raises and never drops a line — every input line appears in the output, either as itself or as the mirror that replaced it (FR-017). A capture failure catches exactly `UsageError` and `WorkspaceError`, leaves that line as the assistant wrote it, and continues (R10). Tags cannot vanish: they are lifted by the same `parse_tags` the editor uses, and a line whose description is only tags fails validation loudly rather than silently losing them. The substituted mirror is an ordinary CommonMark checklist item. No frontmatter is written by this feature — the document is saved before the request, as today. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **PASS.** No new binding, no new screen, no new confirmation, no navigation — the editor keeps focus and nothing moves (FR-020), which is what 009 established for a typed capture and 006 for a reply. The one visible addition is a status line reporting the count, and it is rendered *without* the `⚠` prefix precisely so the warning marker keeps meaning something (R8). |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS.** Both new core functions carry type hints and docstrings stating what they raise — `parse_reply_lines` raises nothing by contract, `capture_reply_tasks` reports failures rather than raising. Tests are chosen by failure mode (R11): the fence and eligibility rules get unit tests where their edge cases live, the capture walk gets unit tests for ordering and partial failure, and each story gets one integration path — not one test per acceptance scenario. Nothing sleeps or reads the wall clock; `capture_task` already takes an injectable `now`. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS.** No network, no admin rights, no new state anywhere. CRLF input is normalised by the existing reply path and covered by a classifier unit test. The mirror line's relative path is produced by `mirrors.mirror_line`, unchanged, so path length and non-ASCII behave exactly as they do for a typed capture. |

## Project Structure

### Documentation (this feature)

```text
specs/012-assistant-task-syntax/
├── plan.md              # This file
├── research.md          # Phase 0 output — R1..R12
├── data-model.md        # Phase 1 output — the two new shapes and what a capture touches
├── quickstart.md        # Phase 1 output — how to validate each story
├── contracts/
│   └── reply-capture.md # Phase 1 output — the prompt clause, the classifier, the capture walk
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── editor_commands.py    # CHANGED — parse_reply_lines(text) -> tuple[ReplyLine, ...]
│   ├── mirrors.py            # CHANGED — capture_reply_tasks(...) -> ReplyCapture
│   ├── assistants.py         # CHANGED — _TASK_SYNTAX constant; compose_prompt(task_capture=...)
│   ├── models.py             # CHANGED — ReplyLine, ReplyCapture, "reply_capture_failed" reason
│   ├── __init__.py           # CHANGED — re-export the two new functions and shapes
│   └── tasks.py              # UNCHANGED — add_task already does everything a capture needs
└── tui/
    └── edit_screen.py        # CHANGED — EditTarget.captures_tasks; capture in _finish_request;
                              #           neutral status note; mirror baseline seeding

tests/
├── unit/
│   ├── test_reply_lines.py           # NEW — fences, indentation, eligibility
│   ├── test_capture_reply_tasks.py   # NEW — substitution, ordering, partial failure
│   └── test_compose_prompt.py        # CHANGED — instruction present/absent/identical
├── integration/
│   └── test_ai_command_tui.py        # CHANGED — one path per story (US1, US3, US5)
└── conftest.py                       # CHANGED — three new stub_assistant modes

README.md                             # CHANGED — the /ai bullet and the inline capture bullet
```

**Structure Decision**: Single project, existing layout, no new module. Both new functions go beside the
function they generalise — `parse_reply_lines` beside `parse_line`, `capture_reply_tasks` beside
`capture_task` — which is what keeps the editor and the reply path from ever disagreeing about what a task
line is (research R1).

## Implementation Sequence

The spec's story order is close to the build order, with one inversion: the classifier has to exist before
anything can be captured, and it is also the whole of US3.

1. **Shapes and the classifier.** `ReplyLine`, `parse_reply_lines`, and its unit tests. This is US3's
   entire behaviour — what is *not* eligible — and every later step depends on it.
2. **The capture walk.** `ReplyCapture`, the `"reply_capture_failed"` reason, `capture_reply_tasks`, and
   its unit tests, including the partial-failure cases that are US5.
3. **The prompt.** `_TASK_SYNTAX`, `compose_prompt`'s `task_capture` parameter, the three existing call
   sites, and the identical-across-profiles test. This is US2, and it is independent of steps 1–2.
4. **The wiring.** `EditTarget.captures_tasks` (and moving the `_capture_task` guard onto it),
   `_finish_request` calling the walk, the mirror baseline seeding, and the neutral status note. This is
   US1 end to end, and it needs steps 1–3.
5. **Integration paths and stub modes.** One test per story through the real TUI.
6. **Documentation.** The two README bullets.

Steps 1 and 3 are independent of each other and may be built in either order. Step 4 is the only step that
touches the adapter.

## Phase 0: Research

Complete — see [research.md](./research.md). Twelve decisions (R1–R12), no `NEEDS CLARIFICATION` markers.
Notable outcomes:

- The walk lives in `core`, in two modules that already exist; no new module (R1).
- Eligibility is the editor's existing rule plus fence tracking, with `parse_line` still the only place
  the grammar is defined (R2).
- `compose_prompt`'s new flag is required rather than defaulted, because either default hides the
  mistake that flag exists to prevent (R3).
- The instruction goes *after* "Do not edit any file" and reconciles itself with it (R4).
- The capture runs on the UI thread after the superseded check — a reply the user never sees must create
  nothing (R5).
- One `editor.replace()` still does the insert, so undo stays one step and the created tasks survive it
  (R6).
- A successful capture is reported without the `⚠` prefix, so the warning marker keeps its meaning (R8).
- Seeding the mirror baseline for each new task is one line and prevents the feature's most likely silent
  bug (R9).
- `AGENTS.md` is deliberately not changed; the prompt is self-contained (R12).

## Phase 1: Design

Complete. Artifacts:

- [data-model.md](./data-model.md) — `ReplyLine` and `ReplyCapture`, what a capture writes, and what it
  must never touch.
- [contracts/reply-capture.md](./contracts/reply-capture.md) — the prompt clause, the eligibility rules
  the classifier guarantees, the capture walk's ordering and failure semantics, and the TUI behaviour.
- [quickstart.md](./quickstart.md) — how to validate each story by hand and which tests cover it.

## Complexity Tracking

No gate failed, and nothing here requires a justification under Principle III. The feature adds no state,
no dependency, no module, and no setting.

Two judgement calls are worth recording, neither a violation:

- **`EditTarget` gains a field rather than reusing `stamps_frontmatter`.** One more boolean on a dataclass,
  against an overload that the existing `/task` guard already needed a comment to explain and that a second
  behaviour would now depend on. Naming it is cheaper than the comment.
- **`compose_prompt`'s flag is required, which touches three test call sites.** The alternative is a
  default, and both defaults are wrong in a way no existing test would catch (R3). Three mechanical edits
  buy a decision that is visible wherever a prompt is composed.
