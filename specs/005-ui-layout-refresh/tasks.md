# Tasks: UI Layout Refresh

**Input**: Design documents from `specs/005-ui-layout-refresh/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included and **not optional for this project**. Constitution VI requires every acceptance
criterion in a spec to map to at least one test, and every pull request to pass formatting, linting,
type checking, and the suite. The FR → test map in [quickstart.md](./quickstart.md) is the coverage
contract these tasks implement.

**Organization**: Tasks are grouped by user story so each can be implemented, tested, and demoed on
its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- Exact file paths are given in every task

## Path Conventions

Single Python package at the repository root: `src/endpaper/{core,cli,tui}/`, `tests/{unit,
integration,contract,performance,fixtures}/`, plus `pyproject.toml` and `.github/workflows/`.

---

## Phase 1: Setup (Versioning & Release Tooling)

**Purpose**: Make the version a fact about the built artifact before anything displays it. Sequenced
first because FR-042 cannot be honestly tested while `__version__` is a hardcoded literal that can
disagree with the package. See [contracts/versioning.md](./contracts/versioning.md) and research R9.

- [X] T001 Set `fallback-version = "0.0.0"` and add `[tool.hatch.build.hooks.vcs]` with `version-file = "src/endpaper/_version.py"` in `pyproject.toml`
- [X] T002 Replace the hardcoded literal in `src/endpaper/__init__.py` with a `try: from endpaper._version import __version__ / except ImportError: __version__ = "0.0.0"`
- [X] T003 [P] Add `src/endpaper/_version.py` to `.gitignore`
- [X] T004 Verify what `uv pip install -e .` produces (research R9 open item) and, if the build hook stamps a dev version instead of leaving the fallback, scope the hook to the wheel and sdist targets in `pyproject.toml` so a source checkout reports `0.0.0`
- [X] T005 [P] Unit test that `__version__` falls back to `0.0.0` with no `_version.py` present, in `tests/unit/test_version_fallback.py`
- [X] T006 [P] Contract test that the TUI status bar string and `endpaper --version` report the same version, asserting parity and never a literal, in `tests/contract/test_version_parity.py`
- [X] T007 Add `.github/workflows/release-dry-run.yml`: `workflow_dispatch` with a required `version` input, PEP 440 input validation, full quality gate, `uv build --no-sources` under `SETUPTOOLS_SCM_PRETEND_VERSION`, clean-venv install, assert `endpaper --version` matches the input, then `actions/upload-artifact` of `dist/` — with **no** `environment: pypi` and **no** `id-token: write`
- [X] T008 [P] Record the versioning change (build-stamped `__version__`, `0.0.0` from source) in `CHANGELOG.md`

**Checkpoint**: `endpaper --version` reports `0.0.0` from a checkout and the real version from a
build; the dry-run workflow can rehearse a release without publishing.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The month-scoped read API in `core`, the session state that replaces the eager scan, and
the pane skeleton the collection bar and scope pane both need.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Core month API

- [X] T009 Add frozen slotted `YearMonth` and `MonthListing` dataclasses in `src/endpaper/core/models.py` per [data-model.md](./data-model.md)
- [X] T010 Implement `list_months(workspace, collection) -> MonthListing` in `src/endpaper/core/documents.py` — glob `<scan_dir>/**/YYYY/MM` directories only, open no files, always include the current month, dedupe across the `daily/` subtree, ignore non-conforming directory names
- [X] T011 Implement `scan_month(workspace, collection, month)` in `src/endpaper/core/documents.py`, reusing `_parse_document` so warning behaviour matches `scan_documents` exactly
- [X] T012 Implement `scan_unfiled(workspace, collection)` in `src/endpaper/core/documents.py` for `*.md` outside any `YYYY/MM` folder (research R6)
- [X] T013 [P] Add `list_meeting_months` and `scan_meeting_month` wrappers in `src/endpaper/core/meetings.py`
- [X] T014 [P] Add `list_note_months` and `scan_note_month` wrappers in `src/endpaper/core/notes.py`

### Core tests and fixtures

- [X] T015 [P] Unit tests for month discovery — ordering, current month always present, `daily/` dedupe, junk directory names ignored, zero files opened — in `tests/unit/test_list_months.py`
- [X] T016 [P] Unit tests for `scan_month` and `scan_unfiled` — ordering identical to `scan_documents` for the same subset, malformed frontmatter yields a warning not an exception — in `tests/unit/test_scan_month.py`
- [X] T017 Add a month-spreading option to `tests/fixtures/generate.py` so generated documents land across many months instead of all in `2026/01`
- [X] T018 Add a read-counting harness and the scoping assertion (opening a collection reads only the current month's paths) in `tests/performance/test_month_scope.py`

### Session state and layout skeleton

- [X] T019 Replace `documents`/`visible_documents` on `EndpaperApp` with the session state in [data-model.md](./data-model.md) — `active`, `month_scope`, `task_category`, `month_cache`, `month_warnings`, `unfiled_cache`, `fully_loaded`, `filter_query`, `pre_filter_scope` — in `src/endpaper/tui/app.py`
- [X] T020 Re-point `refresh_document` at `month_cache` (and `unfiled_cache`), keyed by the month implied by the saved document's path, in `src/endpaper/tui/app.py`
- [X] T021 Restructure `ListScreen.compose` in `src/endpaper/tui/list_screen.py` and the pane widths in `src/endpaper/tui/app.tcss`: remove `#collection-menu`, add the scope pane container, return the freed 14 columns to the `2fr`/`3fr` split per [contracts/tui-keys.md](./contracts/tui-keys.md)

