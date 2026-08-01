---

description: "Task list for 011-ui-refinements"
---

# Tasks: UI Refinements

**Input**: Design documents from `/specs/011-ui-refinements/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. The constitution's Development Workflow requires behaviour changes to land with the
tests that cover them, and Principle VI makes that coverage risk-based rather than one test per
acceptance scenario — research R12 assigns each behaviour to the layer where it can actually break.

**Test runner**: `scripts/dev-tests.sh` (repo `CLAUDE.md`), never a hand-rolled `pytest`. Args pass
through: `scripts/dev-tests.sh tests/unit -k columns`.

**Organization**: Tasks are grouped by user story. Story order is the build order — US1 must precede US2
(FR-026: deletion's confirmation is the confirmation US1 builds).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## Path Conventions

Single project: `src/choom/`, `tests/` at repository root.

---

## Phase 1: Setup

**Purpose**: Establish a known-good starting point on the merged branch

- [X] T001 Run `scripts/dev-tests.sh` and record the green baseline (733 tests at the merge of
      `010-read-on-load`), so any later failure is attributable to this feature
- [X] T002 [P] Re-read `src/choom/tui/list_screen.py`'s refresh timer and `on_screen_suspend`/
      `on_screen_resume` pair to confirm research R11 still holds: pushing a modal pauses the timer

**Checkpoint**: Baseline green, refresh-timer assumption verified

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `core` deletion capability both front-ends call

**⚠️ Blocks US2, US3, and US4.** US1, US5, US6, and US7 do not depend on this phase and may proceed in
parallel with it.

- [X] T003 [P] Unit tests for task-line removal in `tests/unit/test_delete_task.py`: body span removed
      whole, neighbouring tasks byte-identical, CRLF and LF files, trailing-newline state preserved,
      missing id raises `NotFoundError`, duplicate id raises `UsageError` naming the lines. Must fail first
- [X] T004 [P] Unit tests for id dispatch in `tests/unit/test_deletion.py`: unresolvable id →
      `NotFoundError`, ambiguous id → `UsageError` naming every path, `expect` mismatch → `NotFoundError`,
      each kind routed to the right remover. Must fail first
- [X] T005 [P] Implement `delete_document(path: Path) -> None` in `src/choom/core/documents.py` — removes
      the file, raises `NotFoundError` if absent and `WorkspaceError` on failure; leaves the containing
      directory in place even if it becomes empty (data-model §2)
- [X] T006 [P] Implement `delete_task(workspace: Workspace, task_id: str) -> Task` in
      `src/choom/core/tasks.py`, reusing `set_task_body`'s locate-by-id, `_body_span`, newline and
      trailing-newline handling, and `_atomic_write` (research R2)
- [X] T007 Create `src/choom/core/deletion.py` with the `Deleted` dataclass and
      `delete_by_id(workspace, record_id, *, expect=None) -> Deleted`, converting `links.resolve_id`'s
      warnings into the refusals of research R4 (depends on T005, T006)

**Checkpoint**: `core` can delete any record by id, with ambiguity and wrong-collection refused

---

## Phase 3: User Story 1 - Confirmations are a line with two named keys (Priority: P1) 🎯 MVP

**Goal**: One confirmation component: slim, centred, `Esc` stops, `Enter` proceeds, no buttons

**Independent Test**: Edit a document, leave without saving. The dialog is a slim centred bar; `Esc`
returns with edits intact, `Enter` leaves without saving; no other key does anything.

- [ ] T008 [US1] Rewrite `tests/integration/test_discard_tui.py` against `ConfirmDialog`: assert the two
      key labels, that `escape` cancels and `enter` proceeds, and that an unrelated key is swallowed.
      Must fail first
- [ ] T009 [P] [US1] Create `src/choom/tui/confirm_dialog.py` with
      `ConfirmDialog(ModalScreen[bool])` — question plus two labels, `Label` widgets only, no `Button`,
      bindings `escape` → `dismiss(False)` and `enter` → `dismiss(True)` (contracts/tui-chrome §1)
- [ ] T010 [US1] Replace `#discard-dialog`, `#discard-buttons`, `#discard-buttons Button`, and
      `DiscardDialog` rules in `src/choom/tui/app.tcss` with a slim centred `#confirm-dialog`
