---

description: "Task list for 015-link-picker"
---

# Tasks: A Picker for Ambiguous `/link`

**Input**: Design documents from `/specs/015-link-picker/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. Not optional here — the constitution's Development Workflow gate requires a
behaviour change to land with the tests that cover it, and the plan's gate VI names the layers.
Coverage is risk-based (Principle VI): the sort and the row arithmetic are unit-tested because they
are pure and have many cases; keys, focus, and host parity are integration-tested because that is the
only layer where focus exists.

**Organization**: Grouped by user story so each is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: US1, US2, US3 — maps to the user stories in spec.md

## Path Conventions

Single project: `src/choom/` and `tests/` at the repository root, per plan.md.

---

## Phase 1: Setup

**Purpose**: Establish a green baseline and know which existing test this feature invalidates.

- [ ] T001 Run `uv run pytest` plus `uv run ruff format --check . && uv run ruff check . && uv run mypy src` from the repository root and confirm all green before touching anything
- [ ] T002 Read `test_link_several_matches_leaves_the_line_and_names_candidates` in tests/integration/test_links.py — it asserts the behaviour this feature replaces, and T022 rewrites it into the short-terminal fallback case rather than deleting it

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The candidate data every story reads. Ordering lives here because it is one function's
job, not a separate slice — US1 needs the candidates and US2 needs them ordered and dated.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Add the frozen, slotted `LinkCandidate` dataclass (`target`, `collection`, `date`) to src/choom/core/models.py per contracts/core-api.md
- [ ] T004 Implement `link_candidates(workspace, query)` in src/choom/core/links.py — one scan producing every match as a `LinkCandidate`, with `collection` from `target.kind` and `date` as an ISO string (`Document.created` verbatim; `Task.created.isoformat()` or `None`), ordered newest first with ties by title and undated records last, using the two stable sort passes from src/choom/core/documents.py; typed and docstring'd, never raises
- [ ] T005 Re-express `find_link_targets()` in src/choom/core/links.py as `tuple(c.target for c in link_candidates(workspace, query))`, deleting the now-duplicated scan body (depends on T004)
- [ ] T006 [P] Export `LinkCandidate` and `link_candidates` from src/choom/core/__init__.py, following the existing `LinkTarget` / `find_link_targets` entries
- [ ] T007 [P] Unit tests in tests/unit/test_link_candidates.py: newest-first ordering, case-insensitive title tie-break, undated records last, `collection` matching `kind` for all three record types, and that `find_link_targets` returns exactly the same records. Derive every fixture date from `date.today()` with `timedelta` offsets — never a literal date (Principle VI)

**Checkpoint**: `link_candidates()` is callable and tested without a terminal. Stories can begin.

---

## Phase 3: User Story 1 — Choose from the records that matched (Priority: P1) 🎯 MVP

**Goal**: An ambiguous `/link` raises a list in the status-bar region that can be moved through with
`↑`/`↓`, inserted from with `enter`, and dismissed with `esc` — in both editor hosts.

**Independent Test**: In a workspace with several records sharing a word, submit `/link <word>` in the
editor; confirm the list appears, the highlight moves and wraps, `enter` inserts a correct link, and
`esc` leaves the line byte-identical.

### Implementation for User Story 1

- [ ] T008 [US1] Create src/choom/tui/link_picker.py: a `LinkPicker(ListView)` holding its `tuple[LinkCandidate, ...]` and exposing `open(candidates)` / `close()`, with `action_cursor_down` / `action_cursor_up` overridden to call Textual's `loop_from_index(..., wrap=True)` (the base class passes `wrap=False` — verified in research R3), an `escape` binding, and `Chosen(candidate)` / `Cancelled()` messages so the widget never edits the buffer itself. Rows carry plain `candidate.target.title` for now; US2 replaces that
- [ ] T009 [P] [US1] Add `LINK_PICKER_HELP = "↑↓ move   enter insert   esc cancel   ctrl+q quit"` to src/choom/tui/status_bar.py, alongside `LINKS_SECTION_HELP` and following its comment about never concatenating footer strings
- [ ] T010 [P] [US1] Add `#link-picker` sizing to src/choom/tui/app.tcss (`max-height: 8`, border-top), mirroring the existing `#links-section` block
- [ ] T011 [P] [US1] Compose a hidden `LinkPicker` into `EditScreen`'s `#bottom-bar` above the `StatusBar` in src/choom/tui/edit_screen.py
- [ ] T012 [P] [US1] Compose a hidden `LinkPicker` into `ListScreen`'s `#bottom-bar` above the `CommandBar` in src/choom/tui/list_screen.py
- [ ] T013 [US1] In `EditorPane._insert_link` (src/choom/tui/edit_screen.py), switch to `link_candidates()` and, when more than one matches, open `self.screen.query_one(LinkPicker)` with the candidates, focus it, remember the target line index, and swap the footer to `LINK_PICKER_HELP` (depends on T008–T012)
- [ ] T014 [US1] Handle `LinkPicker.Chosen` in src/choom/tui/edit_screen.py: re-resolve with `resolve_id`, replace the remembered line with `format_link(...)` when it resolves and report without writing when it does not (FR-015), then close the picker, refocus `#editor`, and restore `EDIT_HELP`
- [ ] T015 [US1] Handle `LinkPicker.Cancelled` in src/choom/tui/edit_screen.py: close, refocus `#editor`, restore `EDIT_HELP`, and leave the typed line untouched
- [ ] T016 [US1] Extend `EditorPane.check_action` in src/choom/tui/edit_screen.py to return `False` for `save`, `save_and_close`, `close`, and `cancel_request` while the picker is open — the pane's `priority=True` bindings fire from the app down and would otherwise act underneath the list. Leave the app-level `ctrl+q` untouched (Principle V)
- [ ] T017 [P] [US1] Integration tests in tests/integration/test_links.py: the list opens on an ambiguous `/link` with the first row highlighted; `↓` then `enter` inserts a link to the second record with a path correct from the editing file; `↑` from the first row wraps to the last; `esc` leaves the line byte-identical; the footer shows the picker keys while open and the edit help after