**Checkpoint**: core can list and read one month at a time, the app holds month-scoped session state,
and the three panes exist without a collection menu.

---

## Phase 3: User Story 1 - Collections along the top, Tab walks them (Priority: P1) 🎯 MVP

**Goal**: The three collections live on one line at the top; Tab and shift+Tab move between them and
the content area follows immediately, with focus landing on the list pane.

**Independent Test**: Launch the tool, confirm the bar lists all three collections with exactly one
highlighted, Tab and shift+Tab through every position including both wraps, and confirm the panes
refill at each stop with no further keypress.

### Tests for User Story 1

- [X] T022 [P] [US1] Integration tests for the bar and Tab navigation — three collections in order with one highlighted, Tab/shift+Tab wrap at both ends, focus lands on the list pane with row 0 highlighted, Tab inert while the command bar is open — in `tests/integration/test_collection_bar_tui.py`

### Implementation for User Story 1

- [X] T023 [P] [US1] Create the non-focusable `CollectionBar` `Static` rendering `Endpaper >>   Tasks   Notes   Meetings` with the active name styled, in `src/endpaper/tui/collection_bar.py` (research R1)
- [X] T024 [US1] Mount `CollectionBar` docked top in `ListScreen.compose` and style it in `src/endpaper/tui/app.tcss`
- [X] T025 [US1] Add non-priority `tab`/`shift+tab` bindings and `action_next_collection`/`action_previous_collection` with wrap-around in `src/endpaper/tui/list_screen.py` (research R2)
- [X] T026 [US1] Implement `ListScreen.check_action` returning `False` for both collection actions while the command bar is open, in `src/endpaper/tui/list_screen.py`
- [X] T027 [US1] On collection switch, refill all three panes and focus the list pane with row 0 highlighted, in `src/endpaper/tui/list_screen.py`
- [X] T028 [US1] Default the startup collection to Tasks and update the footer strings for the new bindings (`tab collection`, no Tab-as-focus-traversal) in `src/endpaper/tui/app.py` and `src/endpaper/tui/status_bar.py`
- [X] T029 [US1] Rewrite `tests/integration/test_collection_menu_tui.py` against `CollectionBar` and Tab, replacing the `#collection-menu` `ListView` and `CollectionRow` assertions (research R12)
- [X] T030 [US1] Update pane expectations in `tests/integration/test_partitioned_layout.py` for the removed menu pane

**Checkpoint**: collection switching is one keystroke and the layout has its top bar. US1 is
demoable on its own.

---

## Phase 4: User Story 2 - One month at a time (Priority: P1)

**Goal**: Notes and Meetings show a month list in the left pane, default to the current month, and
read only the displayed month from disk.

**Independent Test**: With documents across several months, open the tool and confirm only the
current month's files were read and only its documents are listed; move to an adjacent month and
confirm the same holds for that month.

### Tests for User Story 2