- [ ] T011 [US1] Point `src/choom/tui/edit_screen.py` at `ConfirmDialog` with "You have unsaved changes.
      Are you sure you want to exit?" / `(Esc) Continue Editing` / `(Enter) Exit Without Saving`, and
      delete `src/choom/tui/discard_dialog.py`
- [ ] T012 [P] [US1] Update the remaining `DiscardDialog` references in
      `tests/integration/test_task_body_tui.py` and `tests/integration/test_mirror_propagation.py`

**Checkpoint**: One dialog class exists; `grep -r DiscardDialog` returns nothing

---

## Phase 4: User Story 2 - Delete a record without leaving the tool (Priority: P2)

**Goal**: `ctrl+d` on a highlighted row, confirmed, removes the record

**Independent Test**: Delete a meeting, a note, and a task with a multi-line body from the list; each is
gone from disk (or from `tasks.md`) with neighbours untouched. Decline and nothing changes.

**Depends on**: Phase 2 (core deletion) and Phase 3 (the dialog it raises)

- [ ] T013 [US2] Integration test `tests/integration/test_delete_tui.py`: confirm deletes and declines
      does not; highlight moves to the next record, to the previous when last, to the empty state when
      only; a task's body goes with it and neighbouring tasks are byte-identical; a row whose file was
      removed out of process (`delete_file_out_of_process` in `tests/helpers.py`) reports and refreshes.
      Must fail first
- [ ] T014 [US2] Add the `ctrl+d` binding and `action_delete` to `src/choom/tui/list_screen.py`: no-op
      when nothing is highlighted or the command bar is open, and capture the record id when raising the
      dialog (FR-010, research R11)
- [ ] T015 [US2] Wire the dialog callback to `core.deletion.delete_by_id` and re-read the list, applying
      the highlight rules of contracts/tui-chrome §2 (depends on T014)
- [ ] T016 [US2] Report `NotFoundError`, `UsageError`, and `WorkspaceError` in the status bar and keep the
      session usable (FR-013)
- [ ] T017 [P] [US2] Add `ctrl+d delete` to `LIST_HELP` and `TASK_LIST_HELP` in
      `src/choom/tui/status_bar.py` (FR-014)

**Checkpoint**: Records can be deleted from the list; nothing else on screen changed

---

## Phase 5: User Story 3 - Delete a record from the command line (Priority: P3)

**Goal**: `choom <type> delete <id> --force`, non-blocking, silent on success

**Independent Test**: Delete each record type by id with the flag (exit 0, empty stdout); rerun (exit 1);
omit the flag (exit 2, nothing deleted); run with stdin closed and confirm it never waits.

**Depends on**: Phase 2. **No dependency on Phase 3** — the CLI never confirms.

- [ ] T018 [US3] Contract tests `tests/contract/test_cli_delete.py` covering every row of
      contracts/cli-delete.md: exit codes 0/1/2/3, empty stdout on success, messages on stderr, `--force`
      required, wrong-collection refusal, and a stdin-closed non-blocking check. Must fail first
- [ ] T019 [US3] Add `delete` subparsers with a positional `id` and a required `--force` to the meeting,
      note, and task parsers in `src/choom/cli/main.py`
- [ ] T020 [US3] Add `_cmd_meeting_delete`, `_cmd_note_delete`, and `_cmd_task_delete` over
      `delete_by_id(..., expect=<kind>)` and route them in `_dispatch` (depends on T019)

**Checkpoint**: Both front-ends delete, through one core function

---

