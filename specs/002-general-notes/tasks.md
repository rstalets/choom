---

description: "Task list for 002-general-notes"
---

# Tasks: General Notes

**Input**: Design documents from `/specs/002-general-notes/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks are **required** for this feature, not optional. SC-006 requires 100% of
acceptance scenarios covered by automated tests that run with no terminal attached, and Constitution
Principle VI requires every acceptance criterion to map to at least one test.

**Organization**: Tasks are grouped by user story so each can be implemented and verified
independently.

**Builds on feature 001**, which is already implemented. Most of Phase 2 is a refactor of existing
code, not new code. Read [research.md R1](./research.md#r1-how-notes-share-code-with-meetings) and
[R2](./research.md#r2-naming-and-backward-compatibility-of-the-core-api) before starting it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, `src/` layout. Package code under `src/endpaper/`, tests under `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the baseline this feature's refactor is measured against

- [ ] T001 Run `uv run pytest` and record the passing test count — this is the baseline the Phase 2 regression gate (T015) compares against, and it must be green before any code changes
- [ ] T002 [P] Bump `__version__` to `0.0.2` in `src/endpaper/__init__.py`
- [ ] T003 [P] Add an Unreleased `0.0.2` section to `CHANGELOG.md` with placeholders for the three new CLI commands and the additive `core` API change (Principle VI)
- [ ] T004 [P] Extend `tests/conftest.py` with a `frozen_now` helper usable by note creation and a `daily_note_path(workspace, day)` helper, reusing the existing frozen-clock and seeded-id fixtures