- [X] T031 [P] [US2] Integration tests for the month pane — current month highlighted on selection, moving months refills the list and preview, empty month shows the empty state, warning counts are per-month, returning to a collection resets to the current month — in `tests/integration/test_month_pane_tui.py`
- [X] T032 [P] [US2] Extend `tests/performance/test_month_scope.py` with the adjacent-month case: moving the highlight reads that month's paths and no others

### Implementation for User Story 2

- [X] T033 [P] [US2] Create `ScopePane` in `src/endpaper/tui/scope_pane.py` with a months mode rendering `YYYY-MM` entries most-recent-first
- [X] T034 [US2] Populate the scope pane from `list_months` when Notes or Meetings becomes active, defaulting the highlight to the current month, in `src/endpaper/tui/list_screen.py`
- [X] T035 [US2] Fill the list pane from `month_cache`, reading via `scan_month` on a miss, in `src/endpaper/tui/list_screen.py`
- [X] T036 [US2] Refill the list pane and preview when the scope-pane highlight moves, without moving focus off the scope pane, in `src/endpaper/tui/list_screen.py`
- [X] T037 [US2] Render the **Unfiled** entry after the months when `MonthListing.has_unfiled`, reading via `scan_unfiled` only when selected, in `src/endpaper/tui/scope_pane.py` and `src/endpaper/tui/list_screen.py`
- [X] T038 [US2] Move the displayed month to the created document's month and highlight it, on every create path, in `src/endpaper/tui/app.py`
- [X] T039 [US2] Scope the status bar's warning count to the displayed month using `month_warnings`, in `src/endpaper/tui/list_screen.py`
- [X] T040 [US2] Add per-collection empty-state text naming the month (`No meetings in 2026-07…`) in `src/endpaper/tui/list_screen.py`
- [X] T041 [P] [US2] Update `tests/integration/test_list_tui.py` for month-scoped listing
- [X] T042 [P] [US2] Update `tests/integration/test_list_notes_tui.py` for month-scoped listing
- [X] T043 [US2] Extend `tests/integration/test_unicode_paths.py` to cover the month-scoped read path (spaces and non-ASCII in workspace paths)

**Checkpoint**: a workspace with years of history opens as fast as an empty one, and the left pane
navigates months.

---

## Phase 5: User Story 3 - To-Do and Done are places (Priority: P2)

**Goal**: Tasks shows To-Do and Done as left-pane categories, defaulting to To-Do, with the preview
pane blank — and the same selection is available from the command line.

**Independent Test**: Open Tasks with a mix of open and completed tasks, confirm To-Do lists only
open ones, move to Done and confirm it lists only completed ones, and confirm the right pane stays
blank throughout.

### Tests for User Story 3

- [X] T044 [P] [US3] Unit tests for the `only_done` selection matrix (open-only, all, done-only, `only_done` overriding `include_done`) in `tests/unit/test_task_filter_only_done.py`
- [X] T045 [P] [US3] Integration tests for the category pane — To-Do default and focus, toggling moves a task between categories, preview blank, create returns to To-Do — in `tests/integration/test_task_category_tui.py`
- [X] T046 [P] [US3] Extend `tests/integration/test_task_cli.py` for `task list --done`, including `--json` output and `--done` winning over `--all`

### Implementation for User Story 3

- [X] T047 [US3] Add `only_done: bool = False` to `TaskFilter` in `src/endpaper/core/models.py`
- [X] T048 [US3] Honour `only_done` in `filter_tasks` in `src/endpaper/core/tasks.py`, leaving both existing branches untouched
- [X] T049 [US3] Add `--done` to `task list` in `src/endpaper/cli/main.py`, documented as taking precedence over `--all` rather than erroring (research R8)
- [X] T050 [US3] Add the categories mode to `ScopePane` in `src/endpaper/tui/scope_pane.py`
- [X] T051 [US3] Drive `task_category` from the scope pane and keep the preview pane blank for Tasks, in `src/endpaper/tui/list_screen.py`
- [X] T052 [US3] Remove the `a` show-all binding and its footer text from `src/endpaper/tui/list_screen.py` and `src/endpaper/tui/status_bar.py`
- [X] T053 [US3] Rewrite the show-all assertions in `tests/integration/test_task_tui.py` against the Done category

