---

description: "Task list for 001-meeting-notes"
---

# Tasks: Meeting Notes (with project scaffolding)

**Input**: Design documents from `/specs/001-meeting-notes/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks are **required** for this feature, not optional. SC-006 requires 100% of
acceptance scenarios covered by automated tests that run with no terminal attached, and Constitution
Principle VI requires every acceptance criterion to map to at least one test.

**Organization**: Tasks are grouped by user story so each can be implemented and verified
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

Single project, `src/` layout (FR-006). Package code under `src/endpaper/`, tests under `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, packaging, and quality tooling

- [X] T001 Create `pyproject.toml` at repository root: hatchling backend, `requires-python = ">=3.11"`, runtime deps `textual>=8.2` and `PyYAML>=6.0`, console script `endpaper = "endpaper.cli.main:main"`, and a `dev` extra with pytest, pytest-asyncio, ruff, mypy, types-PyYAML
- [X] T002 Create the package skeleton: `src/endpaper/__init__.py` (with `__version__ = "0.0.1"`), `src/endpaper/__main__.py`, `src/endpaper/core/__init__.py`, `src/endpaper/cli/__init__.py`, `src/endpaper/tui/__init__.py`
- [X] T003 [P] Configure ruff format and lint under `[tool.ruff]` in `pyproject.toml`
- [X] T004 [P] Configure mypy in strict mode for `src` under `[tool.mypy]` in `pyproject.toml`
- [X] T005 [P] Configure pytest and pytest-asyncio (`asyncio_mode = "auto"`) under `[tool.pytest.ini_options]` in `pyproject.toml`
- [X] T006 [P] Create `CHANGELOG.md` at repository root with an Unreleased 0.0.1 section
- [X] T007 [P] Rewrite `README.md` — it currently names the project "cairn"; replace with the endpaper name, a one-paragraph description, and the `uv tool install endpaper` quickstart
- [X] T008 Create `tests/conftest.py` with a `tmp_workspace` fixture, a frozen-clock fixture feeding `create_meeting(now=...)`, and a seeded-id fixture for deterministic filenames
- [X] T009 Add a minimal `main()` in `src/endpaper/cli/main.py` handling only `--version`, then verify `uv sync --all-extras` and `uv run endpaper --version` both exit 0