**Checkpoint**: Baseline green and recorded; note-aware fixtures available.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Generalise feature 001's meeting machinery into a collection-parameterised document
layer, so notes are a second consumer rather than a second copy

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**⚠️ This phase adds no user-visible behaviour.** Its acceptance criterion is T016: feature 001's
entire suite passes with **zero test files edited**. If a 001 test needs changing, the aliases-only
premise of [R2](./research.md#r2-naming-and-backward-compatibility-of-the-core-api) has broken —
fix that before building notes on top of it.

- [ ] T005 Rename `Meeting` to `Document` and `MeetingFilter` to `DocumentFilter` in `src/endpaper/core/models.py`, then add `Meeting = Document`, `Note = Document`, and `MeetingFilter = DocumentFilter` as module-level aliases — true aliases, never subclasses, per [data-model.md](./data-model.md#changed-document-was-meeting)
- [ ] T006 Add the frozen slotted `Collection` dataclass (`id_prefix`, `create_dir`, `scan_dirs`, `reserved_types`) to `src/endpaper/core/models.py` per [data-model.md](./data-model.md#new-collection)
- [ ] T007 Add the frozen slotted `DailyNote` dataclass (`path`, `document: Document | None`, `created: bool`) to `src/endpaper/core/models.py` per [data-model.md](./data-model.md#new-dailynote)
- [ ] T008 Add `notes_dir` and `daily_dir` properties to `Workspace` in `src/endpaper/core/models.py`
- [ ] T009 Add `new_document_id(when, prefix)` to `src/endpaper/core/text.py` and reduce `new_meeting_id(when)` to a one-line binding of it with `"m_"`, keeping its signature unchanged
- [ ] T010 Create `src/endpaper/core/documents.py` by moving `_validate_token`, `create_meeting`, `scan_meetings`, `filter_meetings`, and `match_meeting` out of `meetings.py` and renaming them to `create_document`, `scan_documents`, `filter_documents`, `match_document`, each taking a `collection: Collection` parameter — behaviour must be byte-for-byte the same as today for the meetings case
- [ ] T011 In `src/endpaper/core/documents.py`, make `create_document` take its target directory from `collection.create_dir` and its id prefix from `collection.id_prefix`, and reject `type` values in `collection.reserved_types` with a `UsageError` raised **before any filesystem work** per [R8](./research.md#r8-the-reserved-daily-type)
- [ ] T012 In `src/endpaper/core/documents.py`, make `scan_documents` walk every directory in `collection.scan_dirs` with a non-recursive `glob("*.md")`, concatenate the results before sorting, and treat a missing directory as contributing nothing rather than as a warning per [data-model.md](./data-model.md#scan-behaviour)
- [ ] T013 Add a `_read_document(path) -> Document | None` helper to `src/endpaper/core/documents.py` that parses one file's frontmatter and returns `None` rather than raising when it does not parse, and refactor `scan_documents` to use it so single-file and bulk parsing cannot diverge
- [ ] T014 Reduce `src/endpaper/core/meetings.py` to the `MEETINGS` descriptor (`Collection("m_", "meetings", ("meetings",), frozenset())`) plus four bound wrappers whose signatures exactly match feature 001's, and create `src/endpaper/core/notes.py` with the `NOTES` descriptor (`Collection("n_", "notes", ("notes", "notes/daily"), frozenset({"daily"}))`) plus `create_note` and `scan_notes` bindings
- [ ] T015 Update `src/endpaper/core/frontmatter.py` to annotate `render_frontmatter` against `Document`, and update `src/endpaper/core/__init__.py` to export `Document`, `Note`, `Collection`, `DailyNote`, `DocumentFilter`, the generic document functions, and the notes functions, keeping every feature 001 export in place per [contracts/core-api.md](./contracts/core-api.md)
- [ ] T016 **Regression gate**: run `uv run pytest` and confirm the same passing count as T001 with **zero test files edited**. Do not proceed to Phase 3 until this holds
- [ ] T017 [P] Create `tests/unit/test_collection.py` asserting the `MEETINGS` and `NOTES` descriptor values, that `new_document_id` honours its prefix, that `Meeting is Document` and `Note is Document`, and that a reserved type raises before any directory is created

**Checkpoint**: Core is collection-parameterised, meetings behave exactly as before, and notes have a
descriptor. User stories can now proceed.

---

## Phase 3: User Story 1 - Keep one note per day without deciding anything (Priority: P1) 🎯 MVP

**Goal**: `/note` and `endpaper note today` open today's daily note — creating it once, then opening
that same file untouched for the rest of the day.

**Independent Test**: From a fresh workspace, run the daily-note command twice on the same day with
content written in between, and confirm exactly one file exists, its bytes and mtime are unchanged by
the second call, and it is reachable from the notes list.

### Tests for User Story 1 ⚠️

> **Write these first and confirm they FAIL before implementing.**

- [ ] T018 [P] [US1] Create `tests/integration/test_daily_note.py` covering US1 scenarios 1–4: first call creates `notes/daily/YYYY-MM-DD.md` with `type: daily` and title equal to the ISO date; second call same day returns the same path, creates no second file, and leaves the file **byte-identical and mtime-identical** per [R10](./research.md#r10-test-strategy-for-the-file-did-not-change)
- [ ] T019 [P] [US1] Add to `tests/integration/test_daily_note.py` the edge cases from spec §Edge Cases: a missing `notes/daily/` is recreated (US1 scenario 5); an existing file with broken frontmatter is still opened, not replaced, and not repaired; a zero-byte existing file is treated as existing; no other workspace file is modified (US1 scenario 6)
- [ ] T020 [P] [US1] Add a concurrency test to `tests/integration/test_daily_note.py` that invokes the daily-note path 20 times from threads and asserts exactly one file results — the property `O_EXCL` buys per [R3](./research.md#r3-making-the-daily-note-idempotent-without-a-read-modify-write)

### Implementation for User Story 1

- [ ] T021 [US1] Implement `open_daily_note(workspace, *, now=None) -> DailyNote` in `src/endpaper/core/notes.py`: build the path from the local date, `mkdir` the daily directory, then `os.open(..., O_CREAT | O_EXCL | O_WRONLY)` and treat `FileExistsError` as the already-exists path, returning `DailyNote(path, _read_document(path), created=False)` per [contracts/core-api.md](./contracts/core-api.md#notes)
- [ ] T022 [US1] Export `open_daily_note` and `DailyNote` from `src/endpaper/core/__init__.py`
- [ ] T023 [US1] Add the `note today` subparser and a `_cmd_note_today` handler to `src/endpaper/cli/main.py` that prints the returned path relative to the workspace root and exits 0 in both the created and existing cases per [contracts/cli.md](./contracts/cli.md#endpaper-note-today)
- [ ] T024 [US1] Add `note` to `VERBS` in `src/endpaper/tui/command_bar.py` and post a new `DailyRequested` message when the input is bare `/note` — no type part and no description — per [contracts/tui.md](./contracts/tui.md#the-note-grammar)
- [ ] T025 [US1] Add an `open_daily_note_and_track` method to `src/endpaper/tui/app.py` that calls `open_daily_note` and inserts into the in-memory notes list only when `created and document is not None`
- [ ] T026 [US1] Change `render_preview_markdown` in `src/endpaper/tui/rendering.py` to take `(path, document: Document | None)`, rendering the heading and metadata line from the record when present and falling back to a filename heading with no metadata line when it is `None`, stripping the frontmatter block in both cases
- [ ] T027 [US1] Update `src/endpaper/tui/preview_screen.py` and `src/endpaper/tui/list_screen.py` for the new `render_preview_markdown` signature, and handle `DailyRequested` in `list_screen.py` by pushing the preview and surfacing a status-bar note when the frontmatter could not be read per [contracts/tui.md](./contracts/tui.md#opening-the-daily-note-from-the-bar)
- [ ] T028 [US1] Create `tests/integration/test_daily_note_tui.py` driving `/note` headless via `Pilot` for all three `DailyNote` outcomes, asserting the user lands in preview each time and the list insert happens only on creation

**Checkpoint**: US1 is complete. A user has a friction-free daily note from both front doors — the
highest-value half of §3.2 and the MVP boundary.

---

## Phase 4: User Story 2 - Write a research note, an idea, or a draft (Priority: P2)

**Goal**: `/note.<type> <description>` and `endpaper note new` create typed and untyped notes under
`notes/`, following the meeting rules exactly.

**Independent Test**: From a fresh workspace, create typed notes from both front doors and inspect
the files for location, name, frontmatter, title, and tags.

### Tests for User Story 2 ⚠️

- [ ] T029 [P] [US2] Create `tests/integration/test_create_note_cli.py` covering US2 scenarios 1–4: typed creation with tags, untyped creation omitting the type segment, same-day collision suffixing with the original untouched, `#tag` inside a quoted description, and repeated `--tag` preserving order while deduplicating
- [ ] T030 [P] [US2] Create `tests/integration/test_create_note_tui.py` covering US2 scenarios 1 and 5: `/note.research vendor landscape #procurement` creates a typed note, and `/note vendor landscape` creates an **untyped note** while leaving today's daily note neither created nor opened
- [ ] T031 [P] [US2] Create `tests/integration/test_note_parity.py` for US2 scenario 2: with a fixed `now` and a seeded id, the CLI and TUI create paths produce files identical in every byte except `id`, `created`, and `updated`
- [ ] T032 [P] [US2] Create `tests/integration/test_reserved_type.py` for US2 scenarios 6–7: `--type daily` and `/note.daily` are both rejected with exit 2 and a message naming `endpaper note today`, no file is created, and a type containing `/`, `\`, `.`, or a leading `-` is rejected so nothing is written outside `notes/`

### Implementation for User Story 2

- [ ] T033 [US2] Add the `note new` subparser to `src/endpaper/cli/main.py` with `description`, `--type`, and repeatable `--tag`, reusing the `#`-hazard wording from `meeting new`'s description text
- [ ] T034 [US2] Add a `_cmd_note_new` handler to `src/endpaper/cli/main.py` that calls `create_note` and prints the created path relative to the workspace root, exit 0
- [ ] T035 [US2] Extend `_run_command` in `src/endpaper/tui/command_bar.py` to implement the full `/note` grammar table in [contracts/tui.md](./contracts/tui.md#the-note-grammar): a non-empty rest creates a note with the type part, and `/note.<type>` with an empty description produces a bar-level usage error naming the missing description rather than falling through to core
- [ ] T036 [US2] Add a `create_note_and_track` method to `src/endpaper/tui/app.py` mirroring `create_meeting_and_track`, inserting the new note at the head of the in-memory notes list and recording `last_create_error` on `UsageError`
- [ ] T037 [US2] Handle the note `CreateRequested` variant in `src/endpaper/tui/list_screen.py`, landing the user in the preview of the new note and surfacing a create error in the status bar

**Checkpoint**: US1 and US2 both work independently. Notes can be captured from both front doors.

---

## Phase 5: User Story 3 - Find and read a note written weeks ago (Priority: P3)

**Goal**: `/notes` and `endpaper note list` present daily and typed notes as one collection, filtered
and previewed, never mixed with meetings.

**Independent Test**: Create a known set of daily and typed notes across dates, types, and tags, then
verify list ordering, live filtering, preview rendering, and each command-line filter.

### Tests for User Story 3 ⚠️

- [ ] T038 [P] [US3] Create `tests/integration/test_list_notes_cli.py` covering US3 scenarios 4–6: `--json` emits the seven-key schema, `--type`/`--tag`/`--since` combine conjunctively, `--type daily` selects exactly the daily notes, and an empty workspace prints `[]` and exits 0
- [ ] T039 [P] [US3] Create `tests/integration/test_collection_separation.py` for US3 scenario 7 and FR-018: `note list` returns no meeting, `meeting list` returns no note, and files under `notes/` that are not markdown plus directories under `notes/` other than `daily/` are ignored (FR-023)
- [ ] T040 [P] [US3] Create `tests/integration/test_list_notes_tui.py` covering US3 scenarios 1–3 and 8: daily and typed notes appear together sorted by date descending, live filtering narrows rows, `enter` opens a rendered preview, and switching between collections shows current content in each including notes created during the session
- [ ] T041 [P] [US3] Add a malformed-note case to `tests/integration/test_malformed.py`: a note with unparseable frontmatter is skipped with a warning on stderr, is never rewritten, and does not prevent other notes from listing (FR-021)

### Implementation for User Story 3

- [ ] T042 [US3] Rename the printers in `src/endpaper/cli/output.py` to document terms (`relative_path`, `print_documents_table`, `print_documents_json`) keeping the seven-key JSON schema byte-identical, and update `src/endpaper/cli/main.py`'s meeting handlers to the new names
- [ ] T043 [US3] Add the `note list` subparser with `--json`, `--type`, repeatable `--tag`, and `--since` to `src/endpaper/cli/main.py`, plus a `_cmd_note_list` handler that scans notes, prints warnings to stderr, applies `DocumentFilter`, and emits table or JSON per [contracts/cli.md](./contracts/cli.md#endpaper-note-list)
- [ ] T044 [US3] Change `src/endpaper/tui/app.py` to scan both collections at mount into `documents: dict[str, list[Document]]` keyed by collection name with an `active` name, and re-derive `visible_documents` from the active collection per [R6](./research.md#r6-holding-two-collections-in-a-one-screen-tui)
- [ ] T045 [US3] Add a `switch_collection(name)` method to `src/endpaper/tui/app.py` that sets `active` and clears the filter, and update `apply_filter`, `create_meeting_and_track`, and `create_note_and_track` to operate on the correct collection's list
- [ ] T046 [US3] Add `notes` to `VERBS` in `src/endpaper/tui/command_bar.py` and post a `CollectionRequested` message for both `/notes` and `/meetings`
- [ ] T047 [US3] Update `src/endpaper/tui/list_screen.py` to render rows from `Document` rather than `Meeting`, handle `CollectionRequested` by switching and resetting the selection to the top, and make the empty-state message name the active collection and its create command
- [ ] T048 [US3] Add an active-collection indicator to `src/endpaper/tui/status_bar.py` and render it from `list_screen.py`'s `_render_status`, so the collection is identifiable in both the status bar and the empty state (FR-025)

**Checkpoint**: All three user-facing stories work independently. Notes are capturable and findable.

---

## Phase 6: User Story 4 - An AI assistant works with notes unassisted (Priority: P4)

**Goal**: An assistant discovers the note commands from `AGENTS.md` and drives all three
non-interactively, with no prompt, no decoration, and parseable output.

**Independent Test**: With no human in the loop, run every note command with output redirected to a
file and confirm nothing blocks, nothing decorates, every result parses, and the guidance file
describes the commands used.

### Tests for User Story 4 ⚠️

- [ ] T049 [P] [US4] Extend `tests/contract/test_agents_md.py` for US4 scenario 1: the template documents `note today`, `note new`, and `note list`, states that `notes/daily/` holds one file per day and `notes/` holds typed notes, still states the `--tag` form explicitly, and stays within the line budget (≤58 lines)
- [ ] T050 [P] [US4] Extend `tests/contract/test_non_blocking.py` and `tests/contract/test_no_ansi.py` for US4 scenario 2: each of the three note commands run with redirected output terminates without waiting for input and writes zero `\x1b` bytes
- [ ] T051 [P] [US4] Extend `tests/contract/test_exit_codes.py` and `tests/contract/test_streams.py` for US4 scenario 3: reserved type and bad `--since` exit 2, no workspace exits 3, and warnings never reach stdout while data never reaches stderr
- [ ] T052 [P] [US4] Extend `tests/contract/test_json_schema.py` and `tests/contract/test_json_parses.py` for FR-020: `note list --json` emits objects with exactly the same seven keys as `meeting list --json`, and its stdout parses with no preamble or trailing text
- [ ] T053 [P] [US4] Create `tests/integration/test_no_migration.py` for US4 scenario 4: a workspace created by feature 001 with no notes in it returns an empty result from every note command rather than failing, with no migration step (SC-010)

### Implementation for User Story 4

- [ ] T054 [US4] Restructure `src/endpaper/core/templates/AGENTS.md.tmpl` per [R7](./research.md#r7-keeping-agentsmd-under-60-lines-while-documenting-twice-the-commands): give `notes/` and `notes/daily/` real descriptions in the layout block, retitle the frontmatter section to cover both kinds since the schema is identical, and document notes by their difference from meetings rather than repeating the tag rules — target ≤58 lines
- [ ] T055 [US4] Audit the three new commands in `src/endpaper/cli/main.py` against [contracts/cli.md](./contracts/cli.md): confirm every error path writes to stderr with the `endpaper: ` prefix and returns the right exit code, and that no handler writes to stdout on failure

**Checkpoint**: The command surface is safe for an assistant to drive unattended.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Properties that span the stories, and the release record

- [ ] T056 [P] Extend `tests/unit/test_path_budget.py` to cover `notes/YYYY-MM-DD-<type>-<slug>.md` and `notes/daily/YYYY-MM-DD.md`, asserting both stay within the Windows budget already established for meetings per [R9](./research.md#r9-windows-path-budget-for-notes)
- [ ] T057 [P] Extend `tests/fixtures/generate.py` to generate an N-note workspace including daily notes, and extend `tests/performance/test_scan.py` and `tests/performance/test_filter.py` to cover a 1,000-note workspace with both collections scanned at mount (SC-005)
- [ ] T058 [P] Update `tests/unit/test_command_bar_resolve_mode.py` for the `note` and `notes` verbs, including that a leading space still forces filter mode for the literal word "notes"
- [ ] T059 [P] Finalise the `0.0.2` section of `CHANGELOG.md`: the three new CLI commands, the additive `core` API change (new names added, none removed), and the `AGENTS.md` restructure
- [ ] T060 [P] Update `README.md` to mention daily notes and typed notes alongside meetings in the quickstart
- [ ] T061 Run the full `quickstart.md` validation pass end to end in a scratch workspace, including the concurrency and mtime checks in §1
- [ ] T062 Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src` and fix anything the refactor surfaced
- [ ] T063 Verify the TUI on the target terminals — Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux — with attention to the collection indicator and the empty-state message
- [ ] T064 Verify SC-011 on Windows, macOS, and Linux, including workspace paths containing spaces and non-ASCII characters

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS all user stories.** T016 is a hard gate
- **User Stories (Phases 3–6)**: All depend on Phase 2. US1, US2, and US3 touch overlapping adapter
  files, so see the conflict note below before parallelising
- **Polish (Phase 7)**: Depends on the user stories it verifies

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational. Independently testable and shippable
- **US2 (P2)**: Depends only on Foundational. Does not depend on US1 — typed notes work whether or
  not the daily note exists
- **US3 (P3)**: Depends only on Foundational for its CLI half. Its TUI half (T044–T048) restructures
  app state that US1's T025 and US2's T036 also touch — sequence those, or land T044–T045 first and
  have US1/US2 write against the new shape
- **US4 (P4)**: Verifies the surfaces US1–US3 create. Its tests can be written early but only pass
  once those stories land

### Within Each User Story

- Tests are written first and must fail before implementation
- Core (`notes.py`) before adapters
- CLI and TUI adapters are independent of each other and can be built in parallel
- Story complete and checkpointed before moving to the next priority

### File-conflict notes

These files are touched by more than one phase. Do not run their tasks in parallel:

| File | Tasks |
|---|---|
| `src/endpaper/core/models.py` | T005, T006, T007, T008 — sequential, same file |
| `src/endpaper/core/documents.py` | T010–T013 — sequential, same file |
| `src/endpaper/tui/app.py` | T025 (US1), T036 (US2), T044, T045 (US3) |
| `src/endpaper/tui/command_bar.py` | T024 (US1), T035 (US2), T046 (US3) |
| `src/endpaper/tui/list_screen.py` | T027 (US1), T037 (US2), T047, T048 (US3) |
| `src/endpaper/cli/main.py` | T023 (US1), T033, T034 (US2), T042, T043 (US3), T055 (US4) |

### Parallel Opportunities

**Phase 1**: T002, T003, T004 together after T001.

**Phase 2**: T017 runs alongside nothing else — everything before it is sequential within two files.

**Phase 3**: T018, T019, T020 together (one test file, but independent cases — or write them as one
task if the same author). T026 is parallel with T023 and T024: different files.

**Phase 4**: all four test tasks T029–T032 together — four independent files.

**Phase 5**: T038–T041 together. The CLI chain (T042, T043) runs in parallel with the TUI chain
(T044–T048): separate packages.

**Phase 6**: T049–T053 together — five independent contract test files.

**Phase 7**: T056–T060 together.

```bash
# Phase 4 tests, all at once:
Task: "tests/integration/test_create_note_cli.py — US2 scenarios 1-4"
Task: "tests/integration/test_create_note_tui.py — US2 scenarios 1, 5"
Task: "tests/integration/test_note_parity.py — US2 scenario 2"
Task: "tests/integration/test_reserved_type.py — US2 scenarios 6-7"
```

**Cross-story**: once Phase 2 completes, one developer can take US1's core (T021, T022) while another
takes US2's CLI (T033, T034) — different files, no shared state.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup
2. Phase 2: Foundational — blocks everything, and T016 is a hard gate
3. Phase 3: US1
4. **STOP and VALIDATE**: run quickstart.md §1, including the concurrency and mtime checks
5. Shippable — the daily note is the highest-value half of §3.2 on its own

### Incremental Delivery

1. Setup + Foundational → core is collection-parameterised, meetings unchanged
2. + US1 → **the daily note works**: one command, no decisions, idempotent
3. + US2 → typed notes join it
4. + US3 → notes become findable and readable
5. + US4 → the surface is safe for assistants to drive
6. + Polish → performance, path budget, cross-platform, changelog

US1 is the real shipping line for this feature. A user who has only the daily note has a complete,
useful capture surface; everything after it widens the product rather than completing it.

### Parallel Team Strategy

With two developers after Phase 2:

1. Developer A takes US1 end to end (core → CLI → TUI)
2. Developer B takes US2's core and CLI, then US3's CLI half
3. Rejoin for US3's TUI restructure (T044–T048), which touches the same app state as both
4. Either takes US4 and Polish

---

## Notes

- `[P]` tasks touch different files and have no incomplete dependencies
- Every acceptance scenario in spec.md maps to at least one test task (SC-006, Constitution VI)
- **T016 is the load-bearing task of Phase 2.** A refactor that needs test edits is not the refactor
  that was planned
- **T018's mtime assertion is the load-bearing test of US1.** Bytes alone would pass a no-op rewrite,
  which still costs a OneDrive user an upload — see [R10](./research.md#r10-test-strategy-for-the-file-did-not-change)
- `pilot.pause()` before every assertion in TUI tests — without it, assertions race the message pump
  and fail intermittently
- Neither `create_document` nor `open_daily_note` may ever open an existing file for writing. If a
  task seems to need that, it is the wrong task
- Commit after each task or logical group
