# Implementation Plan: Completed Tasks Leave the Open List

**Branch**: `019-completed-tasks-partition` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-completed-tasks-partition/spec.md`

## Summary

Completing a task moves its record out of `tasks.md` into `tasks/done/YYYY/MM/YYYY-MM-DD-done.md` for
the day it was completed; reopening it moves the record back. `tasks.md` becomes the open list.

The work is a new core module, `choom.core.task_store`, plus surgical changes to four existing core
modules and two adapters. Core decides where a record lives and how it gets there; the adapters
choose which read they want and print the result.

Four decisions carry the design:

1. **`tasks.md` is the canonical address of the task collection.** A task link's derived path is the
   path to `tasks.md`, whichever file currently holds the record. This is what makes the feature
   free of collateral writes: no mirror goes stale, `links heal` has nothing to rewrite, and no
   document the user did not open is touched. It works because `find_mirrors` already gates purely on
   `link.target_id.startswith("task_")` (`mirrors.py:86`) and never consults a path — resolution has
   always been by id, and §3.3 already declares the path "derived, not authored". The cost, stated
   out loud rather than buried: for a completed task the path names the collection, not the file
   holding the line, so following it in an external markdown viewer lands in `tasks.md`. That is
   accepted because the `#id` fragment was never a resolvable anchor in an external viewer anyway,
   and the alternative — rewriting mirrors across the vault on every toggle — is the outcome
   Principle IV exists to prevent.
2. **The move is two byte-level splices, never a re-render** (research R2). The state character, and
   `completed:<ISO>` into the metadata comment. Body-span lines are copied verbatim.
3. **Destination written first, source second, in both directions** (research R3). Of the two
   possible orderings, only this one cannot lose a line: its worst reachable failure leaves the
   record in *both* files, which is the already-detected duplicate-id state that every read and write
   path in the tree already refuses to act on.
4. **Nothing in an existing workspace moves unprompted.** Completed records already sitting in
   `tasks.md` stay there, still list in every done view, and move only on a real state transition or
   through the explicitly-invoked `task tidy` (P3, droppable).

**This feature introduces two regressions in shipped behaviour, and this plan owns fixing both.**
They are not observations; they are work items with named tests, and both are recorded under gate IV:

- **Bug 1 — `ctrl+t` orphans a completed record.** `plan_mirror_deletion` reads
  `workspace.tasks_file` directly (`mirrors.py:397`). Once completed records live elsewhere, the id
  resolves to nothing, the plan falls through to `line_only` (`mirrors.py:466`), the TUI removes the
  document line, and `commit_mirror_deletion` writes nothing. The user's line is gone and the record
  survives, unreferenced. Fix in research R6; regression test in the integration file.
- **Bug 2 — every completed mirror reports dead.** `reconcile_on_open` resolves through
  `_load_tasks_or_warning` → `load_tasks` and treats an unresolved id as dead
  (`mirrors.py:587-591`): box left `[ ]`, one warning per completed task, per open. Fix in research
  R5; regression test in the integration file.

**No new dependency, no new setting, no new CLI command** except the droppable P3 `task tidy`, **no
new key binding, no new screen.** Two `--json` keys are added and none is renamed, retyped, or
removed.

## Technical Context

**Language/Version**: Python 3.11+ (CI runs 3.11 and 3.13).

**Primary Dependencies**: none added. `textual==8.2.8` unchanged. Standard library only in the new
module — `os.scandir` for the store walk and the tick fingerprint, `datetime.date`, `pathlib`.

**Storage**: markdown files only. A completed-task day file has exactly `tasks.md`'s format — task
lines with trailing metadata comments and optional indented bodies, no frontmatter — so `parse_tasks`
reads it unmodified. No index, no database, no cache, no per-user state.

