---

description: "Task list for 017-editor-task-delete"
---

# Tasks: Delete a Task From the Line It Lives On

**Input**: Design documents from `/specs/017-editor-task-delete/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included, and **not staged into a trailing phase**. The constitution's Development Workflow
gate requires a behaviour change to land with the tests that cover it, so every task below that adds a
rule adds that rule's tests in the same task — the span task writes the span tests. Coverage follows the
placement argued at the plan's gate VI: `unit/` carries the weight, because every Principle IV guarantee
here is decidable against a string; one `integration/` file for the gesture end to end. **No
`contract/` test** — this feature adds no CLI command, flag, `--json` key, or exit code. **No
`performance/` test** — the plan step parses one `tasks.md` and scans a buffer already in memory, the
same cost `/task` pays today, so there is no budget to protect and a timing assertion would be exactly
the wall-clock flake Principle VI forbids and this milestone already had to repair once (#84).

**Organization**: Grouped by user story. Phase 2 is unusually heavy on purpose: this feature deletes user
data in two files, and every guarantee about *what* gets removed is a pure string decision. Landing all
of it in core, with its tests, before a single key is bound means the destructive half is proven before
anything can fire it.

**US2 has no phase of its own.** spec.md states it needs no additional behaviour — deleting a task
captured seconds ago is the same code path as deleting one from last week — so it is proven by a test
inside Phase 3 rather than given a phase that would duplicate US1's implementation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: US1–US5 — maps to the user stories in spec.md

## Path Conventions

Single project: `src/choom/` and `tests/` at the repository root, per plan.md.

---

## Phase 1: Setup

**Purpose**: Establish a green baseline and confirm what is being extended rather than replaced.

- [x] T001 Run `scripts/dev-tests.sh` plus `uv run ruff format --check . && uv run ruff check . && uv run mypy src` from the repository root and confirm all green before touching anything. Record the test count so a later drop is visible
- [x] T002 Read the five touch points before editing: `find_mirrors` at src/choom/core/mirrors.py:50 (the task-line recogniser this feature reuses — FR-005 forbids a second definition), `parse_tasks` at src/choom/core/tasks.py:170 and `delete_task` at src/choom/core/tasks.py:520, `EditorPane.check_action` at src/choom/tui/edit_screen.py:384 and `_save` at src/choom/tui/edit_screen.py:421. Confirm two things that the plan depends on and that must not be changed: `tests/integration/test_delete_mirrors.py` pins that deleting a task leaves mirroring documents **byte-identical** (the deliberate asymmetry in spec.md §"Interface parity" — this feature must not change it), and `tests/unit/test_footer_bindings.py:44` pairs `(EditorPane, EDIT_HELP)` so any `show=True` binding missing from the footer fails mechanically

**Checkpoint**: Baseline green, and the two existing guarantees this feature must preserve are known.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The whole of *what a deletion means*, in `core`, with its tests. Nothing in the TUI can be
built until this exists, and nothing here needs a terminal.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Add `link_start: int` and `link_end: int` to the `Mirror` dataclass in src/choom/core/models.py per [data-model.md](./data-model.md) §1, and populate them in `find_mirrors` at src/choom/core/mirrors.py:83-102 from the `Link` it already selects (it currently sorts the line's task links by `link.start` and keeps only `(task_id, text)`, discarding the span). **Do not re-derive which link is the mirror anywhere else** — FR-005 and FR-007 allow exactly one definition, and carrying the evidence `find_mirrors` already computed is what prevents a second one. `Mirror` is constructed in exactly one place in the tree, so this breaks no call site. Same task: extend tests/unit/test_mirror_recognition.py with cases asserting `link_start`/`link_end` bound the link's own text on a plain mirror line, on an indented one, and on a line carrying two task links (the first by document order wins, per FR-007)
- [x] T004 [P] Add `MirrorDeletionOutcome` (a `Literal` of `"deletable"`, `"line_only"`, `"unreadable_tasks"`, `"ambiguous_id"`, `"self_referential"`, alongside the existing `MirrorOutcome`) and the frozen, slotted `MirrorDeletion` dataclass to src/choom/core/models.py per [data-model.md](./data-model.md) §2 and §3, with the field set `outcome`, `task_id`, `description`, `text`, `span`, `extra_text`, `message`. Types only, no behaviour. Docstring states that `text` and `span` describe the same single removal and that nothing here is ever persisted
- [x] T005 Implement `plan_mirror_deletion(workspace, text, line, *, source, body_task_id=None) -> MirrorDeletion | None` in src/choom/core/mirrors.py per [contracts/core-api.md](./contracts/core-api.md) §1, **document-side decisions plus the two non-refusing outcomes only** (the three refusals are T006). Returns `None` when `line` carries no task line. For a task line, computes `task_id`, `description`, `extra_text`, `span`, and `text`, then returns `deletable` when exactly one task record carries the id and `line_only` when none does. `line` is **1-based**, matching `Mirror.line`/`Task.line`/`Link.line`.

      **Read `tasks.md` with `parse_tasks`, never `load_tasks`.** `load_tasks` backfills missing ids and calls `_atomic_write` (src/choom/core/tasks.py:436), so using it here would write to the user's `tasks.md` merely because a key was pressed — before the confirmation, and on a gesture the user may be about to cancel. That is a direct FR-014 violation and it is a one-line mistake to make by reflex.

      Span rules are the four-row table in [data-model.md](./data-model.md) §3: whole line including its terminator; last-line-with-a-trailing-newline runs to end of text; last-line-*without* one instead absorbs the **preceding** terminator so no blank line is left behind; the only line spans the whole buffer. `extra_text` is true when the line has anything non-whitespace left after removing the `_MIRROR_PREFIX` match and the characters between `link_start` and `link_end`. Never raises: a missing `tasks.md` is `line_only`, an unreadable one carries the OS error in `message`.

      Same task: tests/unit/test_mirror_deletion.py (new) covering — `None` for prose, a heading, a blank line, frontmatter, `- [ ] buy milk` (no link), a checklist item whose only link is not a task link, and a task line inside a ``` fence and inside an inline code span; the invariant `plan.text == text[:plan.span[0]] + text[plan.span[1]:]` asserted on every non-refusing case; a blank line immediately above **and** below the removed line both surviving; indented continuation beneath the line surviving (deliberately unlike `tasks.md`, where the body span goes with the record); a nested/indented task line removed with its own leading whitespace and no neighbour reindented; the three last-line variants and the only-line case; `extra_text` true for trailing prose and for a second link on the line, false for a bare mirror; and `deletable` vs `line_only`