**Checkpoint**: US1 is fully functional — an ambiguous `/link` can be completed without leaving the document.

---

## Phase 4: User Story 2 — Tell the candidates apart at a glance (Priority: P2)

**Goal**: Each row shows title, collection, and date, so two records sharing a title are
distinguishable without leaving the editor.

**Independent Test**: Create two records with the same title in different collections on different
dates, submit a `/link` matching both, and confirm each row shows all three fields with the newer
record first.

**Depends on**: Phase 2 for the data, and T008 for the widget whose rows it replaces.

### Implementation for User Story 2

- [ ] T018 [US2] Add `render_candidate_row(candidate, width)` to src/choom/tui/rendering.py: `title · collection · date`, truncating the title with `…` so collection and date always survive, rendering `—` for a `None` date, and never raising on a tiny width or a blank title (contracts/tui.md C3). Width is a parameter, not read off a widget — the same shape as `in_flight_status`
- [ ] T019 [US2] Use `render_candidate_row` for row labels in src/choom/tui/link_picker.py, passing the picker's own width (depends on T018)
- [ ] T020 [P] [US2] Unit tests in tests/unit/test_rendering.py: a long title truncates while collection and date survive intact; an undated candidate renders `—`; a width of 0 and a blank title both return a string rather than raising
- [ ] T021 [P] [US2] Integration test in tests/integration/test_links.py: two records sharing a title but differing in collection and date produce two visually distinct rows, newest first

**Checkpoint**: The list can be chosen from correctly, not just navigated.

---

## Phase 5: User Story 3 — The document is never disturbed (Priority: P3)

**Goal**: Every outcome leaves the writer where they were, in both hosts, at any terminal size, with
both fast paths untouched.

**Independent Test**: With a long document scrolled mid-way, run an ambiguous `/link` through both
insert and cancel and confirm the cursor, the scroll position, and the surrounding panes are unchanged.

### Implementation for User Story 3

