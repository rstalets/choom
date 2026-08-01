---

description: "Task list for 010-read-on-load"
---

# Tasks: Read From Disk on View Load

**Input**: Design documents from `/specs/010-read-on-load/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/view-refresh.md](./contracts/view-refresh.md)

**Tests**: Included, and not optional here. Constitution Principle VI requires risk-based coverage of every
user-facing behaviour, and the Development Workflow section requires behaviour changes to land with the
tests that cover them. Coverage below is chosen by failure mode, not one test per acceptance scenario —
US1 has 24 acceptance scenarios across the spec and 6 test tasks.

**Organization**: Grouped by user story. US1 is the whole correctness fix and ships alone; US2 and US3 each
depend on US1 having removed the cache, and are independent of each other.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project: `src/choom/`, `tests/` at repository root. This feature touches `src/choom/tui/` only —
no `core` change (research R1, "Resolved unknowns").

---

## Phase 1: Setup

**Purpose**: Establish the baseline this change is measured against.

- [X] T001 Run `uv run pytest -q` and record the green baseline, so any failure later in this feature is
      attributable to it rather than pre-existing. Confirm the branch is `worktree-010-read-on-load`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one shared test facility every story's tests need.

**⚠️ CRITICAL**: T002 blocks the test tasks in all three stories.

- [X] T002 Add out-of-process mutation helpers to `tests/helpers.py`: create a document, complete a task,
      delete a file, and write a malformed file, each by calling `choom.core` directly rather than through
      the running app. Document in the docstring that these run in-process but bypass the app entirely,
      which is the condition that matters — the app receives no notification either way. Derive any dates
      from the same clock the behaviour reads (Principle VI; `in_scope_month` in the same file is the
      existing pattern).

**Checkpoint**: Story phases can begin.

---

## Phase 3: User Story 1 - An assistant's changes appear when the view is opened (Priority: P1) 🎯 MVP

**Goal**: Every list load, every return to a list, and every document open reads from disk. The session
snapshot and all machinery for keeping it fresh are deleted.

**Independent Test**: With the app parked on any list, change the workspace without going through the app
(create, delete, edit a body, complete a task), navigate away and back, and confirm the view matches disk.
Reproduces and fixes issue #51's report of one meeting where there are two and an open task that is done on
disk.

### Tests for User Story 1

> Write these first and confirm they fail against the current cache before implementing. T003–T005 are new
> files or new test functions; T006–T008 update existing tests that assert cache mechanics (research R10).

- [X] T003 [P] [US1] Integration test in `tests/integration/test_out_of_process_changes.py` covering the
      four mutation shapes observed after navigating away and back: document created, document deleted,
      document body/title rewritten, task completed. Covers FR-001, FR-002, FR-004, SC-001. Note in the
      module docstring that `tests/integration/test_external_edits.py` is a different concern — foreign
      formatting round-tripped through the editor, written before the app starts.
- [X] T004 [P] [US1] Integration test in `tests/integration/test_out_of_process_changes.py`: a malformed
      document written while the app runs is skipped on the next load, the rest of the list renders, and the
      status bar's warning count reflects the current workspace rather than the count taken at mount.
      Covers FR-007, FR-008, contract C6.
- [X] T005 [P] [US1] Integration test in `tests/integration/test_out_of_process_changes.py`: opening a
      document in the preview after it was rewritten shows the current body (FR-003, research R7); and
      ticking a checkbox inside a document body then returning to the Tasks list shows the task done, with
      no refresh call wired for that path (FR-006, SC-007, contract C2).
- [X] T006 [US1] Update the helper at `tests/integration/test_daily_note_tui.py:16` to stop indexing
      `app.month_cache[("notes", …)]` and read through `app.visible_documents()` instead.
- [X] T007 [US1] Update `tests/integration/test_mirror_reconcile_save.py::test_saving_without_touching_a_mirror_does_not_reload_tasks`
      to assert the user-visible outcome — the mirror file is not rewritten — rather than counting calls to
      `reload_tasks`, which T012 deletes. Rename the test accordingly.
- [X] T008 [P] [US1] Rename `cached_before` / `cached_after` at `tests/integration/test_mirror_propagation.py:195-206`
      to reflect that both are now fresh reads. Assertions are unchanged.

### Implementation for User Story 1

- [X] T009 [US1] In `src/choom/tui/app.py`, make `visible_documents()` scan on every call: `scan_month` for
      a month selection, `scan_unfiled` for the unfiled selection, and the existing all-months walk for an
      active filter. Keep the read scoped to the displayed selection — a list load must not read the whole
      collection (research R2, contract C3).
- [X] T010 [US1] In `src/choom/tui/app.py`, make `visible_tasks()` call `load_tasks` on every call and
      `visible_warnings()` return the warnings from the read that produced the current rows.
- [X] T011 [US1] In `src/choom/tui/app.py`, delete `month_cache`, `month_warnings`, `unfiled_cache`,
      `unfiled_warnings`, `fully_loaded`, `tasks`, `task_warnings`, `_ensure_month_loaded` and
      `_ensure_unfiled_loaded`, plus their initialisation in `__init__` and `on_mount`.
- [X] T012 [US1] In `src/choom/tui/app.py`, delete `reload_tasks`, `refresh_document` and
      `_refresh_document_in`, plus the `refresh_document` call inside `toggle_task_and_track`.
- [X] T013 [US1] In `src/choom/tui/app.py`, stop the three writers patching state: `_track_created` keeps
      setting active collection, clearing the filter and selecting the month but no longer inserts into any
      cache; `add_task_and_track` no longer appends to `self.tasks`; `toggle_task_and_track` reads the
      task's current state via `choom.core.tasks.get_task` instead of scanning `self.tasks`.
- [X] T014 [US1] In `src/choom/tui/edit_screen.py`, delete the four refresh call sites at lines 104, 159,
      166, 321 and 412 (`app.refresh_document`, `app.reload_tasks` ×4). Freshness now comes from
      `ListScreen.on_screen_resume`, which already re-reads.
- [X] T015 [US1] In `src/choom/tui/list_screen.py`, change `_on_selected` (line ~451) to construct
      `PreviewScreen(document.path, _read_document(document.path))`, matching `action_open_preview` at line
      442 so both entry paths read from disk (research R7, FR-003).
- [X] T016 [US1] In `src/choom/tui/list_screen.py`, have `refresh_rows` keep the warning count from its own
      read on the screen and have `_render_status` read that field instead of calling
      `app.visible_warnings()`. `_render_status` fires on every command-bar keystroke via `ModeChanged`, so
      leaving it calling a scanning method would scan once per character (research R3).
- [X] T017 [US1] Verify no change is needed in `ListScreen.action_toggle_task` (line 305) or
      `on_screen_resume` (line 141): both already call `refresh_rows`, which now reads from disk. If either
      needed editing, the read is in the wrong place — revisit T009/T010 rather than adding a call here.
- [X] T018 [US1] Run `uv run pytest -q` and confirm the whole suite is green, including the six existing
      tests that call `visible_documents()` directly and `tests/integration/test_month_scope.py::test_opening_collection_reads_only_current_month`,
      which must still pass unchanged (contract C3).

**Checkpoint**: Issue #51 is fixed and the feature is releasable. US2 and US3 are refinements of *when* the
read happens, not whether it happens.

---

## Phase 4: User Story 2 - An open view keeps up on its own (Priority: P2)

**Goal**: A displayed list re-reads every 2 seconds and re-renders only when a rendered field changed.

**Independent Test**: Park the app on Tasks, complete a task without going through the app, touch nothing,
and confirm the row flips to done within about two seconds; then leave an unchanged workspace idle and
confirm nothing flickers, scrolls, or loses selection.

**Depends on**: US1 (the cache must be gone before a timer that re-reads is coherent).

### Tests for User Story 2

> None of these may sleep or wait for a real tick — invoke the callback directly (research R9,
> Principle VI).

- [X] T019 [P] [US2] Unit test in `tests/unit/test_refresh_key.py` for the change-detection key: identical
      reads produce equal keys; a changed title, type, tag, `updated`, or task `done` state produces a
      different one; reordering without content change is still detected as a change because order is
      rendered.
- [X] T020 [P] [US2] Integration test in `tests/integration/test_refresh_timer_tui.py`: invoking the tick
      against an unchanged workspace performs no rebuild and leaves selection and scroll intact, across
      repeated invocations (FR-010, SC-006).
- [X] T021 [P] [US2] Integration test in `tests/integration/test_refresh_timer_tui.py`: invoking the tick
      after an out-of-process change updates the list, keeps the same record selected when the list
      re-sorts above it, and lands selection on a neighbour when the selected record is gone (FR-009,
      FR-011, US2 scenarios 3 and 4).
- [X] T022 [P] [US2] Integration test in `tests/integration/test_refresh_timer_tui.py`: the tick returns
      without reading or rendering when the command bar is open and when a filter is active (FR-012,
      FR-013, contract C4).
- [X] T023 [P] [US2] Integration test in `tests/integration/test_refresh_timer_tui.py`: the interval is
      registered at `REFRESH_SECONDS`, and the timer is paused while a preview or editor is on top and
      resumed on return. Assert on the `Timer` object's state — do not wait for a tick.
- [X] T024 [P] [US2] Performance test in `tests/performance/test_refresh_tick.py`: the read a tick performs
      on a representative month stays inside one 60 fps frame (~15 ms), with a comment recording the
      measured 0.14 ms/document and that breaching this is the stated trigger to move the read to a worker
      thread (research R5).

### Implementation for User Story 2

- [X] T025 [US2] In `src/choom/tui/list_screen.py`, add `REFRESH_SECONDS = 2.0` as a module constant with a
      comment pointing at research R5 for why it is 2 s and not the issue's 10 s.
- [X] T026 [US2] In `src/choom/tui/list_screen.py`, build the change-detection key from a read result:
      `(id, path, title, type, tags, created, updated)` per document row and
      `(id, text, type, tags, done, created)` per task row. Store the key produced by each `refresh_rows`.
- [X] T027 [US2] In `src/choom/tui/list_screen.py`, implement the tick as **two methods** — one that
      performs the read and returns the rows plus their key, one that applies a result to the screen. This
      is what makes moving the read to a worker thread later a change of caller rather than a rewrite of
      T020–T023 (research R5).
- [X] T028 [US2] In `src/choom/tui/list_screen.py`, wire the tick: return early if the command bar is open
      or a filter is active; otherwise read, compare the key, and apply only on difference, calling
      `refresh_rows(select_id=…)` so selection survives by record id (FR-011).
- [X] T029 [US2] In `src/choom/tui/list_screen.py`, register the interval in `on_mount` via
      `self.set_interval(REFRESH_SECONDS, …)`, and pause/resume it on `ScreenSuspend` / `ScreenResume` so no
      tick fires while a preview, editor, help screen or dialog is on top (FR-012, research R5).

**Checkpoint**: US1 and US2 both work; an open list keeps up without input, and a quiet workspace is
visually still.

---

## Phase 5: User Story 3 - Filtering stays instant (Priority: P3)

**Goal**: The collection read that filtering needs starts when the command bar opens, on a worker thread,
and is held for the whole bar session.

**Independent Test**: On a 1,000-document workspace, press `/` and confirm the keypress does not stall, then
type a filter term and confirm matches appear across months.

**Depends on**: US1. Independent of US2.

### Tests for User Story 3

- [X] T030 [P] [US3] Integration test in `tests/integration/test_filter_hydration_tui.py`: typing a
      non-filter verb, backspacing it away, then typing a filter term still matches immediately — the read
      started at open is not cancelled mid-session (FR-018, US3 scenario 3).
- [X] T031 [P] [US3] Integration test in `tests/integration/test_filter_hydration_tui.py`: closing the bar
      without ever typing a filter leaves the view unchanged, and clearing an applied filter restores the
      pre-filter month scope with current on-disk content (US3 scenarios 4 and 5, FR-019).
- [X] T032 [US3] Update `tests/integration/test_month_scope.py::test_filter_reads_each_month_at_most_once_per_session`
      to assert per **command-bar session** rather than per app session: a second filter term within one bar
      opening reads no additional files; a new bar opening reads again. Rename the test and update its
      docstring, which currently cites spec 005 FR-035 (research R10).
- [X] T033 [P] [US3] Performance test in `tests/performance/test_filter_hydration.py`: on a 1,000-document
      workspace the `/` keypress returns before hydration completes, and the first filter term resolves
      within 500 ms (FR-016, SC-004).

### Implementation for User Story 3

- [X] T034 [US3] In `src/choom/tui/list_screen.py`, add a `@work(thread=True, exclusive=True, group="filter-hydrate")`
      method that reads every month plus unfiled for the active collection, and start it from
      `action_open_command_bar` (line 280) — **not** from the `CommandBar.ModeChanged` handler, which fires
      on every keystroke (research R6, contract C5).
- [X] T035 [US3] In `src/choom/tui/list_screen.py`, have `_on_filter_changed` (line 460, already `async`)
      `await` the worker before matching, so the first term matches the whole collection rather than a
      partial set (FR-017).
- [X] T036 [US3] In `src/choom/tui/list_screen.py`, drop the worker handle in `_on_command_bar_closed`
      (line 527) so the snapshot's lifetime is exactly one bar session (FR-019).
- [X] T037 [US3] Delete the unread `filter_loading` flag at `src/choom/tui/app.py:83`. `Worker.wait()`
      handles the wait; nothing reads the flag (research R6).

**Checkpoint**: All three stories functional and independently verifiable.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T038 Confirm the deletion is complete: `grep -rn "month_cache\|unfiled_cache\|fully_loaded\|reload_tasks\|refresh_document\|filter_loading" src/`
      returns nothing. The baseline count was 38 sites in `src/` (SC-008).
- [X] T039 [P] Run `uv run ruff format --check .`, `uv run ruff check .` and `uv run mypy src tests`; fix
      anything the deletions left behind (unused imports of `ScanWarning`, `_read_document`, `Path` in
      `src/choom/tui/app.py` are likely).
- [X] T040 [P] Verify cross-platform path handling is untouched by running
      `tests/integration/test_unicode_paths.py`; reading more often must not change how paths are built.
- [X] T041 Walk [quickstart.md](./quickstart.md) end to end against a scratch workspace, including the
      two-terminal reproduction from issue #51.
- [X] T042 Verify the TUI by hand on the target terminals listed in `docs/REQUIREMENTS.md`, watching
      specifically for flicker or scroll disturbance from the 2-second tick.
- [X] T043 Review whether any user-facing documentation claims the TUI shows a snapshot; update `README.md`
      only if it does. No `AGENTS.md` change is expected — the workspace guidance never described caching.
- [X] T044 Run the full suite once more and confirm CI is green on the PR before requesting review
      (repository CLAUDE.md).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: T002 blocks T003–T005, T020–T023 and T030–T031.
- **US1 (Phase 3)**: blocks US2 and US3. This is a real dependency, not a convention — a refresh timer over
  a cache would refresh the cache, and hydrating a filter set is meaningless while every month is already
  held in memory.
- **US2 (Phase 4)** and **US3 (Phase 5)**: independent of each other; either may follow US1.
- **Polish (Phase 6)**: after whichever stories are being shipped.

### Within User Story 1

T003–T008 (tests) → T009–T010 (make the reads real) → T011–T014 (delete what they replace) → T015–T016
(screen-side reads) → T017 (verify no further wiring) → T018 (suite green).

T011 must not land before T009/T010: deleting the dictionaries while `visible_documents` still reads them
breaks every TUI test at once and makes bisecting the failures pointless.

### Within User Story 2

T019–T024 (tests) → T025–T026 (constant and key) → T027 (read/apply split) → T028 (tick logic) → T029
(interval and lifecycle). T027 before T028 so the split is the shape the tick is written in, not a later
refactor.

### Within User Story 3

T030–T033 (tests) → T034 (worker) → T035 (await) → T036 (drop) → T037 (flag deletion).

### Parallel Opportunities

- T003, T004, T005 target the same new file — write them together in one pass, but they are not independent
  edits; T008 is genuinely `[P]` against them.
- T019–T024 touch four different files and are fully parallel.
- T030, T031, T033 are parallel; T032 edits an existing file.
- T039 and T040 are parallel.
- US2 and US3 can be worked simultaneously by two people once US1 has landed — they share only
  `list_screen.py`, so coordinate on that file or sequence them.

---

## Parallel Example: User Story 2

```bash
# All six US2 test tasks touch different files and can be written together:
Task: "Unit test for the change-detection key in tests/unit/test_refresh_key.py"          # T019
Task: "Tick with no change performs no rebuild, tests/integration/test_refresh_timer_tui.py"  # T020
Task: "Tick after an external change preserves selection, same file"                       # T021
Task: "Tick guards for command bar and filter, same file"                                  # T022
Task: "Interval registration and pause/resume, same file"                                  # T023
Task: "Scan cost within one frame in tests/performance/test_refresh_tick.py"               # T024
```

---

## Implementation Strategy

### MVP: User Story 1 only

1. Phase 1 (T001) and Phase 2 (T002).
2. Phase 3 (T003–T018).
3. **STOP and validate**: run the issue #51 reproduction from
   [quickstart.md](./quickstart.md) §1. Two meetings where there were two; the completed task reads done.
4. This is shippable. The bug is fixed, 38 sites of machinery are gone, and no writer has to announce
   itself any more.

### Incremental delivery

- **+ US2** turns "visible when you navigate" into "visible on its own within about two seconds", which is
  what makes the shared-workspace story feel live rather than merely correct.
- **+ US3** protects filter responsiveness at 1,000 documents. Below a few hundred documents the difference
  is not perceptible, so this is the slice to drop if the feature needs to be cut short — with the caveat
  that dropping it leaves a 144 ms read on the first filter keystroke at the top of the range.

### Risk notes

- The single largest risk is T011 landing early or partially — see the ordering note above.
- T024's ceiling is the trigger for the deferred worker-thread decision (research R5). If it fails on a
  realistic month rather than a synthetic one, that decision reopens; it does not block the story.
- No task in this feature touches `choom.core`, the CLI, `--json` output, or exit codes. A diff that does
  has strayed outside the plan.