- [x] T006 Add the three refusing outcomes to `plan_mirror_deletion` in src/choom/core/mirrors.py, in the decision order fixed by [contracts/core-api.md](./contracts/core-api.md) §1 — `self_referential` first, then `deletable`, then `ambiguous_id`, then `unreadable_tasks`, then `line_only`. Each sets `text=""`, `span=(0, 0)`, and a `message` naming both the cause and the next step (Principle V).

      **The unreadable boundary is exact and must not be re-collapsed.** The blocking set is precisely `{"task_unterminated_comment", "task_malformed_comment"}` — the only two reasons where `parse_tasks` skips a line **without** producing a `Task` (src/choom/core/tasks.py:239-274, both branches `continue` before `_append_task`), which is why choom cannot tell "already deleted" from "sitting under a broken comment". `task_invalid_value` must **not** block: an invalid `created` date records a warning and then falls through to `_append_task` (tasks.py:290-310), so the task is still findable by id, and refusing there would break FR-022. Lines needing an id backfill also do not block — they have never had an id, so nothing can point at one.

      Same task: tests in tests/unit/test_mirror_deletion.py at that boundary specifically — an unresolvable id plus a `task_unterminated_comment` line gives `unreadable_tasks`; the same with a `task_malformed_comment` line gives `unreadable_tasks`; **an unresolvable id plus only a `task_invalid_value` warning gives `line_only`, not a refusal**; and a *resolvable* id in a file that also contains an unreadable line still gives `deletable` (FR-022 — one broken line never blocks the rest). Plus `ambiguous_id` when two records share the id (message naming both line numbers) and `self_referential` when `body_task_id` equals the line's task id (depends on T005)
