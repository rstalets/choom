---

description: "Task list for 014-inline-editor-pane"
---

# Tasks: Editor Replaces the Preview Pane

**Input**: Design documents from `/specs/014-inline-editor-pane/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/tui.md](./contracts/tui.md)

**Tests**: Included. The constitution's Development Workflow requires behaviour changes to land with the
tests that cover them, and Principle VI requires that coverage be risk-based rather than one test per
acceptance scenario. Test tasks below are chosen for what can actually break — see each phase's note.

**Organization**: Tasks are grouped by user story. The shared refactor that all four stories sit on is
Phase 2; it is genuinely blocking, because until the editor is a widget there is nothing to mount in a
pane.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)

## Path Conventions

Single project: `src/choom/` and `tests/` at the repository root.

---

## Phase 1: Setup

**Purpose**: Establish the baseline this change is measured against. No project initialization is needed
— the repository, dependencies, and tooling already exist.

- [X] T001 Run `uv run pytest` and record the passing baseline, so any later failure is attributable to
      this feature rather than inherited; note the count in the PR description
- [X] T002 [P] Confirm the editor's current presentation contract still holds by running
      `uv run pytest tests/integration/test_edit_presentation.py tests/integration/test_edit_from_list_tui.py`
      — these two files are the regression net for everything Phase 2 moves

**Checkpoint**: A known-green starting point.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Turn the editor from a screen into a widget, without changing a single user-visible
behaviour. Nothing renders inline yet.

**⚠️ CRITICAL**: No user story can begin until this phase is complete and the suite is green again.

- [X] T003 Extract an `EditorPane(Vertical)` widget in `src/choom/tui/edit_screen.py` holding the
      `EditorTextArea` and every field listed in `data-model.md` (`target`, `original_text`, `_request`,
      `_breadcrumb`, `_mirror_baseline`, `_cursor_row`), plus the `is_dirty` property
- [X] T004 Move `EditScreen`'s `BINDINGS` (`ctrl+o`, `ctrl+s`, `ctrl+x`, `escape`, `ctrl+c`) and its
      `check_action` gate onto `EditorPane` in `src/choom/tui/edit_screen.py`, keeping `priority=True`
      on the four that carry it (research R3)
- [X] T005 Move `_save`, `action_save`, `action_save_and_close`, `action_close`, `action_cancel_request`,
      `_render_status`, `_render_in_flight_status`, and `on_resize` onto `EditorPane` in
      `src/choom/tui/edit_screen.py`; status lookups become `self.screen.query_one(StatusBar)` so the
      pane writes to whichever host's bar is present (research R4)
- [X] T006 Move the in-editor command handlers (`_on_editor_command_submitted`, `_capture_task`,
      `_insert_link`, `_start_ai_request`, `_run_assistant`, `_finish_request`) onto `EditorPane` in
      `src/choom/tui/edit_screen.py` unchanged (research R7)
- [X] T007 Add an `EditorPane.Closed` message in `src/choom/tui/edit_screen.py`, posted where
      `action_close` and `action_save_and_close` previously called `app.pop_screen()`, so the pane never
      decides how it disappears (research R1)
- [X] T008 Reduce `EditScreen` in `src/choom/tui/edit_screen.py` to a host: compose `EditorPane` plus its
      own `StatusBar`, handle `EditorPane.Closed` by popping itself, and expose the pane for callers that
      need it
- [X] T009 Add `open_editors(app) -> list[EditorPane]` in `src/choom/tui/edit_screen.py`, iterating
      `app.screen_stack` and querying each screen for mounted panes (research R9)
- [X] T010 Replace the `isinstance(screen, EditScreen)` dirty scan in `ChoomApp.action_quit` in
      `src/choom/tui/app.py` with `open_editors(...)`, so `ctrl+q` finds an inline editor (bug #64 must
      not reopen in a new shape)
- [X] T011 Replace the `isinstance(screen, EditScreen)` scan in `ChoomApp.toggle_task_and_track` in
      `src/choom/tui/app.py` with `open_editors(...)`, so a toggle still skips documents whose editor is
      open and dirty
- [X] T012 [P] Add `EditorPane` sizing to `src/choom/tui/app.tcss` so it fills its host in both
      presentations (`height: 1fr; width: 1fr`), leaving the existing `#editor` rule intact
- [X] T013 Update `open_edit` in `tests/helpers.py` to assert an editor is open (an `EditorPane` is
      mounted) rather than that `app.screen` is an `EditScreen`, and return the pane (research R10)