- [ ] T022 [US3] Add `MIN_PICKER_SCREEN_HEIGHT = 12` and the fallback branch in src/choom/tui/edit_screen.py: when more than one record matches but the screen is shorter than the threshold, report `link_ambiguous_status(...)` and open no list (FR-017). Keep `link_ambiguous_status` in src/choom/tui/status_bar.py and update its docstring — it now describes the fallback, not the ordinary path
- [ ] T023 [US3] Add `on_resize` to src/choom/tui/link_picker.py: rebuild row labels at the new width from the held candidates, preserving the highlighted index; post `Cancelled` (with the fallback message) if the resize drops the screen below the threshold (FR-018)
- [ ] T024 [US3] Rewrite `test_link_several_matches_leaves_the_line_and_names_candidates` in tests/integration/test_links.py as the short-terminal fallback case — same assertions, run at a screen size below the threshold, so the message keeps its coverage where it is still correct
- [ ] T025 [P] [US3] Integration tests in tests/integration/test_links.py that the fast paths are unchanged: exactly one match inserts directly with no list, zero matches reports with no list, and `/link` with no terms still says it needs search terms
- [ ] T026 [P] [US3] Integration test in tests/integration/test_links.py for host parity (FR-004): the same open → move → insert flow, and the same cancel flow, run with the editor inline in the preview pane and full-screen, asserting identical outcomes
- [ ] T027 [P] [US3] Integration test in tests/integration/test_links.py that nothing is disturbed: the editor's cursor location and scroll position are unchanged across open, insert, and cancel; a key outside the four the footer names does not modify the buffer; and inline, the list and scope panes keep their size and position

**Checkpoint**: All three stories are functional and the interface's promises hold at every size.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T028 [P] Update the `/link` entry in src/choom/core/editor_commands.py so its description reflects choosing when several match, and confirm the help screen renders it (src/choom/tui/help_screen.py reads `EDITOR_COMMANDS`)
- [ ] T029 [P] Add an entry to the `[Unreleased]` section of CHANGELOG.md describing the picker in user-visible terms, following the existing "**CLI and TUI, user-visible**" style
- [ ] T030 Leave README.md alone. Its feature list describes the *released* version (see commit efc0872, "keep README to shipped features"), and this is unreleased v0.0.3 work — the release skill folds it in at release time. Confirm no README edit is in the diff
- [ ] T031 Work through quickstart.md scenarios 1–6 by hand, including the full-screen parity scenario and the short-terminal fallback
- [ ] T032 Run the full gates from the repository root: `uv run pytest`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src`
- [ ] T033 Verify cross-platform behaviour holds by running tests/unit/test_path_budget.py and the link path tests in tests/unit/test_link_paths.py: workspace paths with spaces and non-ASCII characters produce correct inserted links, and `relative_destination`'s path budget is unaffected

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: after Setup — **blocks every user story**
- **US1 (Phase 3)**: after Phase 2
- **US2 (Phase 4)**: after Phase 2; T019 also needs T008 from US1
- **US3 (Phase 5)**: after Phase 3 — it constrains the picker US1 builds
- **Polish (Phase 6)**: after the stories being shipped are complete

### Within Each User Story

- Widget before wiring; wiring before the tests that drive it
- T013 → T014 → T015 → T016 are all in `edit_screen.py` and touch the same handler region, so they run in sequence
- T004 → T005 are the same function pair in `links.py`, so likewise

### Parallel Opportunities

- Phase 2: T006 and T007 in parallel once T004 lands
- US1: T009, T010, T011, T012 are four different files — all parallel; T017 parallel with itself once T013–T016 land
- US2: T020 and T021 in parallel
- US3: T025, T026, T027 in parallel (all new tests, no shared edits)
- Phase 6: T028 and T029 in parallel

---

## Parallel Example: User Story 1

```bash
# After Phase 2, launch the four independent files together:
Task: "Add LINK_PICKER_HELP to src/choom/tui/status_bar.py"
Task: "Add #link-picker sizing to src/choom/tui/app.tcss"
Task: "Compose LinkPicker into EditScreen's #bottom-bar"
Task: "Compose LinkPicker into ListScreen's #bottom-bar"
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 → Phase 2 → Phase 3
2. **STOP and validate**: an ambiguous `/link` can be completed from the list in both hosts
3. At this point the feature's whole value is delivered; rows show titles only

### Incremental Delivery

- **+US2**: rows gain collection and date, so records sharing a title become distinguishable
- **+US3**: the bounded/fallback/resize guarantees and the regression net around the fast paths
- **+Polish**: help text, changelog, manual validation, and the cross-platform check

Each increment leaves the tree green and shippable.
