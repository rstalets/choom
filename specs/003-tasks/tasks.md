---

description: "Task list for 003-tasks"
---

# Tasks: Tasks (REQUIREMENTS.md §3.3) and the `YYYY/MM/` layout amendment (§4.6)

**Input**: Design documents from `/specs/003-tasks/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. Constitution Principle VI requires every acceptance criterion in a spec to map
to at least one test, so test tasks are not optional for this project.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
demonstrated independently. Phase 6 is not a user story — it is the layout amendment shipping on this
branch, sequenced before the `AGENTS.md` rewrite that describes it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, `src/` layout: `src/endpaper/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the baseline this feature is measured against

- [X] T001 Run `uv run pytest` and record the passing count (expected 154) — this is the baseline the Phase 2 regression gate (T019) and the Phase 6 gates (T057, T067) compare against, and it must be green before any code changes
- [X] T002 [P] Bump `__version__` to `0.0.3` in `src/endpaper/__init__.py`
- [X] T003 [P] Add an Unreleased `0.0.3` section to `CHANGELOG.md` with placeholders for the four new `task` commands, the `task list --json` schema, the task line format, and the `YYYY/MM/` layout change (Principle VI requires the task line format and the file layout to be recorded as public API)
- [X] T004 [P] Extend `tests/conftest.py` with a `tasks_file(workspace)` helper returning `workspace.root / "tasks.md"` and a `write_tasks(workspace, text, *, newline="\n")` fixture that writes raw bytes with newline translation off, so hand-edited-file tests can assert byte equality

