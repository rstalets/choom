---

description: "Task list for 004-viewing-editing"
---

# Tasks: Viewing and Editing (REQUIREMENTS.md §3.5) and the `CLAUDE.md` fix (§4.3)

**Input**: Design documents from `/specs/004-viewing-editing/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle VI requires every acceptance criterion in a spec to map
to at least one test, so test tasks are not optional for this project.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and
demonstrated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, `src/` layout: `src/endpaper/`, `tests/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the baseline this feature is measured against

- [ ] T001 Run `uv sync --extra dev && uv run pytest` and confirm the baseline is **154 passing** — this is the count the Phase 2 regression gate (T013) and the final gate (T052) compare against, and it must be green before any code changes
- [ ] T002 [P] Bump `__version__` to `0.0.3` in `src/endpaper/__init__.py`
- [ ] T003 [P] Add an Unreleased `0.0.3` section to `CHANGELOG.md` with placeholders for the three new edit-state bindings, `CLAUDE.md` at init, and the **BREAKING** `init_workspace` return-type change (Principle VI requires public API changes to be recorded with their version)
- [ ] T004 [P] Add to `tests/conftest.py`: a `write_raw(path, text, *, newline)` helper that writes bytes with newline translation off (`open(..., newline="")`) so line-ending tests can assert byte equality, and a `sample_document(tmp_workspace)` fixture returning the `Path` of one created meeting

**Checkpoint**: Baseline green and recorded; byte-exact fixtures available.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The save path — where this feature's correctness lives

**⚠️ CRITICAL**: US1, US2, and US3 cannot begin until this phase is complete. **US4 depends only on
T005** and can otherwise proceed in parallel with this entire phase.

**⚠️ This phase adds no user-visible behaviour.** Every FR-016 through FR-023 guarantee is decided
here, as string-in/data-out functions that need neither a filesystem nor a terminal. Nothing in this
phase may import from `endpaper.tui` — the existing import-walk test (`tests/unit/test_core_imports.py`)
enforces it with no edit.