- [x] T007 Implement `commit_mirror_deletion(workspace, plan) -> MirrorDeletion` in src/choom/core/mirrors.py per [contracts/core-api.md](./contracts/core-api.md) §2: `deletable` calls the existing `tasks.delete_task` and returns `plan`; `line_only` returns `plan` having opened nothing; any refusing outcome raises `UsageError`, because reaching here with one is a caller bug. **Add no new write primitive** — `delete_task` already guarantees the record's checkbox line and indented body span go, every other line stays byte-identical, and the file's line-ending and trailing-newline state survive. Export `plan_mirror_deletion`, `commit_mirror_deletion`, and `MirrorDeletion` from src/choom/core/__init__.py's import block and `__all__`, following the existing `find_mirrors` / `capture_task` entries. Same task: tests in tests/unit/test_mirror_deletion.py that `deletable` removes the record and leaves the rest of `tasks.md` byte-identical, that `line_only` writes nothing at all (compare bytes before and after), that each refusing outcome raises `UsageError`, and that `from choom.core import plan_mirror_deletion, commit_mirror_deletion` resolves (depends on T006)
- [x] T008 Run `scripts/dev-tests.sh tests/unit/test_mirror_deletion.py tests/unit/test_mirror_recognition.py` plus `uv run mypy src` and confirm green, then run the full `scripts/dev-tests.sh` and confirm the count is the T001 baseline plus the new tests with nothing failing — in particular `tests/integration/test_delete_mirrors.py`, which must be untouched by the `Mirror` field addition

**Checkpoint**: Every rule about what a deletion removes is implemented and proven against strings, with
no terminal involved. This is the Principle I claim made concrete — if it holds here, the TUI has nothing
left to decide.

---

## Phase 3: User Story 1 - Throw away a task the assistant invented (Priority: P1) 🎯 MVP

**Goal**: With the cursor on a task line, `ctrl+t` removes the task from the document and from `tasks.md`
after one confirmation.

**Independent Test**: Capture several tasks into a document, delete one with `ctrl+t`, and confirm the
document keeps every other line byte-for-byte while `tasks.md` keeps every other task.

**Also covers US2** (undo a mistyped `/task`), which spec.md states needs no additional behaviour — T013
proves it rather than reimplementing it.