- [X] T014 Run `uv run pytest` and fix fallout until green. Behaviour must be **identical** to T001's
      baseline at this point — if a test needed a behavioural change to pass here, the extraction leaked
      something and that is the bug to fix

**Checkpoint**: The editor is a widget hosted by a screen, and the tool behaves exactly as it did before.

---

## Phase 3: User Story 1 - Edit a note without losing your place (Priority: P1) 🎯 MVP

**Goal**: `e` on a highlighted document opens the editor in `#preview-pane` with the list still beside
it, and closing returns to the same highlighted row.

**Independent Test**: Highlight a record, press `e`, confirm the list and scope pane are still mounted
and visible while the editor occupies the preview pane; type, save, confirm the same row is highlighted
with the new content in the preview.

### Implementation for User Story 1

- [X] T015 [US1] Add `_editor_pane: EditorPane | None` to `ListScreen.__init__` in
      `src/choom/tui/list_screen.py` — the single field every guard in this story tests
- [X] T016 [US1] Add `ListScreen.open_inline_editor(target)` in `src/choom/tui/list_screen.py`: hide
      `#preview` and `#preview-links-section`, mount an `EditorPane` in `#preview-pane`, focus `#editor`,
      and leave the collection bar, scope pane, and list pane untouched (FR-001, FR-003)
- [X] T017 [US1] Route by active screen in `open_editor` and `open_task_editor` in
      `src/choom/tui/edit_screen.py`: when the active screen is `ListScreen`, call its
      `open_inline_editor`; otherwise push `EditScreen` as today (FR-002, contract C1)
- [X] T018 [US1] Swap the status bar to `EDIT_HELP` on open in `src/choom/tui/list_screen.py`, and
      restore `_render_status()` on close, so the footer never concatenates the two (FR-009, contract C4)
- [X] T019 [US1] Handle `EditorPane.Closed` in `ListScreen` in `src/choom/tui/list_screen.py`: unmount
      the pane, clear `_editor_pane`, unhide `#preview`, refresh the list once with the edited record
      selected, restore the status bar, and focus `#meeting-list` (FR-011, FR-013, contract C5)
- [X] T020 [US1] Block the command bar while the pane is mounted in
      `ListScreen.action_open_command_bar` in `src/choom/tui/list_screen.py` (FR-008)
- [X] T021 [US1] Widen `ListScreen.check_action` in `src/choom/tui/list_screen.py` to return `False` for
      every list action while `_editor_pane` is set (FR-007, research R2)
- [X] T022 [US1] Bind `tab` and `shift+tab` to a no-op on `EditorPane` in
      `src/choom/tui/edit_screen.py` — the only keys `TextArea` lets through to the host (research R2)
- [X] T023 [US1] Freeze the list while the pane is mounted in `src/choom/tui/list_screen.py`: pause
      `_refresh_timer` on open and resume on close, and return early from `_refresh_tick`,
      `_update_preview`, and `on_screen_resume` while `_editor_pane` is set (FR-021, research R6)
- [X] T024 [US1] Refocus `#editor` rather than the list when a `ConfirmDialog` is declined over an open
      inline editor, in `src/choom/tui/edit_screen.py` and `src/choom/tui/list_screen.py` (FR-014,
      research R5)

### Tests for User Story 1

> Risk-based (Principle VI): these four cover the failure modes the design actually has — a key reaching
> the list, `ctrl+x` losing to `TextArea`'s cut, a refresh touching the buffer, and focus escaping the
> editor. They are not one test per acceptance scenario.

- [X] T025 [P] [US1] Integration test in `tests/integration/test_inline_editor_tui.py`: pressing `e` on a
      highlighted document mounts the editor in `#preview-pane`, `#meeting-list` and `#scope-pane` are
      still displayed, `#preview` is hidden, and the status bar reads `EDIT_HELP`
- [X] T026 [P] [US1] Integration test in `tests/integration/test_inline_editor_tui.py`: typing `j`, `k`,
      `e`, `b`, `space`, and `/` inserts those characters, the highlighted index does not change, the
      command bar stays closed, and `ctrl+d` deletes a character rather than a record
- [X] T027 [P] [US1] Integration test in `tests/integration/test_inline_editor_tui.py`: `ctrl+x` writes
      the file and closes the pane (the priority-binding risk of research R3), `#preview` shows the saved
      content, the same row is highlighted, and focus is back on `#meeting-list`