**Checkpoint**: Baseline green and recorded; task fixtures available.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure parse/render layer and the atomic write primitive every story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**⚠️ This phase adds no user-visible behaviour.** It is where the feature's correctness lives: every
classification rule and every preservation rule is decided here, as string-in/data-out functions that
need neither a filesystem nor a terminal ([research.md R4](./research.md#r4-parsing-is-a-pure-text-to-data-function)).

- [X] T005 [P] Add the frozen slotted `Task` dataclass (`id: str | None`, `text: str`, `done: bool`, `type: str`, `tags: tuple[str, ...]`, `created: date | None`, `line: int`) to `src/endpaper/core/models.py` per [data-model.md](./data-model.md#entity-task)
- [X] T006 [P] Add the frozen slotted `ParsedTasks` dataclass (`tasks`, `warnings`, `lines`, `needs_id`) to `src/endpaper/core/models.py` per [data-model.md](./data-model.md#entity-parsedtasks-the-pure-parse-result)
- [X] T007 [P] Add the frozen slotted `TaskFilter` dataclass (`type`, `tags`, `include_done: bool = False`) to `src/endpaper/core/models.py` per [data-model.md](./data-model.md#entity-taskfilter)
- [X] T008 [P] Add a `tasks_file` property returning `self.root / "tasks.md"` to `Workspace` in `src/endpaper/core/models.py`
- [X] T009 [P] Extend `ScanWarningReason` in `src/endpaper/core/models.py` with `"task_unterminated_comment"`, `"task_malformed_comment"`, and `"task_invalid_value"`
- [X] T010 [P] Add `new_task_id(taken: Container[str]) -> str` to `src/endpaper/core/text.py` — `"t_"` plus 4 lowercase hex from `secrets.token_hex(2)`, retried until unused per [R3](./research.md#r3-task-identifier-format)
- [X] T011 Create `src/endpaper/core/tasks.py` with the task-line regex from [data-model.md](./data-model.md#grammar) — capturing indent, bullet marker, checkbox state, and the remainder — and a `_split_comment(rest)` helper that finds the **last** `<!-- ... -->` on the line
- [X] T012 In `src/endpaper/core/tasks.py`, implement `parse_tasks(text) -> ParsedTasks` covering the full classification table in [data-model.md](./data-model.md#classification-of-a-line): bare, malformed-unterminated, comment-without-recognized-keys (bare), malformed-unknown-token, well-formed-with-bad-`created` (kept, field dropped, warned), well-formed. It must never raise, and `"".join(result.lines)` must equal the input for any input
- [X] T013 In `src/endpaper/core/tasks.py`, implement `render_task_line(...)` emitting fields in the order `id`, `type`, `tags`, `created`, omitting empty ones entirely, and raising `UsageError` on empty text per [contracts/core-api.md](./contracts/core-api.md#pure-layer)
- [X] T014 In `src/endpaper/core/tasks.py`, implement the atomic write helper: read with `open(..., newline="")`, `splitlines(keepends=True)`, write a temp file in the same directory, `os.replace` over the original, and map `PermissionError`/`OSError` to `WorkspaceError` per [R6](./research.md#r6-writing-without-losing-anything)
- [X] T015 [P] In `src/endpaper/core/tasks.py`, implement `filter_tasks(tasks, f)` (conjunctive; oldest-first with undated last, stable within a date) and `match_task(task, query)` (case-insensitive substring over text, type, tags), mirroring `filter_documents` / `match_document`
- [X] T016 Export `Task`, `ParsedTasks`, `TaskFilter`, `parse_tasks`, `render_task_line`, `new_task_id`, `filter_tasks`, and `match_task` from `src/endpaper/core/__init__.py`
- [X] T017 [P] Create `tests/unit/test_task_parse.py`: the grammar table (indents, `-`/`*`/`+` markers, `[ ]`/`[x]`/`[X]`), every row of the classification table, and the **round-trip property** — `"".join(parse_tasks(text).lines) == text` for LF, CRLF, mixed endings, no final newline, and an empty file
- [X] T018 [P] Create `tests/unit/test_task_render.py` and `tests/unit/test_task_id.py`: rendered field order and omission of empty type/tags, empty text raising `UsageError`, `t_`+4-hex format, and collision retry when the generated id is already taken
- [X] T019 **Regression gate**: run `uv run pytest` and confirm the T001 count still passes with zero existing test files edited. Do not proceed to Phase 3 until this holds

**Checkpoint**: The parser is correct and provably lossless. Stories can now build on it.

---

## Phase 3: User Story 1 - Capture a task the moment it is agreed (Priority: P1) 🎯 MVP

**Goal**: One short line from either front door records a task in `tasks.md`, with no file, folder, or
format decision.

**Independent Test**: From a fresh workspace, add tasks from the command line and from the interface,
then open `tasks.md` in a plain text editor and confirm one checkbox line per task with description,
type, and tags intact — and that the file renders as a checklist in a markdown viewer.

### Tests for User Story 1 ⚠️

> **Write these first and confirm they FAIL before implementing.**

- [X] T020 [P] [US1] Create `tests/integration/test_task_cli.py` covering US1 scenarios 1, 3, 4: `task add` with `--type` and `--tag` appends exactly one line carrying text, id, type, tag, and today's date and prints the id; adding to a file with pre-existing prose leaves every pre-existing byte unchanged; a deleted `tasks.md` is recreated
- [X] T021 [P] [US1] Add to `tests/integration/test_task_cli.py` the tag and validation cases: repeated `--tag` preserves order and deduplicates, a `#tag` inside a quoted description is parsed out and stripped from the text, an empty-after-tag-removal description exits 2 with `tasks.md` untouched, and an invalid type or tag token exits 2
- [X] T022 [P] [US1] Create `tests/integration/test_task_tui.py` covering US1 scenario 2: `/task.followup send the vendor comparison #procurement` through the command bar produces a line matching the CLI's in every field except the generated id, and lands the user on the tasks collection with the new task selected (FR-044)
- [X] T023 [P] [US1] Create `tests/integration/test_task_commonmark.py` asserting a generated `tasks.md` parses as a CommonMark task list with the metadata comment invisible in rendered output (SC-004), using the `markdown-it-py` already present transitively via Textual

### Implementation for User Story 1

- [X] T024 [US1] Implement `add_task(workspace, description, *, type="", tags=(), now=None) -> Task` in `src/endpaper/core/tasks.py`: parse inline `#tags` and merge after explicit tags exactly as `create_document` does, validate the type and tag tokens, create `tasks.md` when absent, and append one line — adding the terminator the previously-final line lacked per [R6](./research.md#r6-writing-without-losing-anything)
- [X] T025 [US1] Export `add_task` from `src/endpaper/core/__init__.py`
- [X] T026 [US1] Add the `task` subparser group and the `task add` subcommand to `src/endpaper/cli/main.py` with `description`, `--type`, and repeatable `--tag`, reusing the `#`-hazard wording from `meeting new`'s description text
- [X] T027 [US1] Add a `_cmd_task_add` handler to `src/endpaper/cli/main.py` that prints the new task's **identifier** (not its path) to stdout and exits 0 per [contracts/cli.md](./contracts/cli.md#task-add)
- [X] T028 [US1] Add `task` and `tasks` to `VERBS` in `src/endpaper/tui/command_bar.py`, and extend `_run_command` so `task <description>` posts `CreateRequested("task", …)`, `task.<type> <description>` carries the type, bare `task` posts `BarError("task needs a description")`, and `tasks` posts `CollectionRequested("tasks")` per [contracts/tui.md](./contracts/tui.md#command-bar-grammar--additions)
- [X] T029 [US1] Add task state to `src/endpaper/tui/app.py`: `tasks: list[Task]`, `visible_tasks: list[Task]`, `show_done: bool = False`, a `warnings["tasks"]` entry, a `load_tasks` call on mount, and an `add_task_and_track` method that switches `active` to `"tasks"` on success and records `last_create_error` on `UsageError`
- [X] T030 [US1] Add `"tasks"` to `COLLECTIONS` and a `Tasks` label to `_COLLECTION_LABELS` in `src/endpaper/tui/list_screen.py`, add a `TaskRow(ListItem)` rendering checkbox, date, type, text, and tags, and branch `refresh_rows` on `app.active` to build task rows from `app.visible_tasks`
- [X] T031 [US1] In `src/endpaper/tui/list_screen.py`, clear the preview (`preview.update("")`) when the active collection is tasks — the pane stays visible and keeps its width, per FR-044b and [contracts/tui.md](./contracts/tui.md#layout) — and add the tasks empty-state message
- [X] T032 [US1] Handle the `"task"` variant of `CreateRequested` in `src/endpaper/tui/list_screen.py`, landing on the tasks collection with the new row selected and surfacing a create error in the status bar

**Checkpoint**: US1 is complete and is the MVP boundary — a user can capture a task from either front
door, and the file is a plain markdown checklist.

---

## Phase 4: User Story 2 - See what is open and check things off (Priority: P2)

**Goal**: List what is outstanding and complete it — one keystroke in the interface, one command on
the command line.

**Independent Test**: With a `tasks.md` containing a mix of open and completed tasks, list from both
front doors, toggle from each, and confirm the file changed in exactly the expected character
positions.

### Tests for User Story 2 ⚠️

- [X] T033 [P] [US2] Add to `tests/integration/test_task_cli.py` US2 scenarios 1 and 2: `task list` shows open tasks only, oldest first; `--all` includes completed ones distinguishably; `--type` and `--tag` combine conjunctively with `--all`; an absent or checkbox-free `tasks.md` lists nothing and exits 0
- [X] T034 [P] [US2] Add to `tests/integration/test_task_cli.py` US2 scenarios 5 and 6: `task done` and `task undone` change the file, a no-op toggle exits 0 without writing (assert mtime), an unknown id exits 1 changing nothing, and a duplicated id exits 2 with a message naming both line numbers
- [X] T035 [P] [US2] Add to `tests/integration/test_task_tui.py` US2 scenarios 3 and 4: `space` flips the checkbox in `tasks.md` while preserving the metadata comment and keeping the selection; `a` reveals completed rows struck through and hides them again; the `a` state survives switching to another collection and back
- [X] T036 [P] [US2] Add to `tests/integration/test_task_tui.py` the inertness cases: on the meetings and notes collections `space` and `a` do nothing and raise nothing, and the footer does not advertise them
- [X] T037 [P] [US2] Create `tests/integration/test_task_parity.py` for FR-026: toggling a task with `endpaper task done` and toggling the same task with `space` in the interface produce byte-identical files
- [X] T038 [P] [US2] Add the seven task keys to `tests/contract/test_json_schema.py` and assert `id` and `created` may be null while `type` is `""` and `tags` is `[]`, never null

### Implementation for User Story 2

- [X] T039 [US2] Implement `load_tasks(workspace) -> tuple[list[Task], list[ScanWarning]]` in `src/endpaper/core/tasks.py` — read, parse, return records; a missing `tasks.md` is an empty list, not an error. Identifier backfill is added in Phase 5 (T054)
- [X] T040 [US2] Implement `set_task_state(workspace, task_id, *, done) -> Task` in `src/endpaper/core/tasks.py`: re-read and re-parse, locate by id (never by cached line number, per [R7](./research.md#r7-locate-by-identifier-at-write-time-never-by-cached-line-number)), change only the checkbox character, no-op when already in that state, raise `NotFoundError` on no match and `UsageError` naming line numbers on more than one
- [X] T041 [US2] Export `load_tasks` and `set_task_state` from `src/endpaper/core/__init__.py`
- [X] T042 [P] [US2] Add `print_tasks_table` and `print_tasks_json` to `src/endpaper/cli/output.py` — tab-separated `id, state, created|-, type, text, tags` for the table, and the seven fixed keys for JSON per [contracts/cli.md](./contracts/cli.md#task-list)
- [X] T043 [US2] Add the `task list` subcommand to `src/endpaper/cli/main.py` with `--json`, `--all`, `--type`, and repeatable `--tag`, plus a `_cmd_task_list` handler that routes scan warnings to stderr and data to stdout
- [X] T044 [US2] Add the `task done` and `task undone` subcommands and handlers to `src/endpaper/cli/main.py` — silent on success, exit codes per the table in [contracts/cli.md](./contracts/cli.md#task-done--task-undone)
- [X] T045 [US2] Add `action_toggle_task` and `action_toggle_show_done` to `src/endpaper/tui/list_screen.py`, bound to `space` and `a`, both returning immediately unless `app.active == "tasks"` per [R9](./research.md#r9-the-task-surface-in-the-tui); the toggle calls `set_task_state`, re-reads only `tasks.md`, keeps the selection on the toggled task, and shows a write failure in the status bar
- [X] T046 [US2] Add `TASK_LIST_HELP` to `src/endpaper/tui/status_bar.py` and select the footer text per active collection in `_render_status`, so `space toggle` and `a all` appear only where they fire (FR-041)
- [X] T047 [US2] Apply the live filter and `show_done` to tasks in `src/endpaper/tui/app.py` via `match_task` and `filter_tasks`, keeping the per-collection filter behaviour documents already have

**Checkpoint**: US1 and US2 work independently. The full §3.3 command surface exists from both front
doors.

---

## Phase 5: User Story 3 - Hand-edit `tasks.md` and lose nothing (Priority: P3)

**Goal**: The user edits `tasks.md` in any editor; endpaper picks up what it can, repairs only what is
safe, and never destroys what it cannot understand.

**Independent Test**: Build a `tasks.md` by hand containing well-formed tasks, a bare checkbox, a
truncated comment, headings, prose, and an indented sub-list; list and toggle; diff the file before
and after.

### Tests for User Story 3 ⚠️

- [X] T048 [P] [US3] Create `tests/integration/test_task_handedit.py` covering US3 scenarios 1–3: a bare `- [ ] buy milk` gains an id in place with the rest of the line and file unchanged; `- [ ] thing <!-- id:` is skipped, warned, and left byte-identical; headings, prose, and non-task list items survive verbatim
- [X] T049 [P] [US3] Add to `tests/integration/test_task_handedit.py` US3 scenario 4 and the line-ending rules: a CRLF file with no final newline keeps both properties across a toggle and across backfill, and `add_task` on such a file adds the terminator the previously-final line lacked and nothing else
- [X] T050 [P] [US3] Add to `tests/integration/test_task_handedit.py` the user-comment case: `- [ ] fix the <!-- hack --> path` is treated as a bare task, keeps its own comment, and gains a metadata comment after it that round-trips to the same text on the next scan
- [X] T051 [P] [US3] Add a read-only degradation test to `tests/integration/test_task_handedit.py`: with `tasks.md` not writable, `task list --json` still lists, un-backfilled tasks report `"id": null`, a warning goes to stderr, exit 0 — and `task done` exits 3 leaving the file unchanged (FR-038)
- [X] T052 [P] [US3] Create `tests/integration/test_task_no_loss.py` for SC-003: apply a randomised sequence of 1,000 add/complete/reopen operations and assert no task text is lost or altered and no non-task line changed
- [X] T053 [P] [US3] Add a mixed-damage test to `tests/integration/test_malformed.py`: a `tasks.md` where one line in ten is malformed still lists 100% of the well-formed tasks with no crash (SC-005)

### Implementation for User Story 3

- [X] T054 [US3] Extend `load_tasks` in `src/endpaper/core/tasks.py` to act on `ParsedTasks.needs_id`: generate ids for bare lines, write the repaired text back through the atomic helper, and return records carrying the new ids per [R5](./research.md#r5-who-writes-the-backfilled-identifiers-and-when). Backfill writes **`id` only** — never an invented `created` ([R8](./research.md#r8-a-hand-written-task-has-no-creation-date-and-endpaper-does-not-invent-one))
- [X] T055 [US3] Make backfill best-effort in `src/endpaper/core/tasks.py`: a failed write returns the records with `id=None` on the affected tasks plus a warning, and the read still succeeds (FR-038)
- [X] T056 [US3] Route task scan warnings to stderr in `src/endpaper/cli/main.py` and to the status-bar warning count in `src/endpaper/tui/list_screen.py`, reusing the `warnings[collection]` mechanism feature 002 established (FR-039)

**Checkpoint**: The file is safe to hand-edit. This is the property that makes the format the product.

---

## Phase 6: Layout amendment — partition dated files by `YYYY/MM/`

**Purpose**: Implement REQUIREMENTS.md §4.6 and feature 001's
[Amendments](../001-meeting-notes/spec.md#amendments), which this branch specified but did not build

**Not a user story.** It touches no task code — `tasks.md` is a single file at the workspace root with
nothing to partition. It is sequenced here because Phase 7 rewrites the `AGENTS.md` that describes the
layout, and that file must not describe a layout the code does not implement.

- [X] T057 Confirm the suite is green before starting, so any breakage in this phase is attributable to it
- [X] T058 [P] Create `tests/integration/test_partitioned_layout.py` asserting: a created meeting lands in `meetings/YYYY/MM/`, a typed note in `notes/YYYY/MM/`, a daily note in `notes/daily/YYYY/MM/`, the partition directories are created on demand, and the filename still carries the full ISO date
- [X] T059 [P] Add to `tests/integration/test_partitioned_layout.py` the frontmatter-is-authoritative cases (FR-015a): a file placed under the wrong month still lists and is **not moved**, and a file left directly under `meetings/` still lists
- [X] T060 [P] Add a daily-note single-listing test to `tests/integration/test_partitioned_layout.py`: a workspace with exactly one daily note lists exactly one daily note — the assertion that catches the `scan_dirs` overlap in T063
- [X] T061 In `src/endpaper/core/documents.py`, make `create_document` write into `collection.create_dir / f"{when:%Y/%m}"`; the existing `mkdir(parents=True, exist_ok=True)` already makes partition creation on demand free
- [X] T062 In `src/endpaper/core/documents.py`, change `scan_documents` from `directory.glob("*.md")` to `directory.rglob("*.md")` so a collection's whole subtree is walked
- [X] T063 In `src/endpaper/core/notes.py`, change `NOTES.scan_dirs` from `("notes", "notes/daily")` to `("notes",)` — under `rglob` the first entry already sweeps the second, and leaving both listed every daily note twice. Daily notes stay distinguishable by `type: daily`, which is how the code already tells them apart
- [X] T064 In `src/endpaper/core/notes.py`, apply the same `YYYY/MM` partition to `open_daily_note`, which builds its path directly (`workspace.daily_dir / f"{when:%Y-%m-%d}.md"`) instead of going through `create_document` — the easiest call site to miss, and the highest-volume collection
- [X] T065 [P] Update `tests/unit/test_path_budget.py` for the new worst case: the partition adds 8 characters, taking the generated path from 107 to 115 below the workspace root, still inside the ≤120 budget — the slug and type caps do not change
- [X] T066 [P] Update `tests/fixtures/generate.py` so generated workspaces write into partitioned paths, keeping the performance fixtures representative
- [X] T067 **Gate**: run `uv run pytest` and confirm every pre-existing test passes. Any test that needed a path edit must be a path edit only — a behaviour change here means the amendment has broken something it should not

**Checkpoint**: The layout on disk matches the layout the specs describe, for all three dated
collections.

---

## Phase 7: User Story 4 - An AI assistant manages the list unattended (Priority: P4)

**Goal**: An assistant adds, reads back, and completes tasks with no terminal, no prompts, and no
guesswork about success.

**Independent Test**: Run every task command with output redirected and stdin closed; confirm JSON
parses, output carries no decoration, warnings never reach stdout, and exit codes distinguish
success, not-found, usage error, and workspace error.

### Tests for User Story 4 ⚠️

- [X] T068 [P] [US4] Extend `tests/contract/test_no_ansi.py` and `tests/contract/test_streams.py` to cover all four task commands: no `\x1b` byte in redirected output, data on stdout and diagnostics on stderr, never interleaved
- [X] T069 [P] [US4] Extend `tests/contract/test_non_blocking.py` to run each task command with stdin closed and assert none hangs, opens an editor, or waits for a keypress
- [X] T070 [P] [US4] Extend `tests/contract/test_exit_codes.py` with the task rows: 0 success, 1 unknown id, 2 usage error and duplicate id, 3 outside a workspace and unwritable file
- [X] T071 [P] [US4] Extend `tests/contract/test_agents_md.py` to assert the generated `AGENTS.md` documents the task line format, the four task commands, and the `YYYY/MM/` layout, and to move the stricter line assertion from `<= 58` to the constitution's "roughly 60 lines" bound already used by the other test

### Implementation for User Story 4

- [X] T072 [US4] Rewrite `src/endpaper/core/templates/AGENTS.md.tmpl` in one pass: replace the "`tasks.md` reserved for a future feature" line with the task line format and the four task commands, and update the layout block to show the `YYYY/MM/` partitions. **The budget is the binding constraint** — the template is 58 lines today with no slack, so trim as well as add; shorten the meetings frontmatter example first, since an assistant can infer the schema from any file it opens
- [X] T073 [US4] Verify `endpaper --help` and `endpaper task add --help` both state that `--tag` is the command-line form and that an unquoted `#tag` is eaten by the shell (§3 tagging rule)

**Checkpoint**: The command line is a complete, non-interactive contract for an assistant.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T074 [P] Create `tests/performance/test_task_scan.py` generating a 1,000-task `tasks.md` and asserting `load_tasks` completes in under one second (SC-007)
- [X] T075 [P] Finalise the `0.0.3` section of `CHANGELOG.md`: the four commands, the `task list --json` seven-key schema, the task line format, the `YYYY/MM/` layout with a note that it is a breaking change to file locations, and the unchanged exit codes
- [X] T076 [P] Update `README.md` for the task commands and the partitioned layout if it documents either
- [X] T077 Run the [quickstart](./quickstart.md) end to end by hand, including the CRLF and read-only checks in Scenario 3 and the interface walkthrough in Scenario 5
- [X] T078 Run `uv run ruff format --check . && uv run ruff check . && uv run mypy src` and fix anything outstanding
- [ ] T079 Verify the interface on the target terminals per the constitution's Development Workflow gate: Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux — with particular attention to `space` reaching the app and to CRLF preservation on Windows

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: depends on Phase 1 — **blocks every story**
- **Phase 3 (US1)**: depends on Phase 2
- **Phase 4 (US2)**: depends on Phase 3 (needs `add_task` to have tasks to list, and the tasks collection to toggle in)
- **Phase 5 (US3)**: depends on Phase 4 (extends `load_tasks`)
- **Phase 6 (Layout)**: depends only on Phase 1 — **independent of every task phase** and can be built at any point, or on its own branch; it is placed before Phase 7 only because T072 documents it
- **Phase 7 (US4)**: depends on Phase 4 for the commands it audits and on Phase 6 for the layout it documents
- **Phase 8 (Polish)**: depends on everything

### User Story Dependencies

- **US1 (P1)**: needs only the foundational layer. **The MVP.**
- **US2 (P2)**: builds on US1 — you cannot check off a task you cannot create
- **US3 (P3)**: extends US2's `load_tasks` with backfill; its guarantees are testable the moment US2 exists
- **US4 (P4)**: an audit of what US1–US2 already built, plus the `AGENTS.md` rewrite

The stories are sequential rather than parallel here because they share one file and one module —
that is the nature of a feature whose whole surface is `tasks.md`.

### Within Each Story

Tests first (they should fail), then core, then the CLI adapter, then the TUI adapter. The core
function is always written before either front door so neither adapter grows behaviour of its own
(Principle I).

### File-conflict notes

- Phase 2's `models.py` tasks (T005–T009) all edit one file. They are marked `[P]` because they are
  independent additions, but a single agent should apply them in one pass rather than racing
- T028–T032 all touch the TUI; `command_bar.py`, `app.py`, and `list_screen.py` are separate files but
  the change is one coherent edit — sequence them
- T033/T034 and T020/T021 append to the same test file; write them in order
- T061/T062 edit `documents.py` and T063/T064 edit `notes.py` — the two pairs are parallelisable
  against each other

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 in parallel
- **Phase 2**: T005–T010 in parallel (models and text helpers), then T011–T014 sequentially in
  `tasks.py`, then T017/T018 in parallel
- **Phase 3**: all four test tasks (T020–T023) in parallel before implementation
- **Phase 4**: all six test tasks (T033–T038) in parallel; T042 parallel with core work
- **Phase 5**: all six test tasks (T048–T053) in parallel
- **Phase 6**: T058–T060 in parallel; T065/T066 in parallel
- **Phase 7**: all four test tasks (T068–T071) in parallel
- **Phase 8**: T074, T075, T076 in parallel

---

## Implementation Strategy

### MVP First (User Story 1)

Phases 1 → 2 → 3 deliver capture from both front doors, into a file any markdown viewer renders as a
checklist. That is REQUIREMENTS.md §3.3's reason to exist, and it is demonstrable on its own.

### Incremental Delivery

1. **Phases 1–3** — capture. Ship, use it for a day.
2. **Phase 4** — list and complete. The full §3.3 surface.
3. **Phase 5** — hand-editing guarantees. Nothing new is visible; everything becomes trustworthy.
4. **Phase 6** — the layout amendment. Independent; can ship before or after any of the above.
5. **Phases 7–8** — the assistant contract, documentation, and hardening.

Stage 4 in the plan's sequencing table is the point at which an assistant can do useful task work
unaided, even though the polish phase has not run.

### Suggested split if two people work in parallel

Phase 6 shares no file with Phases 2–5. One person can take the layout amendment start to finish
while another works the task phases; the only meeting point is T072, the single `AGENTS.md` rewrite.

---

## Notes

- **The regression gates (T019, T057, T067) are not ceremony.** This feature edits a file the user
  owns and changes where every existing file is written. Both are places where a green suite is the
  only evidence that nothing was lost.
- **`[P]` means different files with no ordering dependency**, not "safe to skip review".
- Every task above maps to at least one requirement, acceptance scenario, or success criterion in
  [spec.md](./spec.md); the constitution requires that mapping to run in the other direction too, so
  a criterion without a test is a missing task, not an accepted gap.
