---

description: "Task list for 007 Task Content Editing"
---

# Tasks: Task Content Editing

**Input**: Design documents from `/specs/007-task-content-editing/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. The constitution's Development Workflow requires behaviour changes to land with
the tests that cover them, and coverage here is risk-based per [research.md](./research.md) R6 — the
file format carries the data-loss risk, so `unit/` is where the depth goes.

**Organization**: Grouped by user story so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 — maps to the user stories in spec.md
- Exact file paths are in every task

## Path Conventions

Single project: `src/endpaper/` and `tests/` at the repository root. No new module is created —
every task edits a file that already exists.

---

## Phase 1: Setup

**Purpose**: Confirm the starting point. No dependency or tooling change is needed for this feature.

- [ ] T001 Run `uv run pytest` and `uv run ruff check . && uv run mypy src` from the repository root and confirm a green baseline before changing anything

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The parse-side model that all three stories read from. Nothing else can start until a
task knows its own body.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T002 Add `body: str = ""` to `Task` and a frozen `TaskBodySpan` dataclass (`start: int`, `end: int`, `indent: str`) to `src/endpaper/core/models.py`, and add `bodies: tuple[TaskBodySpan, ...] = ()` to `ParsedTasks` per [data-model.md](./data-model.md)
- [ ] T003 Implement `_body_span(lines, task_index) -> TaskBodySpan` in `src/endpaper/core/tasks.py`: the span starts after the checkbox line and ends after the last indented non-blank line before a terminator, where a terminator is a checkbox line at any indent or a non-blank line with no leading whitespace; trailing blank lines are excluded, interior ones kept (research R1)
- [ ] T004 Implement `_common_indent(lines) -> str` and the dedent/re-indent helpers in `src/endpaper/core/tasks.py`: strip the longest common leading-whitespace prefix across non-blank span lines, drop leading and trailing blank lines, and fall back to two spaces when no prefix can be observed (research R2)
- [ ] T005 Populate `Task.body` and `ParsedTasks.bodies` in `parse_tasks` in `src/endpaper/core/tasks.py`, keeping the existing guarantees: never raises, and `"".join(result.lines) == text` for any input
- [ ] T006 [P] Unit-test span boundaries in `tests/unit/test_task_body_parse.py`: no body; simple body; blank line inside a body; trailing blanks excluded; a nested `- [ ]` line ends the body and stays its own task; a non-indented line ends the body; tab-indented body; body on the last task at EOF; body under a malformed-comment line is not re-attached to the preceding task
- [ ] T007 [P] Unit-test dedent and indent reconstruction in `tests/unit/test_task_body_parse.py`: four-space and tab prefixes are stripped and remembered; relative indentation of nested bullets survives; mixed tabs and spaces degrade to no dedent without losing content
- [ ] T008 [P] Extend `tests/unit/test_task_parse.py` and `tests/integration/test_no_migration.py` to prove a pre-feature `tasks.md` parses identically, lists every task it did before, and is not rewritten on first read (FR-006, SC-006)

**Checkpoint**: Every task knows its own body. User stories can now proceed.

---

## Phase 3: User Story 1 - Read a task's details while scanning the list (Priority: P1) 🎯 MVP

**Goal**: Highlighting a task renders its body in the preview pane.

**Independent Test**: Hand-edit `tasks.md` to add indented text under one task, open the TUI, move
the cursor onto that task and confirm the text renders — then move to a task without a body and
confirm the pane does not keep the previous content.

### Tests for User Story 1

- [ ] T009 [P] [US1] Unit-test `render_task_markdown` in `tests/unit/test_rendering.py`: heading is the task text; the metadata line carries creation date, type, and tags with absent fields omitted; a completed task is marked; a task with no body renders heading and metadata only
- [ ] T010 [P] [US1] Integration test in `tests/integration/test_task_body_tui.py`: a hand-written body renders in the preview pane when its task is highlighted, and moving to a body-less task clears it (spec US1 scenarios 1-2); a completed task's body renders the same way in the Done category (scenario 3)

### Implementation for User Story 1

- [ ] T011 [US1] Add `render_task_markdown(task: Task) -> str` to `src/endpaper/tui/rendering.py` per [contracts/tui.md](./contracts/tui.md) — heading, italic metadata line, then the body; reads only from the `Task`, never from disk
- [ ] T012 [US1] Handle `TaskRow` in `ListScreen._update_preview` in `src/endpaper/tui/list_screen.py`, rendering via `render_task_markdown` and clearing the pane for the empty-state row

**Checkpoint**: Bodies written by hand or by an assistant are visible in the TUI. Shippable alone.

---

## Phase 4: User Story 2 - Add and update a task's details (Priority: P2)

**Goal**: `e` on a highlighted task opens the editor on its body; saving writes it back without
disturbing anything else in the file.

**Independent Test**: Highlight a task, press `e`, type a line, save, and confirm the line is in
`tasks.md` under that task and in the preview pane — with the task's own line unchanged.

### Tests for User Story 2

- [ ] T013 [P] [US2] Unit-test the writer in `tests/unit/test_task_body_write.py`: adds a body where none existed; replaces an existing one; an empty body removes the span leaving a lone task line; the task's own line and every line outside the span are byte-identical; a body identical to the one on disk performs no write at all (SC-003)
- [ ] T014 [P] [US2] Unit-test writer failure and preservation in `tests/unit/test_task_body_write.py`: CRLF files stay CRLF; a file with no trailing newline keeps that state; non-ASCII bodies round-trip; an unknown id raises `NotFoundError`; a duplicated id raises `UsageError` naming both line numbers; an unwritable file raises `WorkspaceError`
- [ ] T015 [P] [US2] Integration test in `tests/integration/test_task_body_tui.py`: `e` on a body-less task opens an empty buffer; `e` on a task with a body opens exactly that body and nothing else; save lands in the file and the pane with the same task still highlighted; discard leaves the file unchanged (spec US2 scenarios 1-6)
- [ ] T016 [P] [US2] Integration test in `tests/integration/test_task_body_tui.py`: toggling a task done with `space` preserves its body (spec US2 scenario 7, FR-022)
- [ ] T017 [P] [US2] Extend `tests/integration/test_save_failure.py` with a task-body save whose target task has vanished from the file, asserting the status bar names the problem and the buffer keeps the user's text (FR-023)

### Implementation for User Story 2

- [ ] T018 [US2] Implement `set_task_body(workspace, task_id, body) -> Task` in `src/endpaper/core/tasks.py` per [data-model.md](./data-model.md): re-read and re-parse, locate by id, short-circuit when the body is unchanged, splice the span with the observed indent, write atomically through the existing `_atomic_write`, and preserve the file's line-ending and trailing-newline state
- [ ] T019 [US2] Write a blank line between the checkbox line and the first body line, and drop leading blank lines on read so the round-trip is stable (research R4, needed for SC-008)
- [ ] T020 [US2] Generalise `EditScreen` in `src/endpaper/tui/edit_screen.py` to an edit target carrying buffer text, a `save(text) -> SaveResult` callable, a display path, an `/ai` line offset, and a `stamps_frontmatter` flag; keep the file-backed path behaving exactly as it does today (research R5)
- [ ] T021 [US2] Add `open_task_editor(app, task)` in `src/endpaper/tui/edit_screen.py`, saving through `set_task_body` and suppressing the frontmatter-stamp warning that does not apply to tasks
- [ ] T022 [US2] Make `ListScreen.action_edit` in `src/endpaper/tui/list_screen.py` open the task editor for a `TaskRow` instead of returning early, and do nothing on the empty-state row
- [ ] T023 [US2] Reload the task list after a body save in `src/endpaper/tui/app.py` so the existing resume path re-renders and re-selects by id (research R7)

**Checkpoint**: The full capture loop works in the TUI.

---

## Phase 5: User Story 3 - An assistant reads task details through the CLI (Priority: P3)

**Goal**: The CLI can print any task's body and reports bodies in its machine-readable listing.

**Independent Test**: Add a body, then confirm `endpaper task show <id>` prints it, `--json` carries
it, and a missing id exits 1 on stderr.

### Tests for User Story 3

- [ ] T024 [P] [US3] Extend `tests/contract/test_json_schema.py`: every `task list --json` entry carries `body`, every key it emits today keeps its name, and `task show --json` emits the same object shape (FR-027)
- [ ] T025 [P] [US3] Extend `tests/contract/test_exit_codes.py`: `task show` exits 0 when found (including a task with no body), 1 for an unknown id, and 2 for an ambiguous one
- [ ] T026 [P] [US3] Extend `tests/contract/test_streams.py` and `tests/contract/test_non_blocking.py` to cover `task show` — data on stdout, errors on stderr, no prompt, no editor, no ANSI on a non-TTY
- [ ] T027 [P] [US3] Integration test in `tests/integration/test_task_cli.py`: `task show` prints the body in human form, and `task done` leaves it intact

### Implementation for User Story 3

- [ ] T028 [P] [US3] Implement `get_task(workspace, task_id) -> Task` in `src/endpaper/core/tasks.py`, raising `NotFoundError` for an unknown id and `UsageError` naming both line numbers for a duplicated one
- [ ] T029 [P] [US3] Add `"body"` to the entries emitted by `print_tasks_json` in `src/endpaper/cli/output.py`, leaving the human `print_tasks_table` one line per task and unchanged
- [ ] T030 [US3] Add `print_task_show` and `print_task_show_json` to `src/endpaper/cli/output.py` per [contracts/cli.md](./contracts/cli.md) — the summary line, then the body verbatim after a blank line
- [ ] T031 [US3] Register the `task show <id> [--json]` subparser and its dispatch in `src/endpaper/cli/main.py`, mapping `NotFoundError` to exit 1 and `UsageError` to exit 2 through the existing error handling

**Checkpoint**: All three stories work independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Record the public API changes in `CHANGELOG.md`: the `body` key in `task list --json`, the new `task show` command, and the task line format's body extension (FR-030, Principle VI)
- [ ] T033 [P] Document task bodies and `task show` in `src/endpaper/core/templates/AGENTS.md.tmpl`, keeping it under roughly 60 lines, and update `README.md`'s task paragraph
- [ ] T034 [P] Extend `tests/contract/test_guidance_docs.py` so the guidance file is asserted to name the body format and `task show`
- [ ] T035 [P] Confirm `e` is listed in the footer and help pane for the task collection in `tests/unit/test_footer_bindings.py` and `tests/integration/test_help_pane_tui.py` (FR-024)
- [ ] T036 [P] Extend `tests/integration/test_task_handedit.py` and `tests/integration/test_task_no_loss.py` with body-bearing fixtures: irregular indentation, a fenced code block, a nested checkbox, and non-ASCII text, asserting no line is lost or reordered (SC-004)
- [ ] T037 [P] Extend `tests/integration/test_task_commonmark.py` to assert a file with bodies still renders as a nested checklist (SC-008)
- [ ] T038 Run `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src` and fix what they report
- [ ] T039 Walk [quickstart.md](./quickstart.md) end to end against a scratch workspace, including the byte-identical no-op save check
- [ ] T040 Verify the TUI on the target terminals named in the constitution (Windows Terminal, iTerm2, macOS Terminal, PuTTY, tmux) — manual, and the one task that cannot be automated

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Phase 1 — **blocks every user story**
- **US1 (Phase 3)**: depends on Phase 2 only
- **US2 (Phase 4)**: depends on Phase 2; its result is visible through US1's preview, but the file-level assertions stand alone
- **US3 (Phase 5)**: depends on Phase 2 only — fully independent of US1 and US2
- **Polish (Phase 6)**: depends on the stories it documents

### Within Each Story

Tests are written first and must fail before the implementation lands. In core, the model precedes
the parser, which precedes the writer; adapters come after the core function they call.

T018 → T019 (same writer, ordered). T020 → T021 → T022 (the editor generalisation precedes its task
target, which precedes the binding that opens it). T028 → T030 → T031 in the CLI.

### Parallel Opportunities

- T006, T007, T008 after T005
- All of Phase 3's tasks in parallel with all of Phase 5's — different files, no shared state
- T013 through T017 in parallel with each other
- T024 through T027 in parallel with each other
- Most of Phase 6 is `[P]`; only T038, T039, and T040 must come last

---

## Parallel Example: User Story 3

```bash
# Contract coverage, all independent files:
Task: "Extend tests/contract/test_json_schema.py with the body key"
Task: "Extend tests/contract/test_exit_codes.py with task show"
Task: "Extend tests/contract/test_streams.py and test_non_blocking.py with task show"

# Then core before adapters:
Task: "Implement get_task in src/endpaper/core/tasks.py"
Task: "Add body to print_tasks_json in src/endpaper/cli/output.py"
```

---

## Implementation Strategy

### MVP (User Story 1)

Phase 1 → Phase 2 → Phase 3. That alone ships something real: bodies written by hand or by an
assistant become visible in the TUI, with no editor work at all. Stop and validate here.

### Incremental Delivery

1. Setup + Foundational → every task knows its body
2. US1 → bodies are readable in the TUI → **MVP**
3. US2 → bodies are writable from the TUI
4. US3 → bodies are readable from the CLI
5. Polish → docs, changelog, tolerance and CommonMark coverage

US2 and US3 can be built in either order, or at once by different people.

---

## Notes

- The data-loss risk lives in Phase 2 and T018-T019. If any test budget is cut, it is not cut there.
- `Task.body` defaults to `""`, so every existing construction site keeps working and a task without
  a body stays indistinguishable from one before this feature.
- Commit after each task or logical group. Stop at any checkpoint to validate a story on its own.