- [X] T028 [P] [US1] Integration test in `tests/integration/test_inline_editor_tui.py`: `tab` and
      `shift+tab` leave focus on `#editor` and do not change the active collection
- [X] T029 [P] [US1] Integration test in `tests/integration/test_inline_editor_tui.py`: with the pane
      open, a record created on disk out of process does not change the list, the buffer, or the cursor;
      after close, the list shows it (FR-021, FR-022)
- [X] T030 [US1] Update `tests/integration/test_edit_from_list_tui.py` for the inline path — the list
      screen is never left, and the assertions become "an editor is open" rather than "a screen was
      pushed"
- [X] T031 [P] [US1] Update `tests/integration/test_discard_tui.py`: the confirmation is raised over the
      list screen, declining returns to a still-mounted editor with the buffer intact, confirming
      unmounts it and leaves the file unchanged
- [X] T032 [P] [US1] Update `tests/integration/test_ctrl_q_confirm.py` to cover a dirty **inline** editor
      raising the same confirmation (T010's path)
- [X] T033 [P] [US1] Update `tests/unit/test_footer_bindings.py` for the footer text shown while an
      inline editor is open

**Checkpoint**: US1 is the MVP — quick edits from the list no longer leave the list.

---

## Phase 4: User Story 2 - Update a task's details in place (Priority: P2)

**Goal**: `e` on a highlighted task edits its details in the pane, with the task list still visible.

**Independent Test**: Open Tasks, highlight a task, press `e`, type a line, save, and confirm the task
list stayed visible and the same task is highlighted with its new details in the preview.

**Depends on**: Phase 3 (the mounting path is shared; task editing differs only in its `EditTarget`).

- [X] T034 [US2] Confirm `ListScreen.action_edit`'s task branch in `src/choom/tui/list_screen.py` reaches
      `open_task_editor` and therefore the inline route from T017, with no separate branch of its own
- [X] T035 [US2] Integration test in `tests/integration/test_inline_editor_tui.py`: `e` on a highlighted
      task opens the editor inline on that task's body, saving writes the details, and the same task is
      highlighted with the updated details in the preview
- [X] T036 [P] [US2] Update `tests/integration/test_task_body_tui.py` for the inline path, keeping every
      existing assertion about what is written to `tasks.md`

**Checkpoint**: Both editing entry points from the list are inline.

---

## Phase 5: User Story 3 - Full-screen reading keeps its full-screen editor (Priority: P3)

**Goal**: `enter` still opens the full-screen reading view, and `e` inside it still opens a full-screen
editor.

**Independent Test**: Press `enter` on a record, press `e`, confirm the editor is full-screen, save and
confirm the return lands on the reading view.

**Depends on**: Phase 2 only. This story is a regression guard and can be verified as soon as the
routing exists; it does not need US1's mounting path.

- [X] T037 [P] [US3] Integration test in `tests/integration/test_inline_editor_tui.py`: `e` inside
      `PreviewScreen` pushes a full-screen `EditScreen`, and save-and-close returns to `PreviewScreen`
      (FR-018, contract C1's last row)
- [X] T038 [P] [US3] Confirm `tests/integration/test_edit_presentation.py` passes unchanged in substance
      — it is the full-screen editor's contract and this feature must not move it (research R10)

**Checkpoint**: The scope boundary is enforced by a test, not by intention.

---

## Phase 6: User Story 4 - Creating a record keeps the list in view (Priority: P4)

**Goal**: Creating a note, meeting, or daily note from the list opens its editor in the pane, with the
new record already highlighted in the list.

**Independent Test**: Create a note from the list, confirm the editor is in the pane, the list is
visible, and the new record is the highlighted row while the editor is open.

**Depends on**: Phase 3.

- [X] T039 [US4] In `ListScreen._on_create_requested` in `src/choom/tui/list_screen.py`, refresh the
      scope pane and rows selecting the new record **before** opening the editor, so the pane and the
      list agree about what is being edited (FR-016, research R8)
- [X] T040 [US4] Apply the same ordering in `ListScreen._on_daily_requested` in
      `src/choom/tui/list_screen.py`
- [X] T041 [P] [US4] Update `tests/integration/test_create_opens_editor_tui.py`: the editor opens inline
      and the new record is the highlighted row while it is open
- [X] T042 [P] [US4] Update `tests/integration/test_daily_note_tui.py` for the same behaviour
- [X] T043 [P] [US4] Integration test in `tests/integration/test_inline_editor_tui.py`: following a link
      that resolves to a task opens the editor inline from the list screen (FR-002's last route)

**Checkpoint**: Every route into edit mode from the list screen renders in the pane.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T044 [P] Integration test in `tests/integration/test_narrow_terminal_tui.py`: at 40 columns the
      inline editor mounts, `soft_wrap` is on, and no line requires horizontal scrolling (FR-004,
      research R11)
- [X] T045 [P] Integration test in `tests/integration/test_inline_editor_tui.py`: resizing the terminal
      with an open inline editor preserves the buffer exactly and leaves the cursor on the same
      character (FR-005)
- [X] T046 [P] Update `README.md` only if it describes where the editor appears; per `CLAUDE.md` the
      README documents shipped releases, so an unreleased change does not belong there — check and skip
      deliberately rather than by omission
- [X] T047 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src` and fix
      anything the move introduced
- [X] T048 Run the full suite `uv run pytest` and compare against T001's baseline
- [X] T049 Walk `specs/014-inline-editor-pane/quickstart.md` steps 1–10 by hand in a real terminal,
      including the resize and the out-of-process create
- [ ] T050 Verify the TUI on the target terminals listed in `docs/REQUIREMENTS.md` before release

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies
- **Phase 2 (Foundational)**: depends on Phase 1 — **blocks every user story**
- **Phase 3 (US1)**: depends on Phase 2
- **Phase 4 (US2)**: depends on Phase 3 (shares the mounting path)
- **Phase 5 (US3)**: depends on Phase 2 only — can run alongside Phase 3
- **Phase 6 (US4)**: depends on Phase 3
- **Phase 7 (Polish)**: depends on Phases 3–6

### Within Phase 2

T003 → T004 → T005 → T006 → T007 → T008 are one sequence in one file and must be done in order. T009
follows T008. T010 and T011 both depend on T009 and touch the same file, so they are sequential with
each other. T012 (`app.tcss`) is independent. T013 depends on T003. T014 is the gate on the whole phase.

### Within Phase 3

T015 → T016 → T017 → T018 → T019 in order (all `list_screen.py` / `edit_screen.py`, and each builds on
the last). T020–T024 follow T019 and touch the same two files, so they are sequential. T025–T033 are the
tests: T025–T029 are new and independent of each other; T030–T033 are edits to four different existing
files and can run in parallel.

### Parallel Opportunities

- Phase 2: T012 alongside the T003→T008 sequence
- Phase 3: T025, T026, T027, T028, T029 in parallel once T024 lands; T031, T032, T033 in parallel
- Phase 5: T037 and T038 in parallel, and the whole phase alongside Phase 3
- Phase 6: T041, T042, T043 in parallel
- Phase 7: T044, T045, T046 in parallel

---

## Parallel Example: User Story 1 tests

```bash
# Once T024 lands, these five are independent of one another:
Task: "T025 mounting and status bar in tests/integration/test_inline_editor_tui.py"
Task: "T026 key isolation in tests/integration/test_inline_editor_tui.py"
Task: "T027 ctrl+x save-and-close in tests/integration/test_inline_editor_tui.py"
Task: "T028 tab does not move focus in tests/integration/test_inline_editor_tui.py"
Task: "T029 refresh does not disturb the buffer in tests/integration/test_inline_editor_tui.py"

# And these three touch three different existing files:
Task: "T031 tests/integration/test_discard_tui.py"
Task: "T032 tests/integration/test_ctrl_q_confirm.py"
Task: "T033 tests/unit/test_footer_bindings.py"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 — baseline green
2. Phase 2 — the extraction, with behaviour identical to the baseline (**the gate that matters**)
3. Phase 3 — US1 inline document editing
4. **STOP and VALIDATE**: quickstart steps 1–3

### Incremental Delivery

Phase 2 → Phase 3 (MVP) → Phase 5 (cheap regression guard) → Phase 4 → Phase 6 → Phase 7. Each of Phases
3–6 leaves the tool shippable.

### Risk Notes

- **The one to watch is T014.** If the suite needs behavioural edits to pass after the extraction,
  something leaked; fix the leak rather than the test.
- **T027 is the canary for research R3.** If a widget's `priority=True` binding does not beat
  `TextArea`'s `ctrl+x` cut, that test fails and the fallback in research R3 applies — move the four
  priority bindings to the host screens and delegate to the mounted pane.
- **T023 is where data loss would hide.** A refresh that reaches `_update_preview` while the pane is
  mounted would overwrite the editor mid-edit; three guards exist because three paths reach a render.