**Checkpoint**: task state is a visible place rather than a remembered mode, in both front-ends.

---

## Phase 6: User Story 4 - Editing starts where you are looking (Priority: P2)

**Goal**: `e` opens the editor on the highlighted document, and creating a document lands straight in
the editor — both through one shared route.

**Independent Test**: Press `e` on a highlighted document and confirm the editor opens on its raw
markdown; separately create a document and confirm the editor opens with no read view first.

### Tests for User Story 4

- [X] T054 [P] [US4] Integration tests for `e` from the list — editor opens on the raw markdown, save-and-exit returns to the list with the row updated, `e` is a no-op on tasks and on the empty state — in `tests/integration/test_edit_from_list_tui.py`
- [X] T055 [P] [US4] Integration tests that create paths open the editor directly (note, meeting, daily note) and that exiting lands on the list in the new document's month, in `tests/integration/test_create_opens_editor_tui.py`
- [X] T056 [P] [US4] Parity test that `e`-from-list and `e`-from-preview produce an `EditScreen` with identical bindings and buffer for the same document, in `tests/integration/test_edit_from_list_tui.py`

### Implementation for User Story 4

- [X] T057 [US4] Add `open_editor(app, path) -> bool` to `src/endpaper/tui/edit_screen.py` — the single route into the editor — handling `load_for_edit`'s `OSError` as a status-bar message that leaves the caller's screen in place (research R10)
- [X] T058 [US4] Route `PreviewScreen.action_edit` through `open_editor` in `src/endpaper/tui/preview_screen.py`
- [X] T059 [US4] Add the `e` binding and `action_edit` (documents only, no-op on tasks and empty state) in `src/endpaper/tui/list_screen.py`
- [X] T060 [US4] Route the note and meeting create handlers through `open_editor` instead of pushing `PreviewScreen`, in `src/endpaper/tui/list_screen.py`
- [X] T061 [US4] Route the daily-note handler through `open_editor`, whether or not the note already existed, in `src/endpaper/tui/list_screen.py`
- [X] T062 [US4] Add `e edit` to the list footer in `src/endpaper/tui/status_bar.py`
- [X] T063 [P] [US4] Update the post-create screen assertions in `tests/integration/test_create_tui.py`, `tests/integration/test_create_note_tui.py`, and `tests/integration/test_daily_note_tui.py` to expect `EditScreen`

**Checkpoint**: every route into the editor goes through one function, and creating a document means
typing into it.

---

## Phase 7: User Story 5 - Commands are typed as commands (Priority: P3)

**Goal**: A permanent `/` prefix, `filter`/`f` as an explicit verb searching every month, and a named
error for anything unrecognised.

**Independent Test**: Press `/`, confirm the slash cannot be deleted, run `/filter <term>` and
`/f <term>` and confirm identical narrowing including matches from other months, and type an
unrecognised verb and confirm an error rather than a filtered list.

### Tests for User Story 5

- [X] T064 [P] [US5] Unit tests for the verb table and parser — aliases, `verb.type` forms, unknown-verb error, no leading-space escape hatch, no `_normalize` — in `tests/unit/test_command_parsing.py`
- [X] T065 [P] [US5] Integration tests for the undeletable prefix (backspace on an empty bar keeps `/` and the bar open) in `tests/integration/test_command_bar_prefix.py`
- [X] T066 [P] [US5] Integration tests for `/filter` and `/f` — live narrowing, empty term clears and restores the previous month, escape clears and restores — in `tests/integration/test_filter_verb_tui.py`
- [X] T067 [P] [US5] Integration tests for cross-month filtering — matches from other months listed newest-first, scope shown as suspended, opening a match and returning keeps the results — in `tests/integration/test_cross_month_filter_tui.py`
- [X] T068 [P] [US5] Extend `tests/performance/test_month_scope.py` to assert a filter reads each month at most once per session

### Implementation for User Story 5

