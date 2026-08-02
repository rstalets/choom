---

description: "Task list for 019-completed-tasks-partition"
---

# Tasks: Completed Tasks Leave the Open List

**Input**: Design documents from `/specs/019-completed-tasks-partition/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included, and **not** as a trailing phase. Every behaviour change lands with the tests that
cover it, in the same task — Constitution Principle VI and the Development Workflow gate. There is no
"write the tests afterwards" step in this list, deliberately.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different file, no dependency on an incomplete task
- **[Story]**: which user story the task serves (US1–US6); Setup, Foundational, and Polish carry none
- Every task names the file it touches and the command that verifies it

## Path Conventions

Single project: `src/choom/{core,cli,tui}` over `tests/{unit,contract,integration,performance}`. Tests
run through `scripts/dev-tests.sh`, never a hand-rolled `pytest` invocation.

---

## The one mistake that would sink this feature

**Do not implement the move as `delete_task` + `add_task`.** Both functions already exist, both are
right there in `tasks.py`, and composing them is the single most likely way this ships broken —
because it would pass a naive "the line moved" test and destroy the feature's central guarantee.

`add_task` calls `new_task_id(taken)` (`tasks.py:487`). **It mints a new id.** It also re-renders the
line from parsed fields and accepts no body. So the composed version would:

| What breaks | Consequence |
|---|---|
| The id changes | **Every mirror pointing at that task goes dead.** `- [ ] [call Terry](../../tasks.md#task_a1b2)` now resolves to nothing, in every document, permanently |
| The line is re-rendered | Hand-typed spacing inside the metadata comment is normalised away — FR-008 violated |
| The body is dropped | `add_task` has no body parameter. The indented continuation lines are silently lost — Principle IV violated in the worst way |

The rule, which belongs in a comment at `move_record` and not only here: **a move preserves identity;
a create does not.** The id is permanent and authoritative (`docs/REQUIREMENTS.md` §3.3) and is the
only thing every mirror in the vault holds onto. `move_record` therefore carries the *source bytes*
across, with two computed splices and nothing else (contracts/task-store-format.md F4).

---

## The ordering that makes the tree stay green

Read this before sequencing anything. **Every consumer learns to read the done store while the store
is still always empty**, and only then does the producer start filling it. That is why Phase 4 wires
six readers before Phase 5 flips one writer:

- A reader task that escalates to the store changes no observable behaviour while no workspace has a
  store, so the whole existing suite stays green as each one lands.
- Each reader task still carries its own test, by **hand-writing a day file into the fixture** — no
  `move_record` needed. This is what lets test-with-behaviour and green-at-every-checkpoint both hold.
- T027 is the one task where existing tests change, because it is the moment completed records start
  living somewhere new. Doing it last means exactly one task has to reason about the old expectations.

Inverting this — flipping the writer first — would leave the tree red across a dozen tasks with every
failure attributed to the wrong one.

---

## Phase 1: Setup

**Purpose**: baseline, and the value types everything else needs. Nothing behavioural moves.

- [ ] T001 Confirm the baseline is green before changing anything: run `scripts/dev-tests.sh` from the
      repository root and record the pass count. Also run
      `uv run ruff format --check . && uv run ruff check . && uv run mypy src`. Do not start T002 on a
      red tree — a pre-existing failure attributed to this feature wastes the whole gate
- [ ] T002 [P] Add the two additive defaulted fields to `Task` in `src/choom/core/models.py` per
      [data-model.md](./data-model.md) §3: `completed: date | None = None` and
      `source: Path | None = None`. Defaulted and appended, so every existing construction site and
      test keeps working untouched. Add the `TidySummary` frozen slotted dataclass (`moved: int`,
      `left: int`, `warnings: tuple[ScanWarning, ...]`) in the same pass. Verify:
      `scripts/dev-tests.sh` still green and `uv run mypy src` clean, with no other file changed
- [ ] T003 [P] Add the `done_dir` property to `Workspace` in `src/choom/core/models.py` returning
      `self.root / "tasks" / "done"`, alongside the existing `tasks_file`. Verify:
      `scripts/dev-tests.sh tests/unit -k workspace` green
- [ ] T004 Teach the parser and renderer the `completed` field in `src/choom/core/tasks.py`: add
      `"completed"` to `_RECOGNIZED_KEYS`, validate it exactly as `created` is validated (`_ISO_DATE`
      then `date.fromisoformat`, a bad value emitting `ScanWarning(reason="task_invalid_value")` **and
      the record still returned**), and give `render_task_line` an optional
      `completed: date | None = None` emitted last and omitted when `None`. Cover in
      `tests/unit/test_task_parsing.py`: a comment carrying `completed:` now classifies `task` rather
      than `malformed`; a bad value warns and still yields the record; field order on render is
      `id type tags links created completed`. Verify: `scripts/dev-tests.sh tests/unit` green

**Checkpoint**: tree green, types and grammar in place, no record has moved and no path has been built.

---

## Phase 2: Foundational — `core/task_store.py` (BLOCKING)

**Purpose**: the module every later phase calls. Nothing is wired to it yet, so the tree stays green
throughout; each task is proved by its own unit tests against a `tmp_path`.

**⚠️ CRITICAL — the write ordering.** `move_record` writes the **destination first and the source
second**, in both directions, and this is not a style preference. There are two possible orderings and
only one of them can lose a line:

| Ordering | Failure between the two writes | Outcome |
|---|---|---|
| source first, destination second | destination write fails | **the record is gone from both files** |
| destination first, source second | source write fails | the record exists in **both** files |

The second is loud, already detected everywhere in the tree, and fixable by hand. The first is silent
data loss. Principle IV does not treat that as a close call. Put the table's conclusion in a comment
at `move_record`, so a later "tidy up the write order" refactor has to argue with it.

- [ ] T005 Create `src/choom/core/task_store.py` with the module docstring stating the boundary:
      `tasks.py` knows what a task line *is*; this module knows *where it lives and how it gets there*;
      `task_store` imports `tasks`, never the reverse. Implement C1 `done_file_for(workspace, on)` —
      pure, opens nothing — and C2 `iter_done_files(workspace)`, newest day first, `[]` when the root
      is absent, never raising. Cover both in a new `tests/unit/test_task_store.py`: the exact path for
      a date, an absent root, an unreadable directory yielding what it could enumerate. Verify:
      `scripts/dev-tests.sh tests/unit/test_task_store.py` green
- [ ] T006 Implement the two splices as private helpers in `src/choom/core/task_store.py`, per
      [contracts/task-store-format.md](./contracts/task-store-format.md) F4 — **byte-level, never a
      re-render**. State splice: the one character at `_TASK_LINE.span("state")`, the identical edit
      `set_task_state` performs today. `completed:` insert: inner comment body `B` becomes
      `B.rstrip() + " completed:<ISO>" + <B's original trailing whitespace, or " ">`. Removal: drop the
      first `completed:…` token and the single space before it. Cover in
      `tests/unit/test_task_store.py`: a comment with unusual internal spacing survives byte-identical
      outside the splice; insert-then-remove round-trips to the original bytes; a line with no comment
      and a bare comment are both untouched because neither yields a matchable id. Verify:
      `scripts/dev-tests.sh tests/unit/test_task_store.py` green
- [ ] T007 Implement C3 `load_done_tasks` and C4 `load_task_store` in
      `src/choom/core/task_store.py`. Each returned `Task` carries `source` and its own `completed`.
      An unreadable or unparseable day file yields one warning naming it and does not stop the rest
      (FR-022). Ordering per [data-model.md](./data-model.md) §6: `tasks.md` first, then day files
      newest-first. Cover in `tests/unit/test_task_store.py` with hand-written day files, including one
      unreadable file among three good ones. Verify: `scripts/dev-tests.sh tests/unit/test_task_store.py`
      green
- [ ] T008 Add best-effort id backfill inside the done store to `load_done_tasks` in
      `src/choom/core/task_store.py`, on the same terms `load_tasks` uses for `tasks.md`
      (`tasks.py:423-451`): a hand-written `- [x] paid the invoice` in a day file gets an id written
      back; if the write fails the read still succeeds with a warning (research R13, Principle IV's
      "missing metadata is repaired in place"). Cover both paths in `tests/unit/test_task_store.py`,
      the failure one with the file made read-only. Verify:
      `scripts/dev-tests.sh tests/unit/test_task_store.py` green
- [ ] T009 Implement C5 `move_record(workspace, task_id, *, done, now=None)` in
      `src/choom/core/task_store.py` — **destination first, source second**, per the CRITICAL table
      above, both writes through the existing `write_text_atomic` (which already creates parent
      directories, so FR-003 needs no `mkdir`). Locates by id across the whole store, `tasks.md` first;
      re-reads and re-parses immediately before writing; never trusts a cached line number. Moves the
      checkbox line **and its whole `_body_span`**, bytes intact. Returns early writing **nothing**
      when the record already has the requested state — including when that record sits in the "wrong"
      file for its state, which must not trigger a relocation (FR-005). `now` is injectable
      (Principle VI — no test may read the wall clock). Cover in `tests/unit/test_task_store.py`: the
      round trip with a body, tags, links and a type; the no-op writing nothing in either file; a
      `[x]` in `tasks.md` and a `[ ]` in a day file each staying put on a no-op. Verify:
      `scripts/dev-tests.sh tests/unit/test_task_store.py` green
- [ ] T010 Cover both partial-failure orderings in a new `tests/unit/test_task_move_failure.py`
      (SC-007). **Destination unwritable**: `WorkspaceError` raised, `tasks.md` byte-identical, the
      task still open — nothing moved. **Source unwritable after the destination write succeeded**:
      the record exists in *both* files, no line lost, and the raised `WorkspaceError` names both files
      and states that one copy must be removed by hand. This test is the evidence for the ordering
      decision; if someone later inverts the writes, this is what goes red. Verify:
      `scripts/dev-tests.sh tests/unit/test_task_move_failure.py` green
- [ ] T011 Unify the duplicated `_format_line_numbers` (`tasks.py:575` and `mirrors.py:291`) into one
      file-aware helper in `src/choom/core/tasks.py` that formats `(path, line)` pairs as
      `tasks.md:12 and tasks/done/2026/08/2026-08-02-done.md:3`, and delete `mirrors.py`'s copy in
      favour of importing it (research R7). This is the user's only instruction for recovering from the
      T010 partial failure, so Principle V's "name what went wrong and what to do" applies to it
      directly. Update the existing assertions on the old message shape. Verify:
      `scripts/dev-tests.sh` green
- [ ] T012 Implement C6 `store_fingerprint(workspace)` in `src/choom/core/task_store.py` —
      `(posix_path, st_mtime_ns, st_size)` per day file, sorted, one `os.scandir` walk, opens no file,
      never raises. **Docstring must state that a matching fingerprint is not proof the store is
      unchanged**, and why: timestamp granularity (1 s on HFS+/ext3, 2 s on FAT/exFAT) plus
      size-preserving edits like a `[x]`→`[ ]` toggle, which makes a miss **permanent** rather than
      transient. Point at the bound its caller must apply (T037). Cover in
      `tests/unit/test_task_store.py`: the tuple changes when a file is added, removed, or grown.
      Verify: `scripts/dev-tests.sh tests/unit/test_task_store.py` green
- [ ] T013 Export the new core surface from `src/choom/core/__init__.py` and confirm core stays
      terminal-free. Verify: `scripts/dev-tests.sh tests/unit/test_core_imports.py` green and
      `uv run ruff check .` clean — TID251 bans `argparse`/`textual`/`rich` inside core, and
      `task_store.py` must import none of them

**Checkpoint**: the store module is complete and unit-tested. Nothing reads it, nothing writes to it
through the app, and the whole suite is green.

---

## Phase 3: User Story 5 — the workspace someone already has (Priority: P2)

**Goal**: prove, before anything starts moving records, that an existing `tasks.md` full of completed
lines is not touched. Sequenced first because it is a *negative* guarantee — cheapest to assert while
nothing moves, and it becomes the regression net for every later phase.

**Independent test**: populate `tasks.md` with open and completed lines, run every read command, and
diff.

- [ ] T014 [P] [US5] Add `tests/integration/test_completed_task_partition.py` with the
      no-unprompted-migration cases (SC-008, FR-037): a `tasks.md` carrying 300 completed lines is
      **byte-identical** after `choom init`-adjacent launch, `task list`, `task list --done`,
      `task list --all`, `links check`, and opening a document. Assert on file bytes, not on row
      counts. Verify: `scripts/dev-tests.sh tests/integration/test_completed_task_partition.py` green

**Checkpoint**: the "we did not touch your vault" guarantee is pinned before any writer changes.

---

## Phase 4: The readers learn the store (US3 in part, and both regression fixes)

**Purpose**: every consumer escalates to the done store *while the store is still always empty*, so
each task is behaviour-neutral for existing workspaces and the tree stays green. Each carries its own
test by hand-writing a day file into the fixture.

- [ ] T015 [US3] Make `links.resolve_id` escalate in `src/choom/core/links.py`: for a `task_` id, read
      `tasks.md` first and the done store only on a miss. **`LinkTarget.path` stays
      `workspace.tasks_file` whichever file holds the record** — FR-024, the canonical-address rule
      that is the whole reason no mirror is ever rewritten. Put the rule in a comment at the task pool
      branch; it is load-bearing and reads like a bug otherwise. Cover in `tests/unit/test_links.py`: a
      hand-written completed record resolves, and its `LinkTarget.path` is `tasks.md`. Verify:
      `scripts/dev-tests.sh tests/unit/test_links.py` green
- [ ] T016 [US3] Prove the canonical address means no staleness: add cases asserting
      `choom links check` reports **neither stale nor dead** for a mirror whose task sits in a
      hand-written day file, and that `choom links heal` rewrites nothing (FR-026, SC-009). Put them in
      `tests/integration/test_completed_task_partition.py`. This is the test that fails if someone
      "fixes" T015 to return the record's physical path. Verify:
      `scripts/dev-tests.sh tests/integration/test_completed_task_partition.py` green
- [ ] T017 [P] [US3] Extend link scanning to cover the store in `src/choom/core/links.py` (FR-028):
      `_iter_target_paths` appends the store's files, and `_task_field_reports` /
      `_all_task_field_links` read `load_task_store`. A completed task's `links:` ids and the ordinary
      markdown links in its text or body are still links and must not stop being checked. **Leave
      `link_candidates` on `load_tasks`** — the `/link` picker offers open tasks only, unchanged
      (research R4); add a comment saying so, because it looks like an omission. Cover both in
      `tests/unit/test_links.py`. Verify: `scripts/dev-tests.sh tests/unit/test_links.py` green
- [ ] T018 [US3] **Regression fix — bug 2.** Make `mirrors._load_tasks_or_warning` escalate per C8 in
      `src/choom/core/mirrors.py`: read `tasks.md` first, and read the done store **at most once, and
      only when at least one mirror names an id `tasks.md` does not carry**. Today an unresolved id is
      treated as dead (`mirrors.py:587-591`), so once records move, every mirror of a completed task
      would stay `[ ]` and emit a dead-link warning on every open — strictly worse than current
      behaviour. Named regression test in
      `tests/integration/test_completed_task_partition.py`: with a hand-written day file holding the
      record and the document closed, opening the document ticks the box to `[x]` and produces
      **zero** warnings. Verify:
      `scripts/dev-tests.sh tests/integration/test_completed_task_partition.py` green
- [ ] T019 [US3] Pin the escalation's cost in `tests/unit/test_mirror_reconcile.py` (SC-004,
      preserving spec 008's SC-008): a document whose mirrors all name open tasks reads `tasks.md`
      **exactly once and never touches the store** — asserted by counting reads, the technique
      `tests/performance/test_reconcile_open.py` established. Also update that performance test, which
      counts `load_tasks` calls and must now account for the escalation. Verify:
      `scripts/dev-tests.sh tests/unit/test_mirror_reconcile.py tests/performance/test_reconcile_open.py`
      green
- [ ] T020 [US4] **Regression fix — bug 1, the serious one.** Make `mirrors.plan_mirror_deletion`
      resolve across the whole store in `src/choom/core/mirrors.py`, per C9, still using `parse_tasks`
      and never `load_tasks` so the plan step writes nothing (017 FR-014). Today it opens
      `workspace.tasks_file` directly (`mirrors.py:397`), finds nothing for a completed task, falls
      through to `line_only` (`mirrors.py:466`), and the TUI then **removes the user's document line
      while `commit_mirror_deletion` writes nothing** — the line is gone and the record survives
      orphaned. A completed record must plan `deletable`. Named regression test in
      `tests/integration/test_completed_task_partition.py`: `ctrl+t` on a mirror of a completed task
      removes the document line **and** the record. Verify:
      `scripts/dev-tests.sh tests/integration/test_completed_task_partition.py tests/unit/test_mirror_deletion.py`
      green
- [ ] T021 [US4] Re-scope `unreadable_tasks` in `src/choom/core/mirrors.py` to files **actually read
      during this resolution**, with the message naming that `<file>:<line>` rather than always
      `tasks.md`. 017's rule is kept in substance; applied naively across hundreds of day files, one
      broken line in a file from last March would become a permanent veto on every `ctrl+t` in the
      workspace — a refusal the user cannot act on because nothing tells them the file exists. **This
      changes behaviour that shipped tonight, so pin both directions in the same task** in
      `tests/unit/test_mirror_deletion.py`: a broken line in a day file **not** consulted must **not**
      block a deletion, and a broken line in a file that **is** consulted must still refuse. Blocking
      reason set unchanged — `{task_unterminated_comment, task_malformed_comment}`, with
      `task_invalid_value` still never blocking (017 FR-022). Verify:
      `scripts/dev-tests.sh tests/unit/test_mirror_deletion.py` green
- [ ] T022 [P] [US4] Make `tasks.get_task` and `tasks.delete_task` locate across the store in
      `src/choom/core/tasks.py` (FR-021, FR-036). `delete_task` removes the record from whichever file
      holds it and returns it with `source` naming that file; `deletion.delete_by_id` then reports the
      right path instead of hard-coding `workspace.tasks_file` (`deletion.py:62`). Cover in
      `tests/unit/test_task_store.py` and `tests/contract/test_cli_delete.py`: `choom task delete` on a
      hand-written completed record removes it from the day file and exits 0. Verify:
      `scripts/dev-tests.sh tests/unit/test_task_store.py tests/contract/test_cli_delete.py` green
- [ ] T023 [P] [US1] Wire the CLI's loader choice in `src/choom/cli/main.py`: `task list` with no flags
      keeps `load_tasks` — **one file, whatever the store holds** (FR-018) — while `--done` and
      `--all` use `load_task_store`, and `task show` uses `load_task_store`. Comment the default branch
      with why it must not escalate; it is the point of the feature and looks like an oversight
      otherwise. Cover in `tests/integration/test_task_cli.py` with a hand-written day file: `--done`
      shows it, the bare form does not. Verify:
      `scripts/dev-tests.sh tests/integration/test_task_cli.py` green
- [ ] T024 [P] [US1] Wire the TUI's loader choice in `src/choom/tui/app.py`: `visible_tasks` uses
      `load_tasks` for the Todo category and `load_task_store` for Done. Cover in
      `tests/integration/test_task_category_tui.py` with a hand-written day file. Verify:
      `scripts/dev-tests.sh tests/integration/test_task_category_tui.py` green

**Checkpoint**: every reader finds a record wherever it lives, both regressions are fixed and pinned,
and the full suite is still green because nothing has started writing to the store.

---

## Phase 5: User Story 1 — the open list stays the open list (Priority: P1) 🎯 MVP

**Goal**: completing a task moves the record out of `tasks.md`.

**Independent test**: complete a task via CLI and via the TUI; `tasks.md` no longer carries the line, a
day file does, `task list` does not show it and `task list --done` does.

- [ ] T025 [P] [US1] Add the two `--json` keys in `src/choom/cli/output.py`: `_task_record` gains
      `completed` (ISO string or `null`) and `file` (workspace-relative POSIX path — required because
      `line` is a line number and is ambiguous once records live in two files). **Additive only: no
      existing key is renamed, retyped, or removed**, which is the half of Principle II that would be
      breaking. Verify: `uv run mypy src` clean
- [ ] T026 [US1] Update the two **pinned exact-set constants** deliberately, not by loosening them:
      `EXPECTED_TASK_KEYS` in `tests/contract/test_json_schema.py:9` gains `completed` and `file`, and
      `EXPECTED_KEYS` in `tests/contract/test_task_done_json.py` gains `file` (which
      `_set_task_state_and_propagate` in `src/choom/cli/main.py` must now emit). Keep both as exact-set
      assertions — a set comparison replaced by a subset check is how a removed key stops being caught.
      Add assertions that `completed` is `null` for an open task and an ISO date for a completed one.
      Verify: `scripts/dev-tests.sh tests/contract` green
- [ ] T027 [US1] **The flip.** Make `tasks.set_task_state` delegate to `task_store.move_record` in
      `src/choom/core/tasks.py`, keeping its name, signature, and no-op contract exactly as they are.
      This is deliberately the single entry point the CLI's `task done`, the TUI's space bar, and
      `mirrors._write_task_state` (`mirrors.py:730`) already share, so all three inherit the move and
      cannot diverge. Thread `now` through from `_cmd_task_done`/`_cmd_task_undone` so no test reads the
      wall clock. **Update in this same task the existing tests that assert a completed line stays in
      `tasks.md`** — research R12 lists them: `tests/integration/test_task_cli.py`,
      `test_task_handedit.py`, `test_task_no_loss.py`, `test_task_category_tui.py`,
      `tests/unit/test_task_filter_only_done.py`, `tests/unit/test_mirror_reconcile.py`,
      `tests/integration/test_mirror_reconcile_open.py`, `test_mirror_reconcile_save.py`,
      `test_mirror_propagation.py`. Each still asserts something true in substance; what changes is
      which file the line is expected in. Verify: `scripts/dev-tests.sh` green — the whole suite
- [ ] T028 [US1] Add the US1 acceptance cases to
      `tests/integration/test_completed_task_partition.py`: the record lands in the day file for
      today with `completed:<today>` (clock injected); `tasks.md` contains no line mentioning the id
      (SC-001); a body with tags, links and a type travels with the same lines and the same relative
      indentation and `task show` prints it unchanged. Verify:
      `scripts/dev-tests.sh tests/integration/test_completed_task_partition.py` green
- [ ] T029 [US1] Assert the blast radius (SC-006): a completion writes **no file outside the task
      store** except the documents named in the task's own `links:` field, which is
      `propagate_to_documents`' pre-existing behaviour. Assert by watching writes across the workspace,
      not by inspection. Put it in `tests/integration/test_completed_task_partition.py`. Verify:
      `scripts/dev-tests.sh tests/integration/test_completed_task_partition.py` green

**Checkpoint**: the MVP works end to end. `tasks.md` is the open list.

---

## Phase 6: User Story 2 — unticking brings it back (Priority: P1)

**Goal**: reopening moves the record back with everything intact.

**Independent test**: complete, reopen, and diff `tasks.md` against what it held before.

- [ ] T030 [US2] Add the reverse-direction cases to
      `tests/integration/test_completed_task_partition.py` (SC-002): after complete → reopen, the
      record is back in `tasks.md` with its `created`, `type`, `tags`, `links`, `body` and **id**
      unchanged and no `completed:` field, and the file differs from the original only in the record's
      position. Cover the emptied day file being left in place, not pruned, and a task reopened and
      re-completed on a later day landing in the later day's file. Verify:
      `scripts/dev-tests.sh tests/integration/test_completed_task_partition.py` green
- [ ] T031 [US2] Cover the mirror-driven direction in
      `tests/integration/test_mirror_reconcile_save.py`: unticking a mirror in a document and saving
      moves the record back to `tasks.md`, and ticking one moves it into the store — inherited through
      `set_task_state`, so this is a wiring assertion, not new behaviour. Confirm no document's
      `updated` is stamped by the move (FR-032), which `mirrors.write_document` already guarantees.
      Verify: `scripts/dev-tests.sh tests/integration/test_mirror_reconcile_save.py` green

**Checkpoint**: the move is a round trip, not a trapdoor.

---

## Phase 7: User Story 6 — tidying an old list on purpose (Priority: P3, droppable)

**Goal**: an explicit sweep for the user who asks. **Drop this whole phase without affecting anything
above** — US5 already leaves existing users correct and unharmed.

- [ ] T032 [US6] Implement C7 `tidy_completed(workspace, *, now=None)` in
      `src/choom/core/task_store.py`: moves every parseable completed record out of `tasks.md` into the
      store, one at a time under T009's ordering, returning `TidySummary`. A record it cannot read is
      left and counted. Never prompts, never runs implicitly. Cover in `tests/unit/test_task_store.py`,
      including a failure partway through leaving earlier moves done and reporting counts. Verify:
      `scripts/dev-tests.sh tests/unit/test_task_store.py` green
- [ ] T033 [US6] Add `choom task tidy` to `src/choom/cli/main.py` — non-interactive, no prompt, no
      confirmation flag, reporting moved/left counts, with `--json`. CLI-only, on the precedent that
      `links check`/`links heal` have no TUI surface (research R11): there is nothing to select and no
      per-record decision, so it is inherently non-interactive under Principle II. Cover in
      `tests/integration/test_task_cli.py` and assert non-blocking behaviour in
      `tests/contract/test_non_blocking.py`. Verify: `scripts/dev-tests.sh` green

**Checkpoint**: the escape hatch exists and still never runs on its own.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T034 [P] Add `tests/performance/test_task_store_scan.py` with the SC-003 case: `choom task list`
      with no flags opens **exactly one file** with 365 day files present, asserted by **counting
      reads, not timing** — a count cannot flake, which is why this is the primary performance test.
      **Must carry `@pytest.mark.performance`**: `tests/performance/` runs as its own CI job selected
      by that marker (issue #84), and an unmarked test silently runs in the wrong job. Verify:
      `scripts/dev-tests.sh -m performance tests/performance/test_task_store_scan.py` green
- [ ] T035 [P] Add the SC-005 budget case to `tests/performance/test_task_store_scan.py`: reading the
      whole store stays under 500 ms for 1,000 day files holding 5,000 records, best-of-5, matching the
      technique `test_task_scan.py` uses to avoid the single-sample flakiness issue #84 exists to fix.
      **Must carry `@pytest.mark.performance`.** Derive fixture dates from the same clock the behaviour
      reads — no literal dates (Principle VI). Verify:
      `scripts/dev-tests.sh -m performance tests/performance/test_task_store_scan.py` green
- [ ] T036 Wire the Done view's stat-fingerprint precheck into `src/choom/tui/list_screen.py`:
      `_refresh_tick_read` compares `store_fingerprint` against the previous tick's and skips the parse
      when it matches. This exists because `_refresh_tick` runs every 2.0 s **on Textual's main
      thread** (`list_screen.py:225, 478`), so a whole-store parse is frame budget, not background CPU.
      Verify: `scripts/dev-tests.sh tests/integration/test_task_category_tui.py` green
- [ ] T037 **Bound the fingerprint's staleness** in `src/choom/tui/list_screen.py`: force a full
      re-parse when more than 30 s of *displayed* Done view has elapsed since the last one. Wall-clock,
      not tick-count, because the tick is paused while filtering, editing, or suspended
      (`on_screen_suspend`/`on_screen_resume`) and a tick-count bound would stretch arbitrarily in wall
      time. **The clock is injected** — no test may read the wall clock (Principle VI). This is not
      optional polish: without it a missed change is **permanent**, because the next tick recomputes
      the same fingerprint and misses again, unlike the tick's existing failure mode which always
      recovers. A miss is reachable when timestamp granularity (1 s on HFS+/ext3, 2 s on FAT/exFAT)
      swallows a **size-preserving** edit such as a `[x]`→`[ ]` toggle. Test with an injected clock: a
      day file edited so its `(mtime_ns, size)` is unchanged is still picked up once the bound elapses.
      Record in a comment that if a measured full parse exceeds ~100 ms the answer is to month-scope the
      Done view, **never** to lengthen the interval — a longer interval makes the stall rarer instead
      of smaller and widens the window this bound exists to close. Verify:
      `scripts/dev-tests.sh tests/integration/test_task_category_tui.py` green
- [ ] T038 [P] Update `docs/REQUIREMENTS.md`: §3.2's layout block gains
      `tasks/done/YYYY/MM/YYYY-MM-DD-done.md`, the task-line bullet gains `completed` in the field
      order, and the collection list names the new collection — §3.2's own two-limb test for adding one
      is met, so this records the addition rather than amending the rule. §3.3 gains the
      canonical-address rule (FR-024). Verify: `scripts/dev-tests.sh tests/contract/test_guidance_docs.py`
      green
- [ ] T039 [P] Add two lines to `src/choom/core/templates/AGENTS.md.tmpl`: where completed tasks live,
      and that `tasks.md` is the open list. The file is at 77 lines against the ~100-line backstop that
      `tests/contract/test_guidance_docs.py` enforces, so this sits comfortably inside it — and it is
      exactly the non-obvious layout fact §4.2 says the file exists to carry. Verify:
      `scripts/dev-tests.sh tests/contract/test_guidance_docs.py` green
- [ ] T040 **Leave README.md alone — this is a deliberate skip, not an oversight.** Per CLAUDE.md the
      README feature list describes the *released* version and closes with "Everything above has landed
      on `main` as of vX.Y.Z"; a reader arriving from PyPI installs that version, so a bullet
      describing unreleased work is a promise the tool they just installed does not keep. This feature
      is unreleased. The `/release` skill folds it into the README when v0.0.4 is cut — that is what
      the "document it" task is actually for at implementation time. Recording the behaviour in this
      feature's own `specs/` artifacts is done. Verify: no `README.md` edit appears in
      `git diff --stat origin/release/v0.0.4`
- [ ] T041 Final gate: run `scripts/dev-tests.sh`, then
      `uv run ruff format --check . && uv run ruff check . && uv run mypy src`, then walk
      [quickstart.md](./quickstart.md) §§1–8 by hand in a scratch workspace. Verify the TUI on at least
      one target terminal per `docs/REQUIREMENTS.md` §4.3, watching specifically for jank in the Done
      view every two seconds — that symptom means SC-005 is breached and the remedy is month-scoping,
      not an index

---

## Dependencies & Execution Order

### Phase dependencies

```text
Phase 1 (Setup)              → blocks everything
Phase 2 (task_store.py)      → blocks everything after it; T009 blocks T027 and T032
Phase 3 (US5)                → independent; do early, it is the negative-guarantee net
Phase 4 (readers)            → needs Phase 2; must complete before Phase 5
Phase 5 (US1, the flip)      → needs Phase 4 complete. T027 is the behaviour switch
Phase 6 (US2)                → needs Phase 5
Phase 7 (US6, droppable)     → needs T009; independent of Phases 5–6
Phase 8 (Polish)             → T036 before T037; T038–T041 need the behaviour to be final
```

### Within Phase 2

T005 → T006 → T007 → T008 → T009 → T010. T011, T012, T013 are independent of that chain once T005
exists.

### Parallel opportunities

- T002, T003 (different concerns in `models.py` — coordinate, or serialise if the file conflicts)
- T014 alongside all of Phase 2 (different files entirely)
- T017, T022, T023, T024 (`links.py`, `tasks.py`, `cli/main.py`, `tui/app.py`)
- T025 alongside Phase 4 (`cli/output.py` touched by nothing else)
- T034, T035 (same new file — write together), T038, T039 (docs, no code)

### Suggested MVP

Phases 1, 2, 4, 5 — **T001–T013 and T014–T029**. That delivers the issue's actual ask (`tasks.md`
becomes the open list), both regression fixes, and the guarantee that nobody's existing vault is
touched. Phase 6 follows immediately in practice because a one-way move is a trapdoor; Phase 7 is
genuinely optional and Phase 8's T036–T037 can be deferred only if the Done view is measured under
the frame budget without them.

---

## Notes

- **No README task exists, deliberately.** The tasks template would generate one; it is omitted per
  CLAUDE.md, and T040 records the skip explicitly so a reviewer can see it was a decision. `/release`
  owns the README.
- **No trailing test phase, deliberately.** Every behaviour change above carries its tests in the same
  task, per Principle VI and the Development Workflow gate.
- **The tree is green at every checkpoint.** Phase 4 is sequenced before Phase 5 specifically so that
  readers learn the store while it is still always empty; T027 is the one task where existing
  expectations change, and it updates them itself.
- **Injectable clocks throughout**: T009, T027, T032, T033, T035, T037. No test reads the wall clock.
- **`@pytest.mark.performance` on T034 and T035.** Unmarked, they run in the wrong CI job (issue #84).
- **Two owned regressions**: T018 (`reconcile_on_open` reporting completed mirrors dead) and T020
  (`plan_mirror_deletion` orphaning a completed record — the serious one, since the user's document
  line is removed). T021 pins both directions of the `unreadable_tasks` re-scoping, which changes a
  feature that shipped tonight.