## Phase 6: User Story 4 - A deleted task's mirrors stay in the user's words (Priority: P4)

**Goal**: Deleting a task leaves every mirroring document byte-identical, with the link reported dead

**Independent Test**: Capture a task from a note, delete the task, reopen the note — the line is exactly
as typed and a dead-link warning is surfaced.

**Depends on**: Phase 2. Test-only — research R3 establishes that `mirrors.py` already handles this.

- [ ] T021 [US4] Integration test `tests/integration/test_delete_mirrors.py`: the mirroring document is
      byte-identical after the delete; opening it surfaces a `link_dead` warning; ticking the orphaned
      checkbox still saves; several documents mirroring one task are all left unmodified

**Checkpoint**: Deleting a task cannot damage a file the user did not ask to touch

---

## Phase 7: User Story 5 - The list reads as four labelled columns (Priority: P5)

**Goal**: Date, type, title, tags in fixed labelled columns that hold position

**Independent Test**: With records covering every combination of missing type and missing tags, titles
start at the same column on every row and empty cells stay empty.

**Independent of** every other phase.

- [ ] T022 [P] [US5] Unit tests `tests/unit/test_columns.py`: widths at 80 and at narrow terminals, drop
      order tags-then-type with headers, date and title always kept, ellipsis truncation, empty cells
      holding position. Must fail first
- [ ] T023 [US5] Create `src/choom/tui/columns.py` with `column_widths`, `render_row`, and
      `render_header` — pure functions, no widget imports (research R8)
- [ ] T024 [US5] Add a non-scrolling header `Static` above `#meeting-list` inside `#list-pane` in
      `src/choom/tui/list_screen.py`, with its CSS rule in `src/choom/tui/app.tcss`
- [ ] T025 [US5] Rewrite `DocumentRow._row_text` and `TaskRow._row_text` to call `render_row`, keeping
      `document`/`record` attribute names, the task's leading done marker, and the struck-through style;
      re-render header and rows on `Resize` (depends on T023)
- [ ] T026 [US5] Integration test `tests/integration/test_list_columns_tui.py`: header present, alignment
      holds across records with and without type and tags, in both documents and tasks

**Checkpoint**: The list is a table; `row_titles` in `tests/helpers.py` still passes untouched

---

## Phase 8: User Story 6 - The top bar names the workspace (Priority: P6)

**Goal**: The workspace path in the top-right corner, shortened rather than sprawling

**Independent Test**: Launch against two workspaces, one under `$HOME` and one with a space and a
non-ASCII character; the path is flush right and stays there across a resize.

**Independent of** every other phase.

- [ ] T027 [P] [US6] Unit tests `tests/unit/test_workspace_path.py`: `$HOME` → `~`, left elision with
      `…/` on whole components, final component always kept, spaces and non-ASCII intact. Must fail first
- [ ] T028 [US6] Add the shortening helper and right-aligned rendering to
      `src/choom/tui/collection_bar.py`, padding against the bar's own width the way `StatusBar` pins the
      version, with no filesystem access on redraw (research R9)
- [ ] T029 [US6] Pass the workspace into `CollectionBar` from `src/choom/tui/list_screen.py`'s `compose`
      (depends on T028)
- [ ] T030 [US6] Update `tests/integration/test_chrome_tui.py`,
      `tests/integration/test_narrow_terminal_tui.py`, and
      `tests/integration/test_collection_menu_tui.py` for the bar's new content, including that the
      compact one-letter fallback still wins at the narrowest widths and the bottom bar is unchanged

**Checkpoint**: The workspace is readable from the corner; the bottom bar has lost no width

---

## Phase 9: User Story 7 - The cursor starts where the next words go (Priority: P7)

**Goal**: Edit mode opens with the cursor one blank line below the content, and that is not an edit

**Independent Test**: Open a multi-line note with `e` — the cursor is on an empty line one blank line
below the last content. Leave without typing — no confirmation, file unchanged.