**Checkpoint**: Environment installs, entry point resolves, quality gates run clean on an empty tree.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `core` primitives every user story depends on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T010 [P] Create `src/endpaper/core/errors.py`: `EndpaperError` with an `exit_code` ClassVar, plus `NotFoundError` (1), `UsageError` (2), `WorkspaceError` (3) per [contracts/core-api.md](./contracts/core-api.md)
- [X] T011 [P] Create `src/endpaper/core/models.py`: frozen slotted `Workspace`, `Meeting`, `ScanWarning`, `MeetingFilter` dataclasses per [data-model.md](./data-model.md)
- [X] T012 Create `src/endpaper/core/text.py` with `slugify()` implementing the five-step algorithm in [data-model.md](./data-model.md#slug-algorithm-fr-016)
- [X] T013 Add `parse_tags()` to `src/endpaper/core/text.py`: strip `#tag` tokens from anywhere, collapse resulting whitespace, preserve title casing
- [X] T014 Add `new_meeting_id()` to `src/endpaper/core/text.py` producing `m_YYYYMMDD_` + 8 lowercase hex from `secrets.token_hex(4)`
- [X] T015 Create `src/endpaper/core/frontmatter.py` with `read_frontmatter()`: `yaml.safe_load` followed by coercion of every scalar back to `str`, undoing YAML 1.1 booleans and datetimes per [research.md R2](./research.md#r2-frontmatter-parsing-and-writing)
- [X] T016 Add `render_frontmatter()` to `src/endpaper/core/frontmatter.py`: deterministic emitter, six keys in fixed order, title and tags always double-quoted, timestamps unquoted, no line wrapping at any title length
- [X] T017 Populate `src/endpaper/core/__init__.py` re-exporting exactly the public API listed in [contracts/core-api.md](./contracts/core-api.md)
- [X] T018 [P] Create `tests/unit/test_slugify.py` covering the slug table in data-model.md: unicode folding, emoji-only fallback to `untitled`, 40-char truncation, trailing-hyphen strip after the cut
- [X] T019 [P] Create `tests/unit/test_parse_tags.py`: tags at start/middle/end, repeated tags, no tags, tags-only description
- [X] T020 [P] Create `tests/unit/test_frontmatter.py`: YAML 1.1 coercion cases (`no`/`on`/`off`/`y` stay strings, bare timestamp stays a string, `3.10` stays a string), emitter determinism, and a long-title round-trip proving no 80-column wrap
- [X] T021 Create `tests/unit/test_core_imports.py` asserting `endpaper.core` imports none of `argparse`, `textual`, `rich`, or `sys.stdout` — Constitution gate I, enforced rather than trusted

**Checkpoint**: Core primitives exist and are unit-tested. User stories can now proceed.

---

## Phase 3: User Story 1 - Install endpaper and get a workspace (Priority: P1) 🎯 MVP

**Goal**: A user with no admin rights can install endpaper, create a workspace, and launch the interface.

**Independent Test**: On a clean machine, install, run `endpaper init` in an empty directory, confirm the five paths exist, and launch the TUI with a bare command.

### Implementation for User Story 1

- [X] T022 [P] [US1] Create `src/endpaper/core/templates/AGENTS.md.tmpl` — folder layout, frontmatter schema, meeting commands, explicit `--tag` documentation, at most ~60 lines
- [X] T023 [US1] Implement `find_workspace()` in `src/endpaper/core/workspace.py`: walk ancestors for `.endpaper/config.toml`, stop at filesystem root, raise `WorkspaceError` when absent or when the schema version is unsupported
- [X] T024 [US1] Implement `init_workspace()` in `src/endpaper/core/workspace.py` creating `meetings/`, `notes/daily/`, `tasks.md`, `AGENTS.md`, and writing `.endpaper/config.toml` **last** so an interrupted init leaves a non-workspace
- [X] T025 [US1] Configure hatchling in `pyproject.toml` to ship `src/endpaper/core/templates/*.tmpl` as package data
- [X] T026 [US1] Implement `EndpaperError` → exit-code mapping and traceback suppression in `src/endpaper/cli/main.py`, letting unexpected exceptions still traceback
- [X] T027 [US1] Implement bare-argv detection in `src/endpaper/cli/main.py`: empty `sys.argv[1:]` dispatches to the TUI before argparse runs, with exit 3 when no workspace is found or stdout is not a TTY
- [X] T028 [US1] Build the argparse parser and `meeting` subcommand group in `src/endpaper/cli/main.py`
- [X] T029 [US1] Implement `endpaper init` in `src/endpaper/cli/main.py`: print the workspace root to stdout, exit 0; exit 3 and write nothing when already a workspace
- [X] T030 [P] [US1] Create `src/endpaper/tui/app.tcss` with the list/preview two-pane layout
- [X] T031 [US1] Create `src/endpaper/tui/app.py` with `EndpaperApp`: header, footer, `ctrl+q` quit, and no rebinding of `ctrl+c` or `ctrl+q`
- [X] T032 [US1] Create `src/endpaper/tui/list_screen.py` rendering an empty-state message and the footer binding set

### Tests for User Story 1

- [X] T033 [P] [US1] Create `tests/integration/test_init.py` covering US1 scenarios 2 and 3: all five paths created and exit 0; re-init exits 3 and modifies nothing
- [X] T034 [P] [US1] Create `tests/integration/test_no_workspace.py` covering US1 scenario 5: bare `endpaper` outside a workspace exits 3 with guidance and does not open a TUI
- [X] T035 [P] [US1] Create `tests/integration/test_tui_launch.py` covering US1 scenario 4 headless via `App.run_test(size=(80, 24))`, with `pilot.pause()` before assertions
- [X] T036 [P] [US1] Create `tests/contract/test_agents_md.py` covering US4 scenario 1's structural half: generated `AGENTS.md` is ≤60 lines and mentions `--tag`

**Checkpoint**: A user can install, init, and launch. This is the MVP.

---

## Phase 4: User Story 2 - Capture a meeting note (Priority: P2)

**Goal**: One short command from either front door produces a correctly named, correctly stamped file.

**Independent Test**: From a fresh workspace, create meetings via CLI and TUI; inspect location, filename, frontmatter, and title on disk.

### Implementation for User Story 2

- [X] T037 [US2] Implement `create_meeting()` in `src/endpaper/core/meetings.py` using `os.open` with `O_CREAT | O_EXCL | O_WRONLY`, per [research.md R6](./research.md#r6-file-creation-must-never-overwrite)
- [X] T038 [US2] Implement filename derivation in `src/endpaper/core/meetings.py`: date-first, type segment omitted when untyped, candidate suffixes `-2`, `-3`, … advanced on `FileExistsError`
- [X] T039 [US2] Add validation to `src/endpaper/core/meetings.py`: `UsageError` for an empty post-strip description, and for a `type` or tag containing `/`, `\`, `.`, or a leading `-`
- [X] T040 [US2] Implement `endpaper meeting new` in `src/endpaper/cli/main.py` with `--type` and repeatable `--tag`, printing the created path relative to the workspace root with forward slashes
- [X] T041 [US2] Document the `#`-is-a-shell-comment hazard in `meeting new` help text in `src/endpaper/cli/main.py`, naming `--tag` as the supported form
- [X] T042 [US2] Create `src/endpaper/tui/command_bar.py`: `/` opens the bar, first-token stem is looked up in a closed verb registry, and the footer shows `[filter]` or `[command: <verb>]` live
- [X] T043 [US2] Wire command mode in `src/endpaper/tui/command_bar.py` to `core.create_meeting`, running only on `enter`, with inline `#tag` parsing
- [X] T044 [US2] Create `src/endpaper/tui/preview_screen.py` using `textual.widgets.Markdown`, with `esc` returning to the list and no edit key advertised in the footer (FR-037)
- [X] T045 [US2] Land the user in preview of the newly created file after a TUI create, in `src/endpaper/tui/app.py`

### Tests for User Story 2

- [X] T046 [P] [US2] Create `tests/integration/test_create_cli.py` covering US2 scenarios 2, 4, 5, 6: path on stdout, untyped filename, quoted `#tag` extraction, repeated `--tag` order and dedup
- [X] T047 [P] [US2] Create `tests/integration/test_create_tui.py` covering US2 scenarios 1 and 7 headless: inline tags anywhere in the description, none leaking into the title
- [X] T048 [P] [US2] Create `tests/integration/test_create_parity.py` covering US2 scenario 2: CLI and TUI outputs diff clean after masking `id`, `created`, `updated`
- [X] T049 [P] [US2] Create `tests/integration/test_collision.py` covering US2 scenario 3: two files, first byte-unchanged, suffixes continuing past `-9`
- [X] T050 [P] [US2] Create `tests/unit/test_create_validation.py`: empty-slug fallback to `untitled`, and a path-traversal `type` rejected with exit 2 before any file is written

**Checkpoint**: Capture works from both front doors. US1 and US2 together are shippable.

---

## Phase 5: User Story 3 - Find a meeting from last month (Priority: P3)

**Goal**: Meetings are listed newest-first and narrow as the user types, in both front doors.

**Independent Test**: Create a known set across dates, types, and tags; verify ordering, live filtering, and each CLI filter.

### Implementation for User Story 3

- [X] T051 [US3] Implement `scan_meetings()` in `src/endpaper/core/meetings.py` following the eight-step tolerant scan in [data-model.md](./data-model.md#reading-the-tolerant-scan) — never raises, returns `ScanWarning` as data, never rewrites a skipped file
- [X] T052 [US3] Implement sorting in `src/endpaper/core/meetings.py`: `created` descending, ties broken by `path` ascending for total ordering
- [X] T053 [US3] Implement `filter_meetings()` in `src/endpaper/core/meetings.py` applying type, tags, and since conjunctively
- [X] T054 [US3] Implement `match_meeting()` in `src/endpaper/core/meetings.py` as a pure case-insensitive substring test over title, type, and tags
- [X] T055 [US3] Create `src/endpaper/cli/output.py` with tab-separated and JSON emitters, forward-slash relative paths on every platform, and `ensure_ascii=False`
- [X] T056 [US3] Implement `endpaper meeting list` in `src/endpaper/cli/main.py` with `--json`, `--type`, repeatable `--tag`, and `--since`
- [X] T057 [US3] Validate `--since` as an ISO date in `src/endpaper/cli/main.py`, raising `UsageError` (exit 2) and listing nothing on a bad value
- [X] T058 [US3] Populate the meeting list from a single startup scan held in memory for the session in `src/endpaper/tui/app.py`, appending on create rather than re-scanning
- [X] T059 [US3] Implement row rendering (date, type, title, tags) and `↑`/`↓`/`j`/`k` navigation that stops at both ends without wrapping, in `src/endpaper/tui/list_screen.py`
- [X] T060 [US3] Implement filter mode in `src/endpaper/tui/command_bar.py`: every keystroke narrows the in-memory list via `core.match_meeting`, with zero disk access per keystroke
- [X] T061 [US3] Wire `enter` → preview and `esc` → list in `src/endpaper/tui/list_screen.py`
- [X] T062 [US3] Surface the scan warning count in the footer in `src/endpaper/tui/app.py`

### Tests for User Story 3

- [X] T063 [P] [US3] Create `tests/integration/test_list_cli.py` covering US3 scenarios 4, 5, 6: JSON array shape, conjunctive filters, empty workspace exits 0 with `[]`
- [X] T064 [P] [US3] Create `tests/integration/test_list_tui.py` covering US3 scenarios 1, 2, 3 headless: date-descending order, live narrowing, navigation stopping at the ends
- [X] T065 [P] [US3] Create `tests/integration/test_malformed.py` covering FR-033: a malformed file is skipped, warned on stderr, absent from output, and **byte-identical before and after** the run
- [X] T066 [P] [US3] Create `tests/contract/test_json_schema.py` asserting exactly the seven keys, `""` not null for untyped, `[]` not null for no tags, and forward slashes in `path`

**Checkpoint**: All three human-facing stories work independently.

---

## Phase 6: User Story 4 - An AI assistant works unassisted (Priority: P4)

**Goal**: Every command is safe to drive from a pipe with no human present.

**Independent Test**: Run every command with output redirected to a file; nothing blocks, nothing decorates, every result parses.

### Implementation for User Story 4

- [X] T067 [US4] Finalize the content of `src/endpaper/core/templates/AGENTS.md.tmpl` against the real command surface, keeping it ≤60 lines and free of anything the README already says
- [X] T068 [US4] Audit every write in `src/endpaper/cli/` so data goes to stdout and diagnostics to stderr, never interleaved

### Tests for User Story 4

- [X] T069 [P] [US4] Create `tests/contract/test_no_ansi.py` asserting zero `\x1b` bytes in redirected stdout for every command (US4 scenario 2)
- [X] T070 [P] [US4] Create `tests/contract/test_streams.py` asserting scan warnings reach stderr while stdout stays a clean JSON array (US4 scenario 3)
- [X] T071 [P] [US4] Create `tests/contract/test_exit_codes.py` covering 0, 1, 2, and 3 across the whole command surface
- [X] T072 [P] [US4] Create `tests/contract/test_non_blocking.py` running every command under a timeout with stdin closed, asserting none hangs (US4 scenario 2)
- [X] T073 [P] [US4] Create `tests/contract/test_json_parses.py` asserting stdout parses with no preamble, banner, or trailing text (US4 scenario 4)

**Checkpoint**: The AI-facing contract is enforced by tests, not by good intentions.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T074 [P] Create `tests/fixtures/generate.py` producing an N-meeting workspace for performance runs
- [X] T075 [P] Create `tests/performance/test_scan.py` asserting a 1,000-meeting scan completes under 2s (SC-004)
- [X] T076 [P] Create `tests/performance/test_filter.py` asserting filtering 1,000 meetings completes under 100ms (SC-005)
- [X] T077 [P] Create `tests/unit/test_path_budget.py` asserting worst-case generated paths stay ≤120 characters below the workspace root, per [research.md R10](./research.md#r10-windows-path-length)
- [X] T078 [P] Create `tests/integration/test_unicode_paths.py` exercising workspace paths with spaces and non-ASCII characters (FR-043)
- [X] T079 Run the full quality gates from [quickstart.md](./quickstart.md): `ruff format --check`, `ruff check`, `mypy src`, `pytest`
- [X] T080 Walk quickstart.md scenarios 1–4 by hand against a real terminal
- [ ] T081 Verify the TUI on Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux (Constitution: Development Workflow)
- [X] T082 Update `CHANGELOG.md` recording the 0.0.1 CLI contract: command surface, the seven JSON keys, and exit codes 0/1/2/3

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **blocks all user stories**
- **User Stories (Phase 3–6)**: All depend on Foundational
- **Polish (Phase 7)**: Depends on all desired user stories

### User Story Dependencies

Unlike the usual pattern, these stories are **not** fully parallel — the spec's own priorities
describe a chain, and pretending otherwise would produce tasks that cannot run:

- **US1 (P1)**: Depends only on Foundational. Truly independent.
- **US2 (P2)**: Needs a workspace to write into, so it depends on US1's `find_workspace`.
- **US3 (P3)**: Needs files to list, so it is verified against US2's output. Its CLI half (T051–T057) can be built in parallel with US2 using hand-written fixture files.
- **US4 (P4)**: Audits the surface US1–US3 expose, so it comes last. Its test files (T069–T073) can be written earlier and left failing.

### Within Each User Story

- Core functions before the adapters that call them
- CLI and TUI adapters are peers and can be built in parallel once core lands
- Tests within a story are all `[P]` — separate files, no shared state

---

## Parallel Opportunities

**Phase 1**: T003, T004, T005, T006, T007 — five different config and doc targets.

**Phase 2**: T010 and T011 together; then T018, T019, T020 together once `text.py` and
`frontmatter.py` exist.

**Phase 3**: T022 and T030 together (template and stylesheet touch nothing else); all four tests
T033–T036 together.

```bash
# Phase 3 tests, all at once:
Task: "tests/integration/test_init.py — US1 scenarios 2, 3"
Task: "tests/integration/test_no_workspace.py — US1 scenario 5"
Task: "tests/integration/test_tui_launch.py — US1 scenario 4"
Task: "tests/contract/test_agents_md.py — AGENTS.md structure"
```

**Phase 4**: T046–T050 together after T037–T045 land.

**Phase 5**: the CLI chain (T055–T057) and the TUI chain (T058–T062) are separate files and run in
parallel once T051–T054 exist. Tests T063–T066 together.

**Phase 6**: T069–T073 together — five independent contract test files.

**Phase 7**: T074–T078 together.

**Cross-story**: once Foundational completes, one developer can take US1's TUI shell (T030–T032)
while another takes core meetings (T037–T039), since they share no files.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1: Setup
2. Phase 2: Foundational — blocks everything
3. Phase 3: US1
4. **STOP and VALIDATE**: install, init, launch on a clean machine
5. Publishable to TestPyPI at this point

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. + US1 → installs, inits, launches (MVP)
3. + US2 → **the product's premise works**: one command, one note
4. + US3 → notes become findable
5. + US4 → the surface is safe for assistants to drive
6. + Polish → performance, cross-platform, changelog

US2 is the real shipping line. After it, endpaper does the thing the requirements open with — a file
exists before anyone finishes joining the call. US1 alone is scaffolding a user can see.

---

## Notes

- `[P]` tasks touch different files and have no incomplete dependencies
- Every acceptance scenario in spec.md maps to at least one test task (SC-006, Constitution VI)
- `pilot.pause()` before every assertion in TUI tests — without it, assertions race the message pump and fail intermittently
- Commit after each task or logical group
- Constitution gate I is enforced by T021, not by convention. If it fails, an adapter has leaked into `core`
- T065's byte-comparison is the load-bearing test for Principle IV: a file we could not parse is a file we did not touch