- [x] T009 [P] [US1] Add `body_task_id: str | None = None` to `EditTarget` in src/choom/tui/edit_screen.py:68-84 per [contracts/tui.md](./contracts/tui.md) C9, and pass the task's id from `open_task_editor` (src/choom/tui/edit_screen.py:151, which already holds it) while leaving `open_editor` on the default. Defaulted, so both existing construction sites — the only two in the tree — stay valid. This is what makes FR-024's refusal possible; without it the editor cannot say *which* task's body it is
- [x] T010 [P] [US1] Extend `EDIT_HELP` in src/choom/tui/status_bar.py to `"ctrl+o save   ctrl+x save & back   ctrl+t delete task   esc discard   ctrl+q quit"` per [contracts/tui.md](./contracts/tui.md) C2. 81 characters, well inside the precedent set by `LIST_HELP` (115) and `TASK_LIST_HELP` (117); the `<= 80` assertion in tests/unit/test_footer_bindings.py is parametrized over `PREVIEW_HELP` and `LINKS_SECTION_HELP` only and must stay that way. Leave `LINK_PICKER_HELP` unchanged — `ctrl+t` is inert while the picker is open and an inert key is not advertised
- [x] T011 [US1] Add `Binding("ctrl+t", "delete_task", "Delete task", show=True)` to `EditorPane.BINDINGS` in src/choom/tui/edit_screen.py:322-337 — **without `priority=True`**, unlike the neighbouring `ctrl+o`/`ctrl+s`/`ctrl+x`. Those need priority because `TextArea` binds them itself; `ctrl+t` is unbound at `TextArea`, `Screen`, and `App`, and `Key("ctrl+t", "\x14").is_printable` is `False` so `TextArea._on_key` neither consumes nor inserts it. A priority binding would also fire while the link picker has focus, which is the opposite of what C3 wants. Same task: extend `check_action` at src/choom/tui/edit_screen.py:384-400 to return `False` for `"delete_task"` when `self._link_picker_line is not None` or `self._request is not None` (FR-004), and add tests to tests/integration/test_editor_task_delete_tui.py (new) that `ctrl+t` does nothing while an `/ai` request is in flight and nothing while the picker is open. The footer pairing needs no new test — tests/unit/test_footer_bindings.py already covers it; run it to confirm (depends on T010)
- [x] T012 [US1] Give `EditorPane._save` an optional leading note — `_save(self, note: str | None = None) -> bool` in src/choom/tui/edit_screen.py:421 — which it folds into whatever it renders instead of the caller rendering separately afterwards. Per [contracts/tui.md](./contracts/tui.md) C6 step 4 this is what stops the deletion's success message racing `_save`'s own status render, and it is what lets a save warning (most importantly the dead-line warning for a second copy of the same task, FR-025) be shown *with* the deletion note rather than instead of it. All existing call sites keep working unchanged. Same task: confirm tests/integration/test_edit_save_tui.py and tests/integration/test_ai_command_tui.py still pass
- [x] T013 [US1] Implement `action_delete_task` on `EditorPane` in src/choom/tui/edit_screen.py per [contracts/tui.md](./contracts/tui.md) C4–C8: read `cursor_location`'s row (a multi-line selection is ignored — only the cursor's row counts), call `plan_mirror_deletion` with `row + 1`, return early with a status note on `None` or a refusing outcome, otherwise push the existing `ConfirmDialog` with the C5 wording and `cancel_label="Keep It"` / `confirm_label="Delete"`, and on confirm run `commit_mirror_deletion` → widget edit → `_save(note)`.

      **Remove the line with `editor.delete(...)`, never `editor.text = plan.text`.** The `text` setter is a documented alias of `load_text`, which opens with `self.history.clear()` — assigning it would destroy the user's entire session undo history, not just this step. Convert core's offsets with Textual's own `editor.document.get_location_from_index(...)` and call `editor.delete(start_loc, end_loc, maintain_selection_offset=False)`, which records one undoable `Edit`. `maintain_selection_offset=False` also lands the cursor at the span's start, which is FR-032 with no extra code and no scroll call.

      The confirmation question must carry the **"and the document is saved"** clause from C5: `ctrl+t` commits unrelated unsaved edits in the buffer (FR-028/FR-030), and the user most at risk is the one with a half-written paragraph elsewhere. One dialog, no second stage (FR-009).

      Same task: tests in tests/integration/test_editor_task_delete_tui.py for the happy path — dialog appears quoting the description, Enter removes the line from the buffer and the task from `tasks.md`, the status names the deleted task, every other line of the document and every other task record is byte-identical, and the deleted task is gone from the Tasks collection. Plus **the bridge assertion `editor.text == plan.text` after the widget edit** ([contracts/tui.md](./contracts/tui.md) C6), which is what fails the suite if the adapter ever starts computing its own removal. Plus a **US2** case: a task captured with `/task` earlier in the same editing session deletes identically to one seeded before the editor opened. Plus the FR-011 case: a line with trailing prose raises a dialog whose text says the rest of the line goes too (depends on T007, T009, T011, T012)