- [X] T069 [P] [US5] Extract the verb table (verb, alias, argument shape, one-line description) into `src/endpaper/tui/commands.py` as the single source for the parser and the help pane, per [contracts/commands.md](./contracts/commands.md)
- [X] T070 [US5] Compose the bar as `Horizontal(Static("/", id="bar-prefix"), Input(...))` and style it in `src/endpaper/tui/command_bar.py` and `src/endpaper/tui/app.tcss` (research R3)
- [X] T071 [US5] Delete `_normalize()` and the leading-space filter escape hatch, and resolve verbs against the table in `src/endpaper/tui/command_bar.py`
- [X] T072 [US5] Add the `filter`/`f` verb with live filtering once the verb is complete, and clearing on an empty term, in `src/endpaper/tui/command_bar.py`
- [X] T073 [US5] Emit `unknown command: '<token>'. Press / then 'help' for the list.` for an unrecognised first token, leaving the list untouched, in `src/endpaper/tui/command_bar.py`
- [X] T074 [US5] Load every month into `month_cache` on the first filter keystroke using a `@work(thread=True, exclusive=True)` worker, setting `fully_loaded`, in `src/endpaper/tui/app.py` (research R7)
- [X] T075 [US5] Capture `pre_filter_scope` when a filter becomes active and restore that month when it clears or is cancelled, in `src/endpaper/tui/app.py`
- [X] T076 [US5] Show the scope as suspended in the scope pane while a cross-month filter is active, a `Searching…` row while the load runs, and a distinct `No matches for '<term>'.` state, in `src/endpaper/tui/scope_pane.py` and `src/endpaper/tui/list_screen.py`
- [X] T077 [P] [US5] Update `tests/integration/test_command_bar_visibility.py` for the prefix widget and rewrite the bare-word filter assertions in the existing unit filter tests

**Checkpoint**: no typed word can be silently reinterpreted as a search, and filtering reaches the
whole collection.

---

## Phase 8: User Story 6 - The tool explains itself, and says which one it is (Priority: P3)

**Goal**: `/help` opens a pane listing every command with a description over a still-visible list,
and the running version sits in the bottom-right.

**Independent Test**: Submit `/help`, confirm every verb appears with a description, dismiss it and
confirm the screen underneath is untouched; separately confirm the bottom-right shows the version.

### Tests for User Story 6

- [X] T078 [P] [US6] Integration tests for the help pane — every verb in the table appears, the list stays partly visible, escape restores highlighted row, month, and active filter unchanged — in `tests/integration/test_help_pane_tui.py`
- [X] T079 [P] [US6] Integration test that the version renders in the bottom-right of every screen, in `tests/integration/test_version_indicator.py`

### Implementation for User Story 6

- [X] T080 [P] [US6] Create `HelpScreen(ModalScreen[None])` with a bottom-docked container at `height: 60%` over an alpha background, dismissed by escape, in `src/endpaper/tui/help_screen.py` (research R4)
- [X] T081 [US6] Style the help pane in `src/endpaper/tui/app.tcss`
- [X] T082 [US6] Render the pane from the verb table in `src/endpaper/tui/commands.py` plus the key bindings, so no accepted command can be missing, in `src/endpaper/tui/help_screen.py`
- [X] T083 [US6] Add the `help` verb and push `HelpScreen` from the command bar, in `src/endpaper/tui/command_bar.py` and `src/endpaper/tui/list_screen.py`
- [X] T084 [US6] Render `v{__version__}` right-aligned in the bottom bar, importing the same attribute the CLI uses, in `src/endpaper/tui/status_bar.py`
- [X] T085 [US6] Ensure the version is present on the preview and edit screens' status bars too, in `src/endpaper/tui/status_bar.py`
- [X] T086 [US6] Add a test asserting every verb in the table appears in the rendered pane, in `tests/integration/test_help_pane_tui.py`

