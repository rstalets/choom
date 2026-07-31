---

description: "Task list for feature implementation"
---

# Tasks: Document Links

**Input**: Design documents from `/specs/008-document-links/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: Included. Not optional here — Constitution Principle VI requires risk-based coverage of
every user-facing behaviour, and [quickstart.md](quickstart.md) already fixes which layer each
behaviour is verified at. Coverage is chosen for what could plausibly break, **not** one test per
acceptance scenario: the spec's 60-odd acceptance scenarios map to far fewer tests on purpose.

**Organization**: Grouped by user story, in the spec's priority order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US8)
- Every task names an exact file path

## Path Conventions

Single project: `src/endpaper/` and `tests/` at the repository root, per
[plan.md](plan.md#project-structure).

---

## ⚠️ Read this before planning parallel work

The template's default assumption is that user stories fan out independently. **This feature is a
chain, not a fan.** Saying so up front is more useful than discovering it at the checkpoint:

- **US1 (ids) genuinely comes first.** Every link carries an id, and the CLI's reserved `check`/`heal`
  words are only unambiguous because ids are prefixed (research R8).
- **US2 (the link primitive) is the trunk.** US3, US4, US6, and US7 all consume `core/links.py`.
- **US5 and US8 are the real parallel opportunities.** US5 (task `links:` field) touches
  `core/tasks.py` and needs nothing from `core/links.py` until its last task; US8 is README-only and
  can be done at any point by anyone.
- **US3 and US4 extend the same file** (`core/links.py`, `cli/main.py`), so running them in parallel
  means merge conflicts, not speed.

Stories remain independently *testable* — each phase has a checkpoint that stands on its own — but
they are not independently *startable*.

---

## Phase 1: Setup

**Purpose**: Establish the reference point and the one new file everything else lands in

- [ ] T001 Confirm the baseline is green before changing anything: `uv run pytest -q` (expect 407
      passed), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`. Record the count;
      every later phase is measured against it.