**Testing**: `pytest` via `scripts/dev-tests.sh`. Two new `tests/unit/` files, one new
`tests/integration/` file, two new `tests/performance/` cases carrying `@pytest.mark.performance`
(that marker now selects its own CI job, issue #84), and edits to two pinned `tests/contract/`
key-set constants. Research R12 lists the eleven existing test files that need updating.

**Target Platform**: macOS, Linux, Windows. TUI verified before release on the terminals in
`docs/REQUIREMENTS.md` §4.3.

**Project Type**: single project — `src/choom/{core,cli,tui}` over
`tests/{unit,contract,integration,performance}`.

**Performance Goals**: the default `task list` and the TUI's Todo category open **exactly one file**,
whatever the size of the store (SC-003, asserted by counting reads, not timing). Reading the whole
store stays under **500 ms for 1,000 day files holding 5,000 records** (SC-005). Opening a document
whose mirrors all name open tasks stays at **one file read**, preserving spec 008's SC-008 (SC-004).
The Done view's 2-second refresh tick is the real exposure and gets a stat-fingerprint precheck
(research R10).

**Constraints**: no admin rights, no network. `tasks/done/2026/08/2026-08-02-done.md` is 40
characters below the workspace root against the 260-character Windows limit. Both writes of a move
are individually atomic through the existing `write_text_atomic`. No user file is moved; only records
inside choom's own two task files.

**Scale/Scope**: roughly 220 lines of new source in `core/task_store.py`; ~80 lines changed across
`core/tasks.py`, `core/links.py`, `core/mirrors.py`, `core/models.py`; ~25 lines across `cli/main.py`
and `cli/output.py`; ~35 lines across `tui/app.py` and `tui/list_screen.py`.

No NEEDS CLARIFICATION remain. Every open question was resolved in [research.md](./research.md)
against the installed source.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution v2.1.0. **Result: all gates PASS. Complexity Tracking carries one
row** — not a violation, but the one design element close enough to a prohibited construct that
declining to argue it in writing would be the wrong call.

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `choom.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. **List the `core` functions this feature's reads and writes go through**, and justify any assembly done in an adapter that an existing `core` function already performs. | **PASS.** *New in core*, all in `src/choom/core/task_store.py`, every one taking a `Workspace` and returning data — no stream, no widget, no event loop: `done_file_for(workspace, on: date) -> Path`; `iter_done_files(workspace) -> list[Path]`; `load_done_tasks(workspace) -> tuple[list[Task], list[ScanWarning]]`; `load_task_store(workspace) -> tuple[list[Task], list[ScanWarning]]`; `move_record(workspace, task_id, *, done: bool, now: datetime | None = None) -> Task` — the whole move, both directions, including the two splices, the write ordering, and the duplicate-id outcome; `store_fingerprint(workspace) -> tuple[tuple[str, int, int], ...]` for R10; `tidy_completed(workspace, *, now=None) -> TidySummary` for the P3 sweep. *Existing core functions the reads and writes still go through, unmodified in kind*: `tasks.parse_tasks` (every read of every store file, including the new ones — there is no second parser), `atomic_write.write_text_atomic` (both writes of every move — there is no second write primitive), `tasks.load_tasks` (`tasks.md`, unchanged), `tasks.delete_task` (extended to locate across the store), `links.resolve_id`, `mirrors.find_mirrors`. **Answering the second half of the gate.** Five decisions were audited for adapter leakage and all five are in core: *which file a record belongs in* (`done_file_for`), *what the moved bytes are* (`move_record`), *which read a caller is asking for* (three named functions, R4, so the choice is explicit at the call site but the reading is not), *whether the store changed since the last tick* (`store_fingerprint`), and *what a partial failure means* (`move_record` raises; the adapters print). What is left in the adapters is genuinely adapter work: `cli/output.py` serialising two new keys, `cli/main.py` choosing a loader from `--done`/`--all`, `tui/app.py` choosing a loader from the active category, and `tui/list_screen.py` comparing two fingerprints it did not compute. No adapter constructs a store path, decides where a record goes, or writes a task file. Ruff's TID251 ban on `argparse`/`textual`/`rich` inside core and `tests/unit/test_core_imports.py` both still hold. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS.** *Which commands change behaviour*: `task done` and `task undone` (move the record; exit code, propagation, and warning behaviour unchanged), `task list --done` and `task list --all` (now the union of the store), `task show` and `task delete` (find a record wherever it lives), `links check` / `links heal` / `links <id>` (also cover the store, and report **no** new staleness — FR-026). *Which do not*: `task add` (a new task is never complete, so it always writes `tasks.md`) and **`task list` with no flags**, which keeps its output and its one-file cost (FR-018). Both reachable from both front-ends: the TUI's space bar and the CLI's `task done` land on the same `move_record`, so they cannot diverge. **`--json` is additive only.** Two keys are **added** to the task record — `completed` (ISO date or `null`) and `file` (workspace-relative POSIX path of the file holding the record, required because the existing `line` key is a line number and is now ambiguous without it) — and `file` is added to the `task done`/`undone` object. **No existing key is renamed, retyped, or removed**, which is the half of this rule that would be breaking: `id`, `text`, `done`, `type`, `tags`, `links`, `created`, `line`, `body`, `documents_updated`, and `warnings` all keep their names, their types, and their meanings. Both pinned exact-set constants (`tests/contract/test_json_schema.py:9`, `test_task_done_json.py`) get a reviewed one-line edit rather than being loosened. Exit codes unchanged — 0/1/2/3, with a partial failure reported as 3 (workspace error). Nothing prompts, blocks, opens an editor, or decorates a non-TTY stream; the P3 `task tidy` takes no confirmation, matching `links heal`'s shape (research R11). |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. Any new setting has a sensible default. Date stays the only axis the directory tree encodes; `type` never becomes a directory. | **PASS.** *No new source of truth.* Every record still lives in exactly one markdown line in exactly one markdown file, and every read parses that file. Nothing is written that describes the store rather than being the store: no manifest, no index, no `reindex`, no on-disk cache. The stat fingerprint of research R10 is the one construct close enough to a cache to need an argument, and it is argued in Complexity Tracking below rather than waved past. *No new dependency*, third-party or binary — the new module is standard library only. *No new setting*, so the sensible-default rule has nothing to bind to. **The layout invariant.** `tasks/done/YYYY/MM/` encodes date and only date *within* the collection; `done` is a collection root, occupying the same position as `meetings/`, `notes/`, and `notes/daily/`, not an axis inside one. A task's `type` is free-form and user-invented and stays exactly where it is today, in the metadata comment — no `type` becomes a directory here or anywhere. The harm the invariant names — "a directory per type would fragment the vault into a long tail of one-file folders" — is structurally impossible: completion is binary, every record has exactly one value of it, and the two values map to two fixed locations that exist regardless of what the user invents. `docs/REQUIREMENTS.md` §3.2's explicit test for adding a collection is met on both limbs — a real, distinct need existing collections do not serve (the open list is the file assistants read, and it cannot shrink while completed records live in it), and the same `YYYY/MM` date partitioning as the rest, so there is no reindex and no migration risk. This is a deliberate collection addition, and §3.2 is updated to list it as part of the work (research R14). |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. No user file is moved to match its partition, and no tag can be silently dropped. | **PASS — the dominant gate, so the mechanisms are named rather than asserted, and the two regressions this feature introduces are owned here.** *Never lose a line*: destination written first, source second, both directions (research R3). Of the two orderings only this one has no line-losing failure; its worst reachable outcome duplicates the record, which is the duplicate-id state `get_task`, `set_task_state`, `delete_task`, `set_task_body`, `resolve_id`, `plan_mirror_deletion`, and `delete_by_id` **already** detect and refuse to act on. This feature adds no recovery machinery — it adds file names to those existing messages (research R7) so the user can act, and stops. Each write is individually atomic through the existing `write_text_atomic`; no new write primitive. *Never re-render*: the moved lines are the source bytes with two computed splices (research R2), the same discipline `Mirror.state_offset` and `heal_text` already enforce. *Malformed input*: `parse_tasks` is unchanged and still logs-and-continues. A line it cannot read yields no `Task`, so it can never be matched by id and therefore can never move or be rewritten — FR-016 holds by construction, not by a check. *Never truncate*: `_body_span` decides what travels with a record, unmodified; every line outside the span is byte-identical in both files. *`created`/`updated`*: `created` travels with the record untouched, and no document's `updated` is stamped by a move — the sync path is `mirrors.write_document`, which exists precisely to write without stamping. *CommonMark*: a task line moved between two files of the same format stays a valid list item; nothing is inserted but one field inside an existing HTML comment. *No file moved to match its partition*: no **file** is moved at all. A *record* moves between two choom-managed files, and the invariant's substance is honoured where it actually bites — location is never authoritative (FR-005), a record filed in the "wrong" day file still lists correctly from its own `completed` field, and choom never relocates it to make the path true. That is also why the completion date is a field and not derived from the filename (research R8). *No unprompted vault rewrite*: FR-037 — nothing already in a user's `tasks.md` moves on launch, on a read, on a scan, or on any unrelated write. *No tag dropped*: no tag is parsed, re-rendered, or reconstructed anywhere in this feature; the `tags:` token is inside the bytes that are copied verbatim. **The two regressions.** *Bug 1, `ctrl+t` orphaning a completed record*: `plan_mirror_deletion` resolves across the whole store, so a completed record plans `deletable` rather than `line_only`; `unreadable_tasks` is scoped to files actually read so an old broken day file cannot become a standing veto (research R6). Regression test: `ctrl+t` on a mirror of a completed task removes both halves. *Bug 2, every completed mirror reporting dead*: `reconcile_on_open` escalates to the store when a mirror's id is absent from `tasks.md`, so the box is ticked instead of a dead-link warning being emitted (research R5). Regression test: complete a task without opening the document, open it, assert `[x]` and zero warnings. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; `ctrl+c` is never bound to anything, `ctrl+q` quits immediately unless something is dirty (in which case it MAY raise the existing confirmation); no non-`ctrl` modifier. | **PASS.** **No new binding, no new screen, no new dialog, no new footer entry.** Space still toggles a task and the row still leaves Todo and appears in Done, exactly as it does today — the file it lands in is not something the interface exposes. `ctrl+d` (list delete) and `ctrl+t` (editor task delete) keep their bindings, their confirmations, and their wording; `ctrl+t`'s confirmation now fires correctly for a completed task instead of silently taking the wrong branch, which is a bug fix inside an existing confirmation, not a new one. `ctrl+c` is not bound, inspected, or relied on. `ctrl+q` is untouched. No non-`ctrl` modifier is introduced. The one new user-visible string is FR-013's partial-failure message, which names both files and what to do — Principle V's requirement that an error name what went wrong and what to do instead. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; no test depends on the wall clock. | **PASS.** Every new public function in `core/task_store.py` carries full type hints and a docstring stating what it does and what it raises — `move_record` raises `NotFoundError`, `UsageError`, and `WorkspaceError`; the loaders raise nothing and return warnings. Coverage is chosen by what can plausibly break, not generated from the spec's 21 acceptance scenarios (research R12): `unit/` carries the weight because every Principle IV guarantee here is decidable against strings and a `tmp_path` — the splices, the byte guarantees, the body span, the malformed-line exclusion, the loaders' scopes — and a second unit file covers both partial-failure orderings by making one file unwritable; `integration/` gets one file for the round trip plus the two named regressions, parametrized across CLI and TUI rather than duplicated; `contract/` gets two reviewed edits to pinned key sets; `performance/` gets exactly two cases, both with a real budget to protect (SC-003, SC-005), both marked `@pytest.mark.performance` for the CI job issue #84 added. **No test reads the wall clock**: `move_record` and `tidy_completed` take an injectable `now: datetime | None`, matching `add_task`, and every date-bearing fixture derives its dates from the same clock the behaviour reads. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS.** No elevation, no network, no subprocess. `tasks/done/YYYY/MM/YYYY-MM-DD-done.md` adds 40 characters below the workspace root, against §3.2's 115-character worst case and the 260-character limit — the store's own path depth is fixed and cannot grow with the number of records. Spaces and non-ASCII in the workspace root are carried through `pathlib` untouched, and a task's description is never re-encoded or slugified into a path: the day file's name comes from a date, never from content. Both splices operate on character offsets into a Python `str`, so a multi-byte description cannot be split mid-character. Windows file locking is respected by reusing `write_text_atomic`'s same-directory temp file plus `os.replace`, unchanged. No per-user state is created or read. |

**Post-Phase-1 re-check**: re-evaluated after research.md, data-model.md, contracts/, and
quickstart.md were written. No gate changed status. Phase 1 added no dependency, no setting, no
binding, and no second write primitive. Three things surfaced during design and were each re-checked:
the `Task` model gaining two optional fields with defaults (gate I — data, not behaviour, and both
are read from the record's own bytes or its containing path, never invented); `_format_line_numbers`
being unified across `tasks.py` and `mirrors.py` into one file-aware helper (gate I — it removes a
duplicate rather than adding one, and gate V, since the message it produces is the user's only
instruction for recovering from a partial move); and the stat fingerprint, which is the sole
Complexity Tracking row below.

## Project Structure

### Documentation (this feature)

```text
specs/019-completed-tasks-partition/
├── spec.md                     # Approved
├── plan.md                     # This file
├── research.md                 # Phase 0 — R1–R14
├── data-model.md               # Phase 1
├── quickstart.md               # Phase 1
├── contracts/
│   ├── core-api.md             # Phase 1 — the new core surface and the changed signatures
│   ├── task-store-format.md    # Phase 1 — the day file, the `completed:` field, the splices
│   └── cli.md                  # Phase 1 — per-command behaviour and the --json delta
└── tasks.md                    # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

```text
src/choom/
├── core/
│   ├── task_store.py          # NEW: path derivation, the store loaders, move_record,
│   │                          #      store_fingerprint, tidy_completed
│   ├── tasks.py               # MODIFIED: `completed` in _RECOGNIZED_KEYS + validation;
│   │                          #           set_task_state delegates to move_record;
│   │                          #           delete_task locates across the store;
│   │                          #           get_task reads the store; one file-aware
│   │                          #           _format_line_numbers
│   ├── links.py               # MODIFIED: resolve_id escalates and returns the canonical
│   │                          #           tasks.md path; _iter_target_paths and the task-field
│   │                          #           scans cover the store; link_candidates unchanged
│   ├── mirrors.py             # MODIFIED: _load_tasks_or_warning escalates (bug 2);
│   │                          #           plan_mirror_deletion resolves across the store and
│   │                          #           scopes unreadable_tasks (bug 1)
│   ├── models.py              # MODIFIED: Task gains `completed` and `source`; + TidySummary
│   ├── workspace.py           # MODIFIED: Workspace gains a done_dir property
│   └── __init__.py            # MODIFIED: export the new core surface
├── cli/
│   ├── main.py                # MODIFIED: task list picks its loader; + task tidy (P3)
│   └── output.py              # MODIFIED: _task_record gains `completed` and `file`
└── tui/
    ├── app.py                 # MODIFIED: visible_tasks picks its loader by category
    └── list_screen.py         # MODIFIED: Done-view tick fingerprint precheck

tests/
├── unit/
│   ├── test_task_store.py           # NEW: paths, splices, loaders, byte guarantees
│   └── test_task_move_failure.py    # NEW: both partial-failure orderings
├── integration/
│   └── test_completed_task_partition.py  # NEW: round trip + the two regressions
├── contract/
│   ├── test_json_schema.py          # MODIFIED: EXPECTED_TASK_KEYS + completed, file
│   └── test_task_done_json.py       # MODIFIED: EXPECTED_KEYS + file
└── performance/
    └── test_task_store_scan.py      # NEW: SC-003 counted read, SC-005 budget

docs/REQUIREMENTS.md                 # MODIFIED: §3.2 layout + field order, §3.3 canonical address
src/choom/core/templates/AGENTS.md.tmpl  # MODIFIED: two lines (77 → 79, budget ~100)
README.md                            # UNTOUCHED — unreleased work belongs to the release
```

**Structure Decision**: the single-project layout is kept, and **one new core module is added**:
`src/choom/core/task_store.py`.

Three homes were considered. `core/tasks.py` is the obvious one and was rejected on size and on
subject: it is already 734 lines and owns *the format of a task line* — the parser, the renderer, the
body span. Where a record physically lives is a different subject, and folding a second one into that
file is how the parser's guarantees get harder to see. `core/documents.py` owns `YYYY/MM` partitioning
for documents and was rejected because a task record is not a document: it has no frontmatter, no id
of its own at file level, and no `scan`/`create` lifecycle. A new module states the boundary plainly:
`tasks.py` knows what a task line *is*, `task_store.py` knows *where it lives and how it gets there*,
and `task_store` imports `tasks`, never the reverse.

`set_task_state` keeps its name, its signature, and its position in `tasks.py` and delegates the move
to `task_store.move_record`. That matters more than where the code sits: it is the single entry point
the CLI's `task done`, the TUI's space bar, and `mirrors.reconcile_on_save` all already call
(`mirrors.py:730`), so all three inherit the move without a second implementation and cannot diverge.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

One row. Gate III is PASS, not FAIL — but the stat fingerprint is close enough to the construct
Principle III names that asserting "not a cache" without argument would be exactly the reviewer-stamina
problem the constitution is written against.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| A stat fingerprint — `(path, mtime_ns, size)` per day file — held in memory by `ListScreen` between refresh ticks, to skip re-parsing an unchanged done store (research R10) | `ListScreen._refresh_tick` runs every 2.0 s **on Textual's main thread** (`list_screen.py:225, 478`), so the Done view's read is frame budget, not background CPU — `tests/performance/test_refresh_tick.py` puts the frame-drop crossover near 15 ms. A whole-store parse at the SC-005 ceiling would drop frames every two seconds for as long as the Done view is displayed, degrading the entire UI rather than one list. The fingerprint reduces the steady-state tick to an `os.scandir` walk that opens no file. It holds no task data, answers no question about content, is never written to disk, and dies with the screen; a wrong answer yields a list that is two seconds stale, which is the tick's existing failure mode, not a wrong one. It is also the pattern the tick already uses one layer up — `_refresh_tick_apply` compares a `key` against `_last_render_key` and skips the re-render (`list_screen.py:499`) — applied one layer earlier, where the cost now sits | **Parse on every tick**: rejected, that is the frame-drop above. **Drop the tick for the Done view**: rejected, it would make Done the one collection that does not notice an external edit, an inconsistency the user would have to learn. **Move the tick's read to a worker thread**: a real option and the one `_refresh_tick_read`'s own docstring anticipates, but it is a concurrency change to a shared code path affecting all three collections, which is a larger and riskier edit than this feature should carry. **Month-scope the Done view**: the correct long-term answer and the named first remedy if SC-005 is breached (research R10, spec §"On SC-005"), but tasks have no month scope today, so it is a TUI feature in its own right and out of scope here. **An on-disk index or cache**: forbidden by Principle III without a justification this feature does not have, and explicitly not the answer — recorded here so it cannot become the default remedy later |