- [x] T014 [US1] Add the cancel test to tests/integration/test_editor_task_delete_tui.py: with an unrelated half-written edit sitting in the buffer, press `ctrl+t` on a task line and dismiss with Esc, then assert **nothing at all was written** — `tasks.md` byte-identical, the document byte-identical (so the buffer was *not* saved), and the pane still reporting unsaved changes. FR-014 is the user's last no-effect exit and the confirmation now promises it in words, so the promise needs a test behind it rather than resting on the early return
- [x] T015 [US1] Add the undo test to tests/integration/test_editor_task_delete_tui.py, pinning the behaviour decided in [research.md](./research.md) R2: after a confirmed deletion, the editor's undo restores the line in the buffer, the task record stays deleted, and saving reports the restored line as pointing at a task that no longer exists. Assert the session's earlier undo history survived the deletion — i.e. an edit made *before* the `ctrl+t` is still undoable — which is the property `editor.text = ...` would have destroyed. Use a task-body editor or otherwise avoid a frontmatter stamp for the history assertion, since `_save`'s pre-existing `editor.text = result.saved_text` at src/choom/tui/edit_screen.py:445-453 clears history on its own when the stamp changes the buffer; **do not "fix" that pre-existing behaviour here** — it predates this feature and is out of scope

**Checkpoint**: US1 and US2 fully functional. `ctrl+t` deletes from both places, cancel is a total no-op,
and undo behaves as decided.

---

## Phase 4: User Story 3 - The key does nothing on a line that is not a task (Priority: P1)

**Goal**: `ctrl+t` off a task line raises no dialog, writes no file, and says so briefly.

**Independent Test**: Press `ctrl+t` on prose, a heading, a blank line, a plain checklist item, and a
task line inside a code fence; confirm no dialog and no write in every case.

**Implementation is already in place** — T013's early return on `plan_mirror_deletion` returning `None`,
which T005 established. This phase proves it at the gesture level, which is where Principle V's
"confirmations fire only when there is something to lose" is actually observable.