**⚠️ Do not reach for `render_frontmatter()`.** It rebuilds all six fields in a fixed order with JSON
quoting; putting it on the save path breaks FR-016 outright. See [R1](./research.md#r1-the-updated-stamp-is-surgical-not-a-re-render).

- [ ] T005 Add the frozen slotted `EditableFile` (`path`, `text`, `newline`, `trailing_newline`), `SaveResult` (`ok`, `saved_text`, `stamped`, `message`), and `InitResult` (`workspace`, `written`, `skipped`) dataclasses to `src/endpaper/core/models.py` per [data-model.md](./data-model.md#entities)
- [ ] T006 Create `src/endpaper/core/editing.py` and implement `stamp_updated(text: str, timestamp: str) -> tuple[str, bool]` per the full matching table in [data-model.md](./data-model.md#stamp_updated--the-matching-rules): locate the block exactly as `_parse_document` does (`---\n` prefix, first `\n---` from index 3), replace only the value on the block's **first** `^updated:` line, preserve that line's own ending, and return `(text, False)` — never raise — when the block or the line cannot be found
- [ ] T007 In `src/endpaper/core/editing.py`, implement `load_for_edit(path) -> EditableFile`: read with `open(..., newline="", errors="replace")` so Python performs no translation, record `newline` from the **first** line ending present (`"\n"` when the file has none), record `trailing_newline`, and return `text` normalised to `"\n"` per [R2](./research.md#r2-line-endings-and-the-trailing-newline)
- [ ] T008 In `src/endpaper/core/editing.py`, implement `save_buffer(path, text, file, *, now=None) -> SaveResult` in the fixed pipeline order from [data-model.md](./data-model.md#the-save-pipeline): stamp → denormalise `"\n"` to `file.newline` and restore `file.trailing_newline` → write a `NamedTemporaryFile` **in `path.parent`** with `newline=""` → `os.replace`. Catch `OSError` (including Windows sharing violations on synced files), unlink the temp, and return `SaveResult(ok=False, message=...)` rather than raising. Assert `path == file.path`
- [ ] T009 Export `EditableFile`, `SaveResult`, `InitResult`, `load_for_edit`, `save_buffer`, and `stamp_updated` from `src/endpaper/core/__init__.py`
- [ ] T010 [P] Create `tests/unit/test_stamp_updated.py` covering every row of the matching table: normal block, `created` untouched, user-added seventh field preserved, hand-reordered fields, single-quoted values, no frontmatter, unterminated block, block with no `updated:` line, two `updated:` lines (first only), `updated:` in the body below the block (untouched), and `""`. The sharpest assertion: **diff before and after and confirm exactly one line changed**
- [ ] T011 [P] Create `tests/unit/test_line_endings.py`: round-trip CRLF and LF files, each with and without a trailing newline, through `load_for_edit` → `save_buffer` with text unchanged, asserting the bytes on disk are identical apart from the `updated:` line. Include the documented mixed-endings normalisation case
- [ ] T012 [P] Create `tests/unit/test_save_atomic.py`: monkeypatch `os.replace` to raise `OSError`, assert the target is byte-identical, no temp file is left in the directory, and `SaveResult.ok is False` with a non-empty `message` (FR-020)
- [ ] T013 **Regression gate**: run `uv run pytest` and confirm the T001 count of 154 still passes alongside the new unit tests, with **zero existing test files edited**. Do not proceed to Phase 3 until this holds

**Checkpoint**: The save path is correct and proven without a terminal. Interface work can begin.

---

## Phase 3: User Story 1 - Fix what you are reading, without leaving (Priority: P1) 🎯 MVP

**Goal**: One keystroke turns the page being read into a page that can be typed into; one more puts
it on disk.

**Independent Test**: Open any existing meeting or note from the list, press `e`, type, save, and
confirm the file on disk matches the buffer and the preview shows the new content.

### Tests for User Story 1

- [ ] T014 [P] [US1] Create `tests/integration/test_edit_save_tui.py` covering US1 scenarios 1–7 headless via `App.run_test()` / `Pilot`, matching the pattern in `tests/integration/test_list_tui.py`: `e` opens the raw markdown **including frontmatter**; `ctrl+o` writes and preserves cursor position; `ctrl+s` is indistinguishable from `ctrl+o`; `ctrl+x` saves and lands in preview showing the new content; a title change appears in the list row on return with no other row moved; `updated` advances while `created` does not; and `esc` from preview without editing leaves both bytes **and mtime** untouched

### Implementation for User Story 1

- [ ] T015 [US1] Create `src/endpaper/tui/edit_screen.py` with `EditScreen(Screen[None])`, composing `TextArea(file.text, show_line_numbers=True, id="editor")` plus the bottom bar. Store `original_text` and expose `is_dirty` as the derived comparison `text_area.text != original_text` — **never a flag** ([R3](./research.md#r3-dirty-state-is-a-comparison-not-a-flag))
- [ ] T016 [US1] Add `BINDINGS` and actions to `src/endpaper/tui/edit_screen.py`: `ctrl+o` → `save` (stay), `ctrl+s` → `save` with `show=False` (alias, because it is XOFF), `ctrl+x` → `save_and_close`. On a successful save, reset `original_text` to `SaveResult.saved_text` so the buffer does not immediately read as dirty
- [ ] T017 [US1] In `src/endpaper/tui/edit_screen.py`, render `SaveResult` outcomes into the status bar: `stamped=False` shows the frontmatter warning and still clears dirty state (FR-018); `ok=False` shows the error and **stays in the edit state with the buffer intact** — including for `ctrl+x`, which must not leave on a failed save (FR-020)
- [ ] T018 [US1] In `src/endpaper/tui/preview_screen.py`, add the `e` binding and an `action_edit` that calls `load_for_edit(self.path)` and pushes `EditScreen` (FR-003)
- [ ] T019 [US1] In `src/endpaper/tui/preview_screen.py`, add `on_screen_resume` that re-reads the file and re-renders, so returning from a save shows saved content (FR-007) — same pattern as `list_screen.py:92`
- [ ] T020 [US1] Add a `refresh_document(path)` method to `src/endpaper/tui/app.py` that re-parses **only** the changed file into the active collection's list, preserving list order (FR-021, FR-022). It must not rescan the workspace
- [ ] T021 [US1] Add `#editor` styles to `src/endpaper/tui/app.tcss` so the editing area fills the screen above the bottom bar and the gutter is not clipped

**Checkpoint**: A user can fix a typo without leaving endpaper. This is the MVP — stop and validate.

---

## Phase 4: User Story 2 - Back out without losing a keystroke (Priority: P2)

**Goal**: `esc` asks only when there is work to lose, and never when there is not.

**Independent Test**: Enter the edit state four ways — with changes, without changes, after a save,
and after cancelling — press `esc` in each, and confirm the prompt appears exactly when unsaved
changes exist and the file is untouched whenever the user discards.

### Tests for User Story 2

- [ ] T022 [P] [US2] Create `tests/integration/test_discard_tui.py` covering US2 scenarios 1–6: type then `esc` raises the dialog with nothing written; Cancel returns with buffer **and cursor** intact; Discard leaves the file byte-identical to before the edit state was entered; no changes means no dialog; **no dialog after a `ctrl+o` save**; and **no dialog after the user manually retypes the original text** — the last is the case an "edited" boolean gets wrong

### Implementation for User Story 2

- [ ] T023 [US2] Create `src/endpaper/tui/discard_dialog.py` with `DiscardDialog(ModalScreen[bool])`, offering Discard (`dismiss(True)`) and Cancel (`dismiss(False)`) per [R6](./research.md#r6-the-discard-prompt-is-a-modalscreenbool-with-a-callback)
- [ ] T024 [US2] Add the `esc` binding and `action_close` to `src/endpaper/tui/edit_screen.py`: when `is_dirty` is False, pop immediately and silently; otherwise `self.app.push_screen(DiscardDialog(), callback)` — **not** `push_screen_wait`, which raises `NoActiveWorker` outside a worker
- [ ] T025 [US2] In the callback in `src/endpaper/tui/edit_screen.py`, `True` pops to preview and `False` returns focus to the `TextArea`. Cancel requires no restoration work because the widget is never unmounted (FR-027)
- [ ] T026 [US2] Add `DiscardDialog` styles to `src/endpaper/tui/app.tcss` — centred dialog with the two buttons

**Checkpoint**: The edit state is safe to enter casually, which is what makes a one-keystroke
transition worth having.

---

## Phase 5: User Story 3 - A buffer that reads like prose (Priority: P3)

**Goal**: Long paragraphs wrap, the gutter says where you are, and every live key is on screen.

**Independent Test**: Open a document with frontmatter, a paragraph far wider than the pane, and a
hundred body lines; check the first gutter number, wrapped-row numbering, absence of horizontal
scrolling, and the footer contents.

### Tests for User Story 3

- [ ] T027 [P] [US3] Create `tests/integration/test_edit_presentation.py`: assert `editor.show_line_numbers is True`, `editor.soft_wrap is True`, and `editor.tab_behavior == "focus"`; that gutter line 1 is the opening `---` of the frontmatter; that a paragraph wider than the pane wraps with no horizontal scroll; and that pressing `tab` leaves `editor.text` unchanged (FR-010, FR-011, FR-012)
- [ ] T028 [P] [US3] Create `tests/unit/test_footer_bindings.py` asserting **mechanically** that every binding with `show=True` in each of `ListScreen`, `PreviewScreen`, and `EditScreen` appears in that state's help string, and that each help string names no key its screen does not bind (FR-030, FR-031)

### Implementation for User Story 3

- [ ] T029 [US3] In `src/endpaper/tui/status_bar.py`, add `EDIT_HELP = "ctrl+o save   ctrl+x save & back   esc discard   ctrl+q quit"` and prepend `e edit` to `PREVIEW_HELP`, lifting the restriction features 001 and 002 placed on the preview footer (FR-032)
- [ ] T030 [US3] Render `EDIT_HELP` in the `EditScreen` status bar in `src/endpaper/tui/edit_screen.py`, sharing the `⚠ {note}   {HELP}` warning slot `PreviewScreen` already uses
- [ ] T031 [US3] Review `src/endpaper/tui/edit_screen.py` and confirm `TextArea` is constructed with **exactly one** non-default option, `show_line_numbers=True`. `TextArea.code_editor()` must not appear anywhere — it disables soft wrap and makes `tab` insert a literal tab, two of the three things §4.5 forbids ([R5](./research.md#r5-textarea-configuration--one-option-not-the-convenience-constructor))

**Checkpoint**: The edit state is legible and advertises itself honestly.

---

## Phase 6: User Story 4 - An assistant finds the conventions without being told (Priority: P4)

**Goal**: `endpaper init` drops a `CLAUDE.md` pointing at `AGENTS.md`, and never destroys guidance
that was already there.

**Independent Test**: Initialize a workspace in an empty directory, then in one that already contains
a `CLAUDE.md`, and confirm the file is written in the first case, untouched in the second, and that
init reports what it did in both.

**⚠️ Independent of Phases 2–5.** This phase needs only T005 and shares no other file with the
editing work. One person can take it start to finish while another builds the edit state.

### Tests for User Story 4

- [ ] T032 [P] [US4] Create `tests/integration/test_init_guidance.py` covering US4 scenarios 1–3: `CLAUDE.md` created in an empty directory and naming `AGENTS.md`; a pre-existing `CLAUDE.md` byte-identical after init with exit 0; a pre-existing `AGENTS.md` byte-identical after init with exit 0 — **the third currently fails**, because `workspace.py:52` overwrites it (FR-049, FR-050, SC-012)
- [ ] T033 [P] [US4] Create `tests/contract/test_guidance_files.py` enforcing SC-013 mechanically: `CLAUDE.md` is ≤ 12 lines, contains the literal `AGENTS.md`, and contains **none** of `meetings/`, `notes/`, `tasks.md`, `frontmatter`, `endpaper meeting`, `endpaper note`, `endpaper task`. Any hit means a convention now has two places to drift. Also assert `AGENTS.md.tmpl` is still ≤ 60 lines

### Implementation for User Story 4

- [ ] T034 [P] [US4] Create `src/endpaper/core/templates/CLAUDE.md.tmpl` — at most 12 lines that state this directory is an endpaper workspace, tell the reader to read `AGENTS.md` before creating or changing anything, and say the one non-obvious thing: **create through the commands, modify the markdown directly**. It restates no layout, no schema, and no command syntax ([R9](./research.md#r9-what-goes-in-claudemd))
- [ ] T035 [US4] Rewrite the guidance-file writes in `src/endpaper/core/workspace.py` to use `os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)` for **both** `AGENTS.md` and `CLAUDE.md`, treating `FileExistsError` as "skipped" — the same primitive `create_document` already uses (`documents.py:75`), so the guarantee is enforced by the OS rather than a check-then-write race
- [ ] T036 [US4] Change `init_workspace(target)` in `src/endpaper/core/workspace.py` to return `InitResult(workspace, written, skipped)`. The existing `.endpaper`-exists `WorkspaceError` is unchanged
- [ ] T037 [US4] Update the **8 call sites across 6 files**, each a mechanical `.workspace` suffix except the first: `src/endpaper/cli/main.py:110`, `tests/conftest.py:16`, `tests/integration/test_unicode_paths.py:13,27`, `tests/integration/test_note_parity.py:47`, `tests/integration/test_create_parity.py:47`, `tests/fixtures/generate.py:18,37`
- [ ] T038 [US4] In `src/endpaper/cli/main.py`, print a notice to **stderr** naming each skipped guidance file and what to add to it, keeping the workspace path on **stdout** and the exit code **0** (FR-051) — a caller piping stdout must still get the path and nothing else
- [ ] T039 [US4] Export `InitResult` from `src/endpaper/core/__init__.py`
- [ ] T040 [US4] **Trial, not an assertion** (SC-011): point a fresh assistant session at a newly initialised workspace, ask it to record a meeting, and observe whether it runs `endpaper meeting new` or hand-writes a file into `meetings/`. Record the result in the PR description. One trial is weak evidence; the point is to catch a regression to hand-writing

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The hardening and documentation that make the feature trustworthy rather than merely working

- [ ] T041 [P] Create `tests/integration/test_save_failure.py`: saving to a read-only file shows an error, **stays in edit with the buffer intact**, and leaves the file unchanged, in 100% of induced failure cases (FR-020, SC-011)
- [ ] T042 [P] Create `tests/integration/test_external_edits.py`: a document whose body, frontmatter field order, and line endings were all changed outside endpaper opens, edits, and saves indistinguishably from one endpaper wrote itself (FR-041, SC-010)
- [ ] T043 [P] Add to `tests/integration/test_edit_presentation.py`: non-ASCII, emoji, and right-to-left text is written back intact with the gutter still numbering real lines (FR-013)
- [ ] T044 [P] Add a resize case to `tests/integration/test_edit_save_tui.py`: resizing the terminal while editing preserves the buffer, the cursor position, and the dirty state
- [ ] T045 [P] Add an edge case to `tests/integration/test_edit_save_tui.py`: editing a document so it no longer matches the active filter moves the selection to the nearest remaining row on return, rather than leaving nothing selected
- [ ] T046 [P] Add a case to `tests/integration/test_save_failure.py`: deleting the frontmatter in the buffer and saving writes the bytes as typed, surfaces a warning, does not repair the file, and on the next scan the document is skipped with a warning and **never rewritten** (FR-018, FR-050)
- [ ] T047 [P] Document the `stty -ixon` fallback for terminals whose flow control swallows `ctrl+s` in `README.md`, and state that `ctrl+o` is the canonical save key (FR-035)
- [ ] T048 [P] Finalise the `0.0.3` section of `CHANGELOG.md`: the three edit-state bindings, `CLAUDE.md` at init, init no longer clobbering an existing `AGENTS.md`, and the **BREAKING** `init_workspace` return-type change with its one-line migration
- [ ] T049 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src` and fix everything they report
- [ ] T050 Walk the cross-platform matrix in [quickstart.md](./quickstart.md#cross-platform): `ctrl+o` saves on Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux; `ctrl+q` and `ctrl+c` still work from all three states; a CRLF file edited on Windows is still CRLF afterwards (FR-019, FR-033, SC-007)
- [ ] T051 Run the full [quickstart.md](./quickstart.md) validation guide top to bottom and confirm every acceptance scenario listed there has a passing test
- [ ] T052 **Final regression gate**: `uv run pytest` — the 154 baseline tests still pass alongside the new ones, and re-confirm the Constitution Check in [plan.md](./plan.md#constitution-check) against the built code

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup. **Blocks US1, US2, US3.** Does *not* block US4
- **US1 (Phase 3)**: Depends on Phase 2 complete
- **US2 (Phase 4)**: Depends on Phase 3 — the discard prompt needs a screen to leave
- **US3 (Phase 5)**: Depends on Phase 3 for `EditScreen` to exist; independent of Phase 4
- **US4 (Phase 6)**: Depends on **T005 only**. Otherwise fully independent
- **Polish (Phase 7)**: Depends on all desired stories being complete

### User Story Dependencies

- **US1 (P1)**: The MVP. Depends only on the foundational save path
- **US2 (P2)**: Builds on US1's `EditScreen`. Not independently deliverable — a discard prompt with
  no edit state is nothing — but independently *testable* once US1 lands
- **US3 (P3)**: Builds on US1's `EditScreen`. Can be developed in parallel with US2; they touch
  different methods of the same file, so land one before starting the other to avoid a merge
- **US4 (P4)**: Shares no file with US1–US3 beyond `models.py` (T005). Fully parallel

### Within Each User Story

- Tests are written first and must fail before implementation
- `core` before `tui`; models before the functions that return them
- Screens before the bindings that push them
- Story complete and checkpointed before moving to the next priority

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 in parallel (T001 first — it is the baseline)
- **Phase 2**: T010, T011, T012 in parallel once T005–T009 land. T006/T007/T008 are the same file and
  must be sequential
- **Phase 3**: T014 first (it should fail). T015–T017 are the same file and sequential; T018/T019 are
  the same file and sequential; T020 and T021 are independent of both
- **Phase 6**: T032, T033, T034 all in parallel. T035/T036 are the same file and sequential
- **Phase 7**: T041–T048 all in parallel; T049–T052 are sequential gates
- **Across phases**: one person on Phase 6 start to finish, another on Phases 2→3→4→5

---

## Parallel Example: Phase 2 unit tests

```bash
# Once T005-T009 land, all three test files are independent:
Task: "Create tests/unit/test_stamp_updated.py — the full matching table"
Task: "Create tests/unit/test_line_endings.py — CRLF/LF x trailing-newline round trips"
Task: "Create tests/unit/test_save_atomic.py — OSError injection at os.replace"
```

## Parallel Example: User Story 4

```bash
# Nothing here blocks on the editing work beyond T005:
Task: "Create tests/integration/test_init_guidance.py — US4 scenarios 1-3"
Task: "Create tests/contract/test_guidance_files.py — SC-013 forbidden-substring list"
Task: "Create src/endpaper/core/templates/CLAUDE.md.tmpl — <= 12 lines, pointer only"
```

---

## Implementation Strategy

### MVP First (User Story 1)

Phases 1 → 2 → 3 deliver the whole premise: open a note you already have and fix it, without leaving
the tool. That is demonstrable on its own and is where the feature's value is concentrated.

### Incremental Delivery

1. **Phases 1–3** — edit and save. Ship it, use it for a day.
2. **Phase 4** — the discard prompt. Nothing new is visible; entering the edit state becomes safe.
3. **Phase 5** — gutter, wrapping, footer. The buffer becomes legible.
4. **Phase 6** — the `CLAUDE.md` fix. Independent; can ship before or after any of the above.
5. **Phase 7** — hardening, documentation, and the cross-platform matrix.

### Suggested split if two people work in parallel

Phase 6 shares no file with Phases 2–5 except `models.py` (T005, a three-dataclass addition). One
person can take the guidance-file fix start to finish while another works the editing phases; there
is no meeting point beyond the final regression gate.

---

## Notes

- **The Phase 2 regression gate (T013) is not ceremony.** This feature writes to files the user owns
  and hand-edits. A green suite with zero existing test files edited is the only evidence that the
  save path preserves what was already there.
- **T032's third case fails before it passes.** `init_workspace` overwrites an existing `AGENTS.md`
  today (`workspace.py:52`); that is a live hole this feature closes, not a new requirement.
- **`[P]` means different files with no ordering dependency**, not "safe to skip review".
- Every task above maps to at least one requirement, acceptance scenario, or success criterion in
  [spec.md](./spec.md); the constitution requires that mapping to run in the other direction too, so
  a criterion without a test is a missing task, not an accepted gap.