- [ ] T002 Create `src/endpaper/core/links.py` with a module docstring stating it holds the link
      primitive (scanner, resolver, path derivation, healer, inbound scan) and why those live
      together — see [plan.md](plan.md#project-structure) Structure Decision.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The types every later story passes around

**⚠️ CRITICAL**: US2 onward cannot begin until this phase is complete. US1 does not depend on it and
may run concurrently.

- [ ] T003 Add link types to `src/endpaper/core/models.py`: `Link`, `LinkTarget`, `LinkReport`
      dataclasses (`frozen=True, slots=True`) and the `LinkStatus` / `LinkDirection` `Literal`
      aliases; extend `ScanWarningReason` with `"link_dead"` and `"link_ambiguous"`. Field lists are
      fixed in [data-model.md](data-model.md#entities). One file, so not parallelisable.
- [ ] T004 Re-export the new names from `src/endpaper/core/__init__.py` and extend
      `tests/unit/test_core_imports.py` to guard them.

**Checkpoint**: Types exist; US2–US7 can begin.

---

## Phase 3: User Story 1 - Ids name their collection in full (Priority: P1) 🎯 MVP

**Goal**: Ids become `meeting_`, `note_`, `task_` prefixed, so every link written later inherits a
scheme that scales to new collections without a registry.

**Independent Test**: Create a meeting, note, and task in a fresh workspace and confirm each id
carries its collection's full name. Separately, confirm a workspace holding old-scheme ids still
lists, reads, and resolves, and that no file is rewritten.

### Tests for User Story 1

- [ ] T005 [P] [US1] Extend `tests/unit/test_collection.py` to assert new meeting, note, daily-note,
      and task ids carry the `meeting_` / `note_` / `task_` prefixes (US1 AC1–3).
- [ ] T006 [P] [US1] Extend `tests/integration/test_no_migration.py`: a workspace whose frontmatter
      and task lines carry old-scheme ids (`m_…`, `n_…`, `t_…`) still lists, reads, and resolves, and
      `tasks.md` is byte-identical before and after a read (US1 AC4, FR-013, SC-007).

### Implementation for User Story 1

- [ ] T007 [P] [US1] Change `MEETINGS = Collection("m_", …)` to `"meeting_"` in
      `src/endpaper/core/meetings.py`.
- [ ] T008 [P] [US1] Change `NOTES = Collection("n_", …)` to `"note_"` in
      `src/endpaper/core/notes.py`.
- [ ] T009 [US1] Update both id builders in `src/endpaper/core/text.py`: `new_meeting_id` to pass
      `"meeting_"`, and `new_task_id` to build `f"task_{secrets.token_hex(2)}"`. Same file, so after
      T007/T008 rather than beside them.
- [ ] T010 [US1] Update literal example ids across the **16 test modules** that carry them —
      `tests/contract/test_exit_codes.py`; `tests/integration/{test_cli_tui_parity,
      test_collection_separation,test_external_edits,test_task_cli,test_task_handedit,
      test_malformed}.py`; `tests/performance/test_task_scan.py`;
      `tests/unit/{test_collection,test_frontmatter,test_line_endings,test_save_atomic,
      test_stamp_updated,test_task_id,test_task_parse,test_task_render}.py`. Includes fixture ids
      (`id: m_1`) and generated ones (`f"id:t_{i:04x}"`). **Leave the deliberately-malformed
      `<!-- id:` fixture in `test_malformed.py` alone** — it carries no prefix and is testing the
      broken-comment path.
- [ ] T011 [US1] Update the prefix sentence and the frontmatter/task examples in
      `src/endpaper/core/templates/AGENTS.md.tmpl` so it states the current prefixes and no longer
      states the old ones (US1 AC5). Content additions to this file are T058; this task is only the
      prefix correction.
- [ ] T012 [P] [US1] Update literal example ids in `REQUIREMENTS.md` (§3.3, §4.6) and `CHANGELOG.md`.

**Checkpoint**: New ids are prefixed, old ids still resolve, nothing was migrated. Independently
shippable.

---

## Phase 4: User Story 2 - A link resolves, and repairs itself (Priority: P2)

**Goal**: The primitive. A link written by hand — with a path, without one, or with a wrong one —
resolves, and the path is corrected on the next save.

**Independent Test**: Write a fragment-only link by hand, confirm it resolves; save and confirm a
correct relative path appeared; move the target, save again, confirm the path was corrected.

### Tests for User Story 2

- [ ] T013 [P] [US2] Create `tests/unit/test_link_scan.py` — **the highest-risk code in the
      feature**. Cover ``` and `~~~` fences (closed, unclosed to EOF, and with info strings), inline
      code spans including equal-length multi-backtick runs, images, URL-scheme destinations,
      reference-style links, two links on one line, unclosed links, and angle-bracket destinations.
      A masking bug here silently rewrites a user's prose. Cases enumerated in
      [research.md](research.md#measurements).
- [ ] T014 [P] [US2] Create `tests/unit/test_link_paths.py` — table-driven `relative_destination`
      from every layout depth (collection `YYYY/MM`, `notes/daily/YYYY/MM`, root `tasks.md`, and a
      document outside the dated layout), forward slashes on every platform, and angle-bracket
      escaping for paths with spaces or parens (SC-005, FR-008).
- [ ] T015 [P] [US2] Create `tests/unit/test_link_resolve.py` — id-before-path ordering, old-prefix
      ids resolving unchanged, duplicate ids resolving deterministically with a `link_ambiguous`
      warning, and dead links returning a status rather than raising (FR-006, FR-013, R11).
- [ ] T016 [P] [US2] Create `tests/integration/test_link_heal.py` — save-time repair end to end: a
      fragment-only link gains a path, a path-only link gains a fragment, a stale path is corrected,
      a dead link beside a stale one is left byte-identical, and link text plus surrounding prose are
      unchanged (US2 AC1–8, SC-001, SC-002).

### Implementation for User Story 2

- [ ] T017 [US2] Implement `find_links(text, *, source, in_tasks_field=False)` in
      `src/endpaper/core/links.py`: the inline-link regex plus the fenced-block and code-span mask.
      Returns `Link` records carrying `start`/`end` offsets. Never raises. Grammar and exclusions are
      fixed in [contracts/link-format.md](contracts/link-format.md#grammar).
- [ ] T018 [US2] Implement `relative_destination(source, target)` in
      `src/endpaper/core/links.py` using `os.path.relpath` with `os.sep` replaced by `/`, plus the
      angle-bracket wrapper for destinations containing a space, paren, or angle bracket (R3, R4).
- [ ] T019 [US2] Implement `resolve_id` and `resolve_link` in `src/endpaper/core/links.py` — id
      first, path second; deterministic duplicate handling with a warning; documents only at this
      stage (tasks as targets arrive in T044).
- [ ] T020 [US2] Implement `heal_text(workspace, text, *, source)` in
      `src/endpaper/core/links.py` as a byte-level splice of destinations only, returning `text`
      unchanged when nothing is stale so callers can skip a write entirely (FR-026, FR-022).
- [ ] T021 [US2] Add the keyword-only `workspace: Workspace | None = None` parameter to
      `save_buffer` in `src/endpaper/core/editing.py`, healing before stamping `updated`, and add
      `warnings: tuple[ScanWarning, ...] = ()` to `SaveResult` in `src/endpaper/core/models.py`. A
      dead link never sets `ok=False`. The default keeps the four existing test call sites compiling
      (R5).
- [ ] T022 [US2] Pass the workspace from `src/endpaper/tui/edit_screen.py` (`_save`, line ~140) and
      surface `SaveResult.warnings` in the existing `⚠ …` status-bar form.
- [ ] T023 [US2] Re-export the links API from `src/endpaper/core/__init__.py`.

**Checkpoint**: Links resolve and repair themselves on save. This is the feature's trunk — US3, US4,
US6, and US7 all build on it.

---

## Phase 5: User Story 3 - Ask what points at a record (Priority: P3)

**Goal**: `endpaper links <id>` answers both directions, computed by scanning, with nothing stored.

**Independent Test**: Create a meeting and a note that links to it, then ask what points at the
meeting and confirm the note is listed with file, line, and link text.

### Tests for User Story 3

- [ ] T024 [P] [US3] Create `tests/contract/test_links_cli.py` — `links <id>` JSON keys, the
      `--direction` grouping shape, exit code 0 for an empty result and 1 for an unresolvable id,
      stdout/stderr separation, and no prompt or pager
      ([contracts/cli.md](contracts/cli.md#json-schema)).
- [ ] T025 [P] [US3] Create `tests/integration/test_links.py` — inbound and outbound end to end,
      including the two negative cases that make the candidate filter correct: an id appearing as
      plain prose is **not** an inbound link, and a record's own frontmatter `id:` is **not** a
      self-link (US3 AC6, AC7).
- [ ] T026 [P] [US3] Create `tests/performance/test_link_scan.py`, marked
      `@pytest.mark.performance` — inbound links for one id under 500 ms on a 6,000-document
      workspace (SC-006). This test is the standing justification for having no index; measured at
      155 ms in research R2.
- [ ] T027 [US3] Implement `inbound_links(workspace, target_id)` and
      `outbound_links(workspace, source)` in `src/endpaper/core/links.py`. Inbound reads each file's
      bytes, substring-tests for the id, and runs `find_links` only on hits — a hit is a *candidate*,
      never a result (FR-030).
- [ ] T028 [US3] Add the `links` subparser with `<id>`, `--json`, and
      `--direction out|in|both` (default `both`) to `src/endpaper/cli/main.py`, reserving `check` and
      `heal` in the id position, plus the `_cmd_links` handler.
- [ ] T029 [US3] Add `print_links_json` and `print_links_table` to `src/endpaper/cli/output.py` —
      tab-separated, no header, no colour on a non-TTY.
- [ ] T030 [US3] Wire exit codes for `links <id>` in `src/endpaper/cli/main.py`: 0 including an empty
      result, 1 when the id itself resolves to nothing, 2 for a bad `--direction`.

**Checkpoint**: Backlinks work from the command line with nothing persisted.

---

## Phase 6: User Story 4 - Audit and repair from the command line (Priority: P4)

**Goal**: `links check` reports stale and dead as distinct classes; `links heal` fixes every stale
link and touches no dead one.

**Independent Test**: Move a document and confirm `check` reports stale; delete one and confirm it
reports dead; run `heal --dry-run` then `heal` and confirm the reported set and the changed set match.

### Tests for User Story 4

- [ ] T031 [P] [US4] Extend `tests/contract/test_links_cli.py` with `check` and `heal`: the report
      schema, exit 1 when anything is stale or dead, exit 0 on a clean workspace, and
      `--dry-run` being non-blocking and write-free.
- [ ] T032 [P] [US4] Extend `tests/integration/test_link_heal.py`: `--dry-run` reports **exactly**
      the set `heal` then changes (the property that makes `heal` safe to run without reading a
      diff); dead links survive byte-identical beside repaired ones; and a workspace with nothing
      stale sees **zero writes and no `updated` movement** (SC-008, US4 AC4, AC5, AC8).
- [ ] T033 [US4] Implement `check_links(workspace, paths=())` and
      `heal_links(workspace, paths=(), *, dry_run=False)` in `src/endpaper/core/links.py`, returning
      `LinkReport` tuples. `heal_links` must not open a file for writing when nothing in it is stale.
- [ ] T034 [US4] Add the `check` and `heal` sub-subcommands with `[<path>…]`, `--json`, and
      `--dry-run` to `src/endpaper/cli/main.py`, plus handlers.
- [ ] T035 [US4] Add `print_link_reports_json` and `print_link_reports_table` to
      `src/endpaper/cli/output.py`, with `old_path`/`new_path` serialised as `null` where they do not
      apply.
- [ ] T036 [US4] Wire exit codes for `check` and `heal` in `src/endpaper/cli/main.py` per the table
      in [contracts/cli.md](contracts/cli.md#exit-codes).

**Checkpoint**: A workspace can be audited and repaired non-interactively.

---

## Phase 7: User Story 5 - A task remembers where it came from (Priority: P5)

**Goal**: A `links:` field on the task line, shaped exactly like `tags:`.

**Independent Test**: Hand-write a `links:` field on a task line, confirm the task still parses and
the link is reported in both directions; confirm a `tasks.md` with no `links:` anywhere is
byte-identical after a read/write cycle.

**Note**: This phase can start as soon as Phase 2 is done — only its last task (T044) needs
`core/links.py`. It is the best parallelisation opportunity in the feature.

### Tests for User Story 5

- [ ] T037 [P] [US5] Extend `tests/unit/test_task_parse.py`: a `links:` field with one and several
      ids; a malformed value warning and skipping only that line; and — importantly — that a line
      with **no** `links:` field parses exactly as before (US5 AC1, AC2, AC6, FR-016).
- [ ] T038 [P] [US5] Extend `tests/unit/test_task_render.py`: field order `id`, `type`, `tags`,
      `links`, `created`, with empty fields omitted (US5 AC4, FR-017).
- [ ] T039 [P] [US5] Extend `tests/integration/test_task_handedit.py`: a hand-written `links:` field
      survives a `task done` round-trip, every untouched line stays byte-identical, and `tasks.md`
      remains valid CommonMark (US5 AC3, AC8, SC-010).
- [ ] T040 [US5] Add `links: tuple[str, ...] = ()` to `Task` in `src/endpaper/core/models.py`.
- [ ] T041 [US5] Add `"links"` to `_RECOGNIZED_KEYS`, validate its values with `_IDVAL` mirroring the
      `tags` rule (split on `,`, reject empty), and populate `Task.links` in `parse_tasks` — all in
      `src/endpaper/core/tasks.py`. Note this also fixes a live trap: today an unrecognised key makes
      `_classify_body` return `malformed`, dropping the whole task from every listing (R7).
- [ ] T042 [US5] Add the `links` parameter to `_render_comment` and `render_task_line` in
      `src/endpaper/core/tasks.py`, emitted between `tags` and `created` and omitted when empty.
- [ ] T043 [US5] Include `links` in task JSON output in `src/endpaper/cli/output.py`
      (`print_tasks_json`).
- [ ] T044 [US5] Extend `src/endpaper/core/links.py` so tasks are first-class both ways: `resolve_id`
      resolves a `task_` id to its line in `tasks.md`, and `inbound_links` scans task `links:` fields
      as well as document bodies (US5 AC7).

**Checkpoint**: Tasks link to their source. This is what unblocks issue #21.

---

## Phase 8: User Story 6 - Insert a link without leaving the editor (Priority: P6)

**Goal**: `/link <search terms>` on its own line becomes a correct markdown link.

**Independent Test**: In the editor, submit `/link` with terms matching exactly one record and
confirm the line became a correct link; repeat with zero and several matches and confirm the typed
line survives both.

### Tests for User Story 6

- [ ] T045 [P] [US6] Extend `tests/unit/test_editor_commands.py`: `/link foo` parses to the `link`
      command with argument `foo`; a line that is not entirely the command falls through as ordinary
      text (FR-046).
- [ ] T046 [P] [US6] Extend `tests/integration/test_links.py` with the three `/link` outcomes — one
      match inserts, zero and several leave the line exactly as typed and report in the status bar —
      and assert the editor never changes state in any of them (US6 AC1–5).
- [ ] T047 [US6] Implement `find_link_targets(workspace, query)` in `src/endpaper/core/links.py`,
      reusing `match_document`'s case-insensitive substring rule so `/link` and the list filter never
      disagree about what "matches" means (R11).
- [ ] T048 [US6] Register `EditorCommand(name="link", argument="<search terms>", …)` in
      `src/endpaper/core/editor_commands.py`. `parse_line` needs no change — it dispatches off the
      table, and `/help` picks the entry up automatically.
- [ ] T049 [US6] Handle the `link` case in the `EditorCommandSubmitted` handler in
      `src/endpaper/tui/edit_screen.py`: save first, then replace the line on a single match, or
      leave it untouched and report otherwise.
- [ ] T050 [US6] Add the no-match and ambiguous-match status-bar strings to
      `src/endpaper/tui/status_bar.py`; the ambiguous one names candidates so the user can retype.

**Checkpoint**: Links can be authored without leaving the document.

---

## Phase 9: User Story 7 - See and follow links in the preview pane (Priority: P7)

**Goal**: A Links section in the preview pane — outbound above, inbound below — with one key to open
either.

**Independent Test**: Open a document with outbound links and confirm they are listed on open; expand
the inbound section and confirm what points at it is listed; press the open key on each.

### Tests for User Story 7

- [ ] T051 [P] [US7] Extend `tests/unit/test_footer_bindings.py` for the new preview bindings —
      every one of `l`, `enter`/`o`, and `esc` must be visible in the footer, and the links-section
      help string must fit 80 columns (Principle V, FR-051).
- [ ] T052 [P] [US7] Extend `tests/integration/test_links.py`: outbound links render on open with no
      workspace scan; inbound links appear only once the section is expanded; a record nothing points
      at says so rather than rendering empty; opening a dead link reports and does not change the
      view (US7 AC1–5).
- [ ] T053 [US7] Render the Links section in `src/endpaper/tui/rendering.py` — outbound above,
      inbound below, dead links shown with their unresolvable id rather than hidden. Layout sketch in
      [contracts/tui.md](contracts/tui.md#rendering).
- [ ] T054 [US7] Add the collapsible region and its bindings (`l` toggle, `↑↓`/`jk` move,
      `enter`/`o` open, `esc` collapse) to `src/endpaper/tui/preview_screen.py`, computing outbound
      links on mount and inbound links only on first expansion (FR-048, FR-049).
- [ ] T055 [US7] Add `l links` to `PREVIEW_HELP` and a separate links-section help string in
      `src/endpaper/tui/status_bar.py` — swap the string rather than appending, so the footer never
      overflows (53 → 63 chars, still inside 80).
- [ ] T056 [US7] Implement opening a selected link from `src/endpaper/tui/preview_screen.py` into
      whichever collection the target lives in, including a task target in `tasks.md` (FR-050).

**Checkpoint**: All seven behavioural stories are complete.

---

## Phase 10: User Story 8 - The workspace has to actually be on disk (Priority: P8)

**Goal**: The README warns that a cloud-synced workspace must be pinned to local disk.

**Independent Test**: Read the README's workspace-creation section and confirm it names all four
providers and the exact setting each needs.

- [ ] T057 [P] [US8] Add the cloud-storage warning to the "Create a workspace" section of
      `README.md`, naming OneDrive ("Always keep on this device"), Dropbox ("Make available
      offline"), Google Drive ("Available offline"), and iCloud Drive (keep downloaded; do not let
      Optimize Storage evict it), and stating **why**: there is no index, so the files have to be
      present — for endpaper and for the assistant reading the folder (FR-053).

**Checkpoint**: Every user story is delivered.

---

## Phase 11: Polish & Cross-Cutting Concerns

- [ ] T058 Add the link syntax, the task `links:` field, and the three `endpaper links` commands to
      `src/endpaper/core/templates/AGENTS.md.tmpl`, **and tighten the file back to ≤ 60 lines**. It
      is 63 lines today, so this is a net reduction, not an append. The reclamation plan (fold the
      frontmatter example, collapse the duplicated list-command flags, halve the exit-code section)
      is worked out in [research.md](research.md#r9-the-agentsmd-line-budget). Acceptance:
      `wc -l < src/endpaper/core/templates/AGENTS.md.tmpl` returns ≤ 60.
- [ ] T059 [P] Record all four public-API changes in `CHANGELOG.md` with their version: the id prefix
      scheme, the task line format gaining `links`, the new `endpaper links` commands, and the new
      JSON schema (FR-054).
- [ ] T060 [P] Update `REQUIREMENTS.md` §3.3 and §4.6 for the task line's `links` field and the link
      format, so the requirements document and the shipped behaviour agree.
- [ ] T061 Run the full gate: `uv run ruff format --check .`, `uv run ruff check .`,
      `uv run mypy`, `uv run pytest -q`. Expect the 407 baseline plus this feature's tests, all green.
- [ ] T062 Walk [quickstart.md](quickstart.md) Scenarios 1–8 by hand against a scratch workspace,
      including the code-fence non-rewrite check in Scenario 2 — the case that would silently corrupt
      a note explaining link syntax.
- [ ] T063 Verify the new preview bindings from `src/endpaper/tui/preview_screen.py` on the target
      terminals — launch `uv run endpaper` in a workspace, open a document, and exercise `l`,
      `↑↓`/`jk`, `enter`/`o`, and `esc` on Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside
      tmux. Confirm the footer text from `src/endpaper/tui/status_bar.py` is not truncated at 80
      columns (constitution, Development Workflow).
- [ ] T064 [P] Extend `tests/integration/test_unicode_paths.py` and `tests/unit/test_path_budget.py`
      to cover this feature: a workspace path with spaces and non-ASCII characters round-tripping a
      link, a destination requiring the angle-bracket form from `relative_destination`, and the
      worst-case relative destination (117 chars, research R3) staying well inside the Windows
      260-character budget.
- [ ] T065 Confirm SC-011 by hand: run `uv run endpaper init` in an empty directory, give a fresh
      assistant only the generated `AGENTS.md` from that workspace, and ask it to write a link, ask
      what points at a record, and repair stale paths. It should need nothing else. This is the real
      test of T058 — if the assistant has to guess, the template is wrong regardless of its line
      count.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup. Blocks US2–US7. **Does not block US1 or US8.**
- **US1 (Phase 3)**: after Setup. Should land first — see the note at the top of this file.
- **US2 (Phase 4)**: after Phase 2. The trunk.
- **US3, US4, US6, US7**: after US2.
- **US5 (Phase 7)**: after Phase 2 for T037–T043; T044 additionally needs US2 and US3.
- **US8 (Phase 10)**: no dependencies at all.
- **Polish (Phase 11)**: after every story it documents. T058 needs US1–US6 to describe them
  accurately.

### Story dependency graph

```
Setup ──┬── US1 (ids) ──────────────────────────────────────┐
        │                                                    │
        └── Foundational ──┬── US2 (primitive) ──┬── US3 ────┼── Polish
                           │                     ├── US4     │
                           │                     ├── US6     │
                           │                     └── US7     │
                           └── US5 (task links) ──── T044 ───┘

US8 (README) ── independent of everything, any time
```

### Within each story

- Tests are written before the implementation they cover and must fail first.
- In `core/links.py`, order is scanner → paths → resolver → healer; each builds on the previous.
- Core before adapters, always. `cli/` and `tui/` only ever call into `core`.

### Parallel Opportunities

- **T007 and T008** — different collection files, genuinely parallel.
- **All test-authoring tasks marked [P] within a phase** — different files.
- **US5 alongside US2** — the strongest opportunity; different modules (`core/tasks.py` vs
  `core/links.py`) until T044.
- **US8 (T057)** and the documentation tasks **T059/T060** — README, CHANGELOG, and REQUIREMENTS are
  three separate files.
- **Not parallel despite appearances**: T017–T020 (all `core/links.py`), T028/T030 and T034/T036 (all
  `cli/main.py`), T029 and T035 (both `cli/output.py`).

---

## Parallel Example: User Story 2

```bash
# The four test modules are independent files — write them together:
Task: "tests/unit/test_link_scan.py — scanner and mask"      # T013
Task: "tests/unit/test_link_paths.py — relative destinations" # T014
Task: "tests/unit/test_link_resolve.py — resolution order"    # T015
Task: "tests/integration/test_link_heal.py — save-time repair" # T016

# Implementation is strictly sequential — one module, building on itself:
# T017 find_links → T018 relative_destination → T019 resolve → T020 heal_text
```

---

## Implementation Strategy

### MVP scope

**US1 alone is the smallest shippable increment**, and it is deliberately first because it is a
prerequisite rather than a feature: changing the id scheme after real workspaces hold real ids is a
migration, and endpaper is pre-release. It delivers a self-describing id scheme that new collections
can join without arbitration.

**The first increment a user would notice is US1 + US2** — links that resolve and repair themselves.
If only two phases ship, ship those.

### Incremental delivery

1. Setup + Foundational → types in place
2. **US1** → prefixed ids, nothing migrated → validate, ship
3. **US2** → the primitive; links resolve and self-heal → validate, ship
4. **US3** → backlinks answerable from the CLI
5. **US4** → audit and repair
6. **US5** → tasks carry provenance (unblocks #21)
7. **US6, US7** → authoring and following in the TUI
8. **US8 + Polish** → documentation, gates, manual verification

### Parallel team strategy

Real, but narrower than the template's default. With two developers: one takes US1 then the US2→US3→
US4 trunk; the other takes US5 (stopping before T044) and US8, then joins on US6/US7. A third
developer adds little until US2 lands, because everything else consumes it.

---

## Notes

- `[P]` means different files and no dependency on incomplete work.
- Every task names its file. Where a task touches a file another task also touches, it is sequenced
  rather than marked `[P]` — the conflicts are called out above.
- Commit after each task or logical group; stop at any checkpoint to validate a story on its own.
- The baseline is **407 tests**. Any phase that reduces it has broken something.