- [x] T016 [US3] Add the no-op tests to tests/integration/test_editor_task_delete_tui.py: `ctrl+t` with the cursor on ordinary prose, on a heading, on a blank line, inside frontmatter, on `- [ ] buy milk` (a checklist item with no link), on a checklist item whose only link is not a task link, and on a task line inside a ``` fence. For each, assert **no `ConfirmDialog` is on the screen stack**, `tasks.md` is byte-identical, the document is byte-identical, and the status bar shows the non-warning note `no task on this line`. The dialog assertion is the load-bearing one: a dialog for a no-op is the reflex-dismissal failure the constitution warns about, and a test that only checked "nothing was written" would pass while still teaching users to dismiss it

**Checkpoint**: The destructive binding is provably inert on every line that is not a task line.

---

## Phase 5: User Story 4 - Clean up a task line whose task is already gone (Priority: P2)

**Goal**: A task line whose record was deleted elsewhere can be removed from the document, without
touching `tasks.md`.

**Independent Test**: Delete a task through the task list, reopen the document that mirrors it, and
confirm `ctrl+t` removes the line, leaves `tasks.md` byte-identical, and says which of the two it did.

- [x] T017 [US4] Add the `line_only` tests to tests/integration/test_editor_task_delete_tui.py: seed a document with a captured task, delete the task through `core.deletion.delete_by_id` (the same path the list view's `ctrl+d` uses), reopen the document, and press `ctrl+t` on the stale line. Assert the dialog's wording states the task is already absent and that only the line goes (FR-012), that confirming removes the line from the document, and that `tasks.md` is **byte-identical before and after** — the file is never opened for writing when there is no record to remove

**Checkpoint**: The drift case that already exists in shipped workspaces is resolvable from the editor.

---

## Phase 6: User Story 5 - A task list choom cannot fully parse stops the deletion (Priority: P2)

**Goal**: When the id does not resolve and `tasks.md` has an unreadable line, nothing is written and the
message says why.

**Independent Test**: Break one metadata comment, press `ctrl+t` on a task line whose id does not
resolve, and confirm neither file is written and the message names the unreadable line.

- [x] T018 [US5] Add the refusal tests to tests/integration/test_editor_task_delete_tui.py: with a hand-broken metadata comment in `tasks.md` (an unterminated `<!--`), press `ctrl+t` on a task line whose id does not resolve and assert **no dialog appears**, both files are byte-identical, and the status names the unreadable line and the next step. Then, in the same broken workspace, press `ctrl+t` on a task line whose id **does** resolve and assert it deletes normally — the FR-022 half, proven at the gesture level as well as the unit level, because collapsing the two is exactly the regression T006's boundary tests exist to catch

**Checkpoint**: All five user stories functional and independently verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: The requirements that are not user stories, the platform checks, and the gates.

- [x] T019 [P] Add the FR-023 and FR-024 refusal tests to tests/integration/test_editor_task_delete_tui.py: a duplicate id across two task records refuses with a message naming both line numbers and writes nothing; and `ctrl+t` inside a task's own body editor, on a task line for **that same** task, refuses with an explanation and writes nothing. Also assert the case that must keep working — deleting a *different* task from inside a task body editor succeeds, which is safe only because `delete_task` and `set_task_body` both re-read and locate by id rather than by a cached line number
- [x] T020 [P] Add the FR-025 test to tests/integration/test_editor_task_delete_tui.py: a document mirroring the same task on two lines, with the cursor on one. Assert the task record is deleted, **only the cursor's line** is removed, the other line is left exactly as it was, and the status reports that a line still points at a task that no longer exists. No new code should be needed — the report comes from `reconcile_on_save`'s existing dead-mirror warning surfacing through `_save`; if it does not appear, fix the wiring in T012's note fold-in rather than adding a second warning path
- [x] T021 [P] Add the FR-031 partial-failure test to tests/integration/test_editor_task_delete_tui.py: make the document unwritable so the save fails after the record has been removed, and assert the task is gone, the buffer keeps the line removed and is still marked unsaved, the save's own message is shown, and **nothing the user typed is lost**. Follow the pattern in tests/integration/test_save_failure.py
- [x] T022 [P] Add a CRLF end-to-end case to tests/integration/test_editor_task_delete_tui.py: a document with `\r\n` endings and no trailing newline, deleted through the full gesture, still `\r\n` and still without a trailing newline afterwards. **No new source should be required** — `load_for_edit` normalises the buffer to LF and `_apply_line_ending_policy` restores both properties on write, so if this test needs production code to pass, the removal is doing something it should not
- [x] T023 [P] Parametrize the core happy-path case in tests/integration/test_editor_task_delete_tui.py across both hosts — the inline pane opened from the list and the full-screen editor — proving FR-001's "identical in each". Parametrize only where the host could plausibly matter; do not duplicate every case into two files
- [x] T024 Verify cross-platform behaviour per the plan's platform gate: a workspace path with spaces and non-ASCII characters, and a task description with non-ASCII characters, both survive the gesture verbatim. Character offsets into a Python `str` cannot split a multi-byte description mid-character; add a case that would catch it if the implementation ever moved to byte offsets. Extend tests/integration/test_unicode_paths.py rather than creating a new file
- [x] T025 **Leave README.md alone — this is a deliberate skip, not an oversight.** Per CLAUDE.md the README feature list describes the *released* version and closes with "Everything above has landed on `main` as of vX.Y.Z"; `/release` folds a version's user-visible changes in when it cuts that version. Adding or extending a bullet for this unreleased work — including appending a sentence to the existing editor bullet, which is the same error in a harder-to-spot form — would promise behaviour a reader installing from PyPI does not get. The feature is recorded in this feature's own `specs/017-editor-task-delete/` artifacts instead, which is what a "document it" task is actually for at implementation time. Confirm no README.md edit appears in the diff
- [ ] T026 Run [quickstart.md](./quickstart.md) end to end by hand against a scratch workspace under `/tmp`, including step 7's `diff` check that a deletion produces exactly two hunks (the removed line and the `updated:` stamp) with both adjacent blank lines and the indented continuation surviving
  - **Deferred.** This needs a live terminal running the TUI interactively under `pilot`-free conditions — this session can drive `pilot` against a headless app, but not a hand at a real keyboard watching `diff` output scroll by. The automated integration suite (`test_editor_task_delete_tui.py`, `test_unicode_paths.py`) covers every scenario quickstart.md walks through, including the exact two-hunk byte-diff claim (T013's happy path plus the CRLF and unicode cases), but the by-hand walkthrough itself is left unticked rather than fabricated.
- [ ] T027 Verify the TUI on the target terminals in `docs/REQUIREMENTS.md` §4.3 — confirm `ctrl+t` actually arrives (it is not intercepted by any of them) and the extended footer renders without breaking the status bar at 80 columns
  - **Deferred.** This needs each target terminal (Windows Terminal, iTerm2, macOS Terminal, PuTTY, tmux) running interactively — a visual, terminal-hosted check this session cannot perform headlessly, on the same terms feature 016 deferred its own equivalent task. Left unticked rather than fabricated. Deferred to the pre-release verification gate the constitution's Development Workflow section already requires ("TUI changes MUST be verified before release on the target terminals listed in `docs/REQUIREMENTS.md`") — a release-time activity, not a per-PR one.
- [x] T028 Run the full gate: `scripts/dev-tests.sh` plus `uv run ruff format --check . && uv run ruff check . && uv run mypy src`. Confirm green, confirm `tests/integration/test_delete_mirrors.py` still passes unchanged (the deliberate `choom task delete` asymmetry is intact), and confirm the diff touches no CLI file — `src/choom/cli/` must be untouched, which is the structural form of the plan's Principle II claim

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks every user story**
- **US1 (Phase 3)**: depends on Phase 2. The MVP
- **US3 (Phase 4)**: depends on Phase 3 (its behaviour is T013's early return)
- **US4 (Phase 5)**, **US5 (Phase 6)**: depend on Phase 3; independent of each other and of US3
- **Polish (Phase 7)**: depends on all stories

### Within Phase 2

T003 and T004 are independent of each other. T005 depends on both. T006 depends on T005, T007 on T006,
T008 on T007. The order is deliberate: each task leaves `plan_mirror_deletion` correct as far as it goes,
so the tree is green at every checkpoint rather than only at the end.

### Within Phase 3

T009 and T010 are independent. T011 depends on T010 (the footer test pairs the binding with the string).
T013 depends on T007, T009, T011, and T012. T014 and T015 depend on T013.

### Parallel Opportunities

- T003 ∥ T004 (different concerns, one file — coordinate the single edit to `models.py`)
- T009 ∥ T010 (different files)
- T019 ∥ T020 ∥ T021 ∥ T022 ∥ T023 (all additive cases in one new test file — coordinate the file, or
  land them sequentially; none depends on another's code)
- Phases 5 and 6 can run in parallel once Phase 3 is done

---

## Implementation Strategy

### MVP

Phases 1–3. That delivers the whole reported problem: a task line the user did not want, gone from both
places in one gesture, with cancel a total no-op and undo behaving predictably. Phase 4 should follow
immediately rather than being deferred — it is the safety half of a destructive binding, and shipping the
key without proving it inert off a task line is not a smaller MVP, it is an unfinished one.

### Increments

1. Phase 2 → the destructive logic exists and is proven, but nothing can fire it
2. Phase 3 → `ctrl+t` works (MVP)
3. Phase 4 → proven inert everywhere else
4. Phases 5–6 → the two drift cases
5. Phase 7 → the remaining FR edges, platform checks, gates

---

## Notes

- **No README task exists, deliberately.** The tasks template would generate one; it is omitted per
  CLAUDE.md and the reason is recorded as T025 so a reviewer sees the decision rather than a gap.
- **No `contract/` test task.** This feature adds no CLI command, flag, `--json` key, or exit code.
  `tests/contract/test_cli_delete.py` already covers `task delete` and stays untouched — T028 checks that
  `src/choom/cli/` has no diff at all.
- **No `performance/` test task.** No budget to protect; see the header.
- **Two mistakes to watch for, both one-liners, both called out in the task text where they would be
  made**: `load_tasks` instead of `parse_tasks` in the planning path (T005 — it writes), and
  `editor.text = ...` instead of `editor.delete(...)` in the gesture (T013 — it clears undo history).
- The pre-existing undo-clearing in `EditorPane._save` (edit_screen.py:445-453) is **out of scope**. It
  predates this feature; T015 works around it rather than fixing it.
- Commit after each task or logical group. Stop at any checkpoint to validate independently.