**Independent of** every other phase.

- [ ] T031 [P] [US7] Unit tests `tests/unit/test_cursor_placement.py` for the padding rule: content
      without trailing blanks, content with several, empty content, and the resulting cursor row.
      Must fail first
- [ ] T032 [US7] In `src/choom/tui/edit_screen.py`, compute the padded text once at construction, load
      the `TextArea` with it, set `original_text` to the padded text so `is_dirty` stays false, and place
      the cursor on the last line at column 0 — for documents and task bodies alike (research R10)
- [ ] T033 [US7] Extend `tests/integration/test_edit_from_list_tui.py`: entering and leaving edit mode
      without typing raises no confirmation and leaves the file's bytes unchanged (FR-042)

**Checkpoint**: Appending to a note costs zero cursor-movement keystrokes

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Add the three delete commands to the Commands block in
      `src/choom/core/templates/AGENTS.md.tmpl`, with the `--force` rule stated; confirm the file stays
      under the ~100-line backstop (it is 74 today)
- [ ] T035 [P] Update `README.md` for deletion in both front-ends, the four-column list, and the
      workspace path in the top bar
- [ ] T036 Run every scenario in [quickstart.md](./quickstart.md) by hand against a scratch workspace
- [ ] T037 Run the full gate set: `scripts/dev-tests.sh`, `uv run --extra dev ruff format --check .`,
      `uv run --extra dev ruff check .`, `uv run --extra dev mypy`
- [ ] T038 Verify the TUI on the target terminals in `docs/REQUIREMENTS.md` §4.3 — the column layout and
      the top-bar path are the two new width-sensitive surfaces
- [ ] T039 Verify a workspace path containing spaces and non-ASCII characters renders and deletes
      correctly on at least one platform other than the development machine

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: blocks Phases 4, 5, and 6 only
- **US1 (Phase 3)**: blocks Phase 4. Independent of Phase 2
- **US2 (Phase 4)**: needs Phase 2 **and** Phase 3
- **US3 (Phase 5)**: needs Phase 2 only
- **US4 (Phase 6)**: needs Phase 2 (and, in practice, Phase 4 for the delete gesture under test)
- **US5, US6, US7 (Phases 7–9)**: independent of everything above and of each other
- **Polish (Phase 10)**: after the stories being shipped are complete

### The one binding order

US1 before US2. Deletion is this feature's only new confirmation point and FR-026 allows exactly one
confirmation component — building the delete against today's dialog means building it twice and shipping
the button-and-highlight style in between.

### Parallel Opportunities

- T003–T006 are four different files: all parallel
- Phases 3, 5, 7, 8, and 9 touch disjoint files and can run concurrently once Phase 2 is done
  (Phase 5 needs Phase 2; Phases 7–9 need nothing)
- Within each story, the `[P]` test task can be written while its implementation task is in progress by
  someone else, but must fail before the implementation lands

---

## Parallel Example: Phase 2

```bash
Task: "Unit tests for task-line removal in tests/unit/test_delete_task.py"
Task: "Unit tests for id dispatch in tests/unit/test_deletion.py"
Task: "Implement delete_document in src/choom/core/documents.py"
Task: "Implement delete_task in src/choom/core/tasks.py"
```

---

## Implementation Strategy

### MVP (US1 alone)

Phase 1 → Phase 3. The discard confirmation becomes slim, centred, and one-keypress. Shippable on its own
with no deletion anywhere.

### Recommended increment

Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6. This is the whole deletion capability in both
front-ends with its safety properties proven, which is the feature's substance.

### Finishing

Phases 7, 8, and 9 in any order — three independent presentation improvements — then Phase 10.

---

## Notes

- `[P]` = different files, no dependencies
- Every behaviour change lands with its test, in the same commit where practical
- Verify each test fails before writing the implementation it covers
- No test may sleep or read the wall clock (Principle VI)
- Stop at any checkpoint to validate a story independently