**Checkpoint**: all six stories are independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T087 [P] Record the public API changes in `CHANGELOG.md`: `TaskFilter.only_done`, `list_months`/`scan_month`/`scan_unfiled` and their wrappers, and `task list --done`
- [X] T088 [P] Record the user-visible behaviour changes in `CHANGELOG.md`: startup collection is now Tasks, the `a` show-all binding is retired, `filter` is an explicit verb, create opens the editor
- [X] T089 [P] Update the TUI description in `README.md` and the command list in the `AGENTS.md` template under `src/endpaper/core/templates/` if the new verbs change what an assistant should know
- [X] T090 Confirm every FR in the [quickstart.md](./quickstart.md) FR → test map has a passing test, and add any that are missing
- [X] T091 Run the full gate — `ruff format --check .`, `ruff check .`, `mypy`, `pytest` — and fix what it reports
- [X] T092 Walk all eight scenarios in [quickstart.md](./quickstart.md) by hand, including the local build and pretend-version rehearsals
- [ ] T093 Verify the TUI on Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux — specifically that `shift+tab` arrives, the top bar renders at 80 columns, and the modal help pane redraws on resize
- [X] T094 Verify the layout degrades legibly in a terminal too narrow for three panes, keeping the highlighted collection identifiable
- [X] T095 Run the release dry-run workflow once with a proposed version and confirm the artifact installs and reports that version

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately. Blocks only US6's version indicator, but
  is sequenced first so nothing displays a version that is not yet trustworthy.
- **Foundational (Phase 2)**: depends on Setup only for repository hygiene; **blocks every user
  story**.
- **User Stories (Phases 3–8)**: all depend on Foundational. See the cross-story notes below.
- **Polish (Phase 9)**: depends on all desired stories.

### User Story Dependencies

- **US1 (P1)** — depends on Foundational only. The MVP.
- **US2 (P1)** — depends on Foundational only. Independent of US1: the month pane can be exercised
  with the collection set programmatically, though it is far more pleasant to demo after US1.
- **US3 (P2)** — depends on Foundational, and shares `scope_pane.py` with US2 (T033 creates the
  widget, T050 adds its second mode). If US3 is built before US2, T033 moves into Phase 5.
- **US4 (P2)** — depends on Foundational, specifically T020 (`refresh_document` re-pointed at the
  month cache), or the row will not reflect a save. Otherwise independent.
- **US5 (P3)** — depends on Foundational and on US2's `month_cache` being populated by `scan_month`
  (T035). The cross-month load (T074) has nothing to fill without it.
- **US6 (P3)** — depends on Foundational, on Phase 1 for a trustworthy version, and shares the verb
  table with US5 (T069 creates it, T082 renders it). If US6 is built before US5, T069 moves into
  Phase 8.

### Within Each User Story

- Tests are written first and must fail before the implementation tasks in the same phase
- Core (`src/endpaper/core/`) before adapters (`cli/`, `tui/`)
- Widgets before the screen wiring that mounts them
- Existing-test rewrites last within the phase, once the behaviour they assert exists

### Parallel Opportunities

- T003, T005, T006, T008 in Setup
- T013–T018 in Foundational, once T009–T012 land
- Every `Tests for User Story N` block — different files, no shared state
- T023 (`collection_bar.py`), T033 (`scope_pane.py`), T069 (`commands.py`), T080 (`help_screen.py`)
  are four new files with no import cycles between them
- With more than one developer: US1 and US2 in parallel after Foundational, then US3 and US4, then
  US5 and US6 (respecting the two shared-file notes above)

---

## Parallel Example: User Story 1

```bash
# Tests first:
Task: "Integration tests for the bar and Tab navigation in tests/integration/test_collection_bar_tui.py"

# Then the new widget, independent of the screen wiring:
Task: "Create CollectionBar in src/endpaper/tui/collection_bar.py"

# T029 and T030 rewrite different existing test files and can run together at the end:
Task: "Rewrite tests/integration/test_collection_menu_tui.py against CollectionBar"
Task: "Update pane expectations in tests/integration/test_partitioned_layout.py"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (US1)
2. **STOP and VALIDATE**: quickstart Scenario 1 end to end
3. The tool is demoable: collections on top, one keystroke to switch, a third of the width back

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → the layout everyone sees (MVP)
3. US2 → the performance claim the issue was really about
4. US3 → visible task state, both front-ends
5. US4 → the two keystrokes back
6. US5 → commands stop colliding with search
7. US6 → discoverability and a version to quote in bug reports

Each step is independently testable and leaves the tool in a shippable state.

### Notes

- `[P]` tasks touch different files and have no incomplete dependencies
- The `tests/contract/` suite must keep passing untouched apart from T046's `--done` addition — it
  pins the CLI's exit codes, `--json` schema, non-blocking behaviour, and no-ANSI-on-non-TTY
  guarantees, none of which this feature may change
- Commit per task or per logical group; stop at any checkpoint to validate a story on its own
