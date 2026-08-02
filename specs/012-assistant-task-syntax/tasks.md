---

description: "Task list for 012-assistant-task-syntax"
---

# Tasks: Linked Task Syntax for AI Assistant

**Input**: Design documents from `/specs/012-assistant-task-syntax/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included. The constitution's Development Workflow requires behaviour changes to land with the
tests that cover them, and Principle VI makes that coverage risk-based rather than one test per acceptance
scenario — research R11 assigns each behaviour to the layer where it can actually break. This feature is
weighted to `unit/`, because its failure modes are string classification and partial failure.

**Test runner**: `scripts/dev-tests.sh` (repo `CLAUDE.md`), never a hand-rolled `pytest`. Args pass
through: `scripts/dev-tests.sh tests/unit -k reply`.

**Organization**: Tasks are grouped by user story. Story order is *not* quite the build order — US3's
rules are additions to the classifier US1 builds, so US1 ships a classifier that enforces the editor's
existing whole-line rule and US3 adds fence tracking on top. Each story is still independently testable at
its checkpoint.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths in every description

## Path Conventions

Single project: `src/choom/`, `tests/` at repository root.

---

## Phase 1: Setup

**Purpose**: Establish a known-good starting point on the merged branch

- [X] T001 Run `scripts/dev-tests.sh` and record the green baseline, so any later failure is attributable
      to this feature
- [X] T002 [P] Re-read `_finish_request` in `src/choom/tui/edit_screen.py` and confirm research R5 and R6
      still hold on the merged branch: the superseded check runs before the buffer is touched, and the
      insert is a single `editor.replace()` of the `⋯` placeholder span
- [X] T003 [P] Re-read `AssistantProfile.parse_reply` in `src/choom/core/assistants.py` and confirm the
      string reaching `AssistantReply.text` is the assistant's final answer with tool-call narration
      already stripped (#69), which is what the classifier will receive

**Checkpoint**: Baseline green, both wiring assumptions verified against the merged code

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shapes every later phase returns and consumes

**⚠️ Blocks every user story phase.**

- [X] T004 Add `ReplyLine` (frozen, slots: `text: str`, `task: ParsedCommand | None`) and `ReplyCapture`
      (frozen, slots: `text: str`, `tasks: tuple[Task, ...]`, `warnings: tuple[ScanWarning, ...]`) to
      `src/choom/core/models.py`, with docstrings stating the invariants in data-model.md §"New shapes"
- [X] T005 Add `"reply_capture_failed"` to the `ScanWarningReason` literal in
      `src/choom/core/models.py` (additive; no reader enumerates it exhaustively)
- [X] T006 Re-export `ReplyLine`, `ReplyCapture`, `parse_reply_lines`, and `capture_reply_tasks` from
      `src/choom/core/__init__.py`, in the existing alphabetical `__all__` order

**Checkpoint**: The shapes exist and import cleanly; `scripts/dev-tests.sh` still green

---

## Phase 3: User Story 1 - Ask for my commitments and get real tasks (Priority: P1) 🎯 MVP

**Goal**: A reply's task lines become real tasks and mirrors; its prose lands untouched

**Independent Test**: Run an `/ai` request whose reply interleaves prose and task lines. Each task line
becomes a checklist item linking to a task with the right description, type, and tags; the prose is
unchanged and in order; the editor does not move; the status bar reports the count.

- [X] T007 [P] [US1] Unit tests for the classifier's whole-line rule in `tests/unit/test_reply_lines.py`:
      one `ReplyLine` per input line in order, `/task ...` and `/task.followup ...` eligible, a leading-space
      line not eligible, `Did you know you can type /task here?` not eligible, `/ai ...` and `/link ...` not
      eligible, `/task` with no description eligible with an empty argument, CRLF input. Must fail first
- [X] T008 [P] [US1] Unit tests for the capture walk's success path in
      `tests/unit/test_capture_reply_tasks.py`: each eligible line replaced by its mirror, every other line
      byte-identical, line count and order preserved, tasks returned in reply order, `#tags` and the `.type`
      suffix reaching the task, and a reply with no eligible lines returning its input **unchanged**
      (identity, not equality). Must fail first
- [X] T009 [US1] Implement `parse_reply_lines(text: str) -> tuple[ReplyLine, ...]` in
      `src/choom/core/editor_commands.py` — rules 2–4 of contracts/reply-capture.md §2 only, calling
      `parse_line` rather than restating the grammar. Pure, raises nothing, docstring states both
      (fence tracking is US3's task T022)
- [X] T010 [US1] Implement `capture_reply_tasks(workspace, text, *, source, source_id) -> ReplyCapture` in
      `src/choom/core/mirrors.py` — classify, capture each eligible line through the existing
      `capture_task`, substitute the returned mirror line, preserve order. Success path only; per-line
      failure recovery is US5's task T029. Docstring states what it raises (depends on T009)
- [X] T011 [US1] Add `captures_tasks: bool` to `EditTarget` in `src/choom/tui/edit_screen.py`; set `True`
      in `open_editor`, `False` in `open_task_editor`, and move `_capture_task`'s guard onto it, replacing
      the `stamps_frontmatter` overload and the comment that explained it (research R3)
- [X] T012 [US1] Call `capture_reply_tasks` from `_finish_request` in `src/choom/tui/edit_screen.py` —
      after the superseded check, only when `reply.ok` and `self.target.captures_tasks`, inserting
      `ReplyCapture.text` through the existing single `editor.replace()` (research R5, R6; depends on T010,
      T011)
- [X] T013 [US1] Seed `self._mirror_baseline[task.id] = False` for every task in `ReplyCapture.tasks` in
      `src/choom/tui/edit_screen.py`, at the same point `_capture_task` does it for a typed capture
      (FR-023, research R9)
- [X] T014 [US1] Add `warn: bool = True` to `_render_status` in `src/choom/tui/edit_screen.py` and report
      the success count without the `⚠` prefix — `1 task captured` / `N tasks captured`, nothing at all
      when no line was eligible (research R8; the failure wordings are US5's task T025)
- [X] T015 [US1] Add a `reply_with_tasks` mode to `_STUB_SOURCE` in `tests/conftest.py` printing prose and
      task lines interleaved, including one `/task.followup ... #tag` line
- [X] T016 [US1] Integration test in `tests/integration/test_ai_command_tui.py` using
      `reply_with_tasks`: mirrors in the buffer at the right lines, prose byte-identical and in order,
      `tasks.md` holding tasks with the right description, type, tags, and source link, the status bar
      carrying the count without `⚠`, and the editor still focused on the same screen (depends on T012–T015)

**Checkpoint**: US1 is shippable — a reply's task lines become real, linked tasks; the feature's substance

---

## Phase 4: User Story 2 - The assistant is told the grammar, on the same terms every time (Priority: P2)

**Goal**: Every configured assistant receives one identical task syntax instruction

**Independent Test**: Compose a prompt for each profile and confirm both carry the same clause, stating
the form, the whole-line rule, the tag lifting, and what happens to the line.

- [X] T017 [P] [US2] Unit tests in `tests/unit/test_compose_prompt.py`: the clause present with
      `task_capture=True`, absent with `task_capture=False`, and identical across every profile in
      `PROFILES`. Update the three existing call sites there and in
      `tests/integration/test_unicode_paths.py` for the new keyword. Must fail first
- [X] T018 [US2] Add the `_TASK_SYNTAX` constant to `src/choom/core/assistants.py` — both forms, `#tags`
      lifted, whole-line/unindented/outside-a-fence, the line becomes a link to the task choom creates,
      optional — placed after the "Do not edit any file" bullet and reconciling itself with it
      (contracts §1, research R4)
- [X] T019 [US2] Add the required keyword-only `task_capture: bool` to `compose_prompt` in
      `src/choom/core/assistants.py`, appending `_TASK_SYNTAX` only when true (depends on T018)
- [X] T020 [US2] Pass `task_capture=self.target.captures_tasks` from `_start_ai_request` in
      `src/choom/tui/edit_screen.py` (depends on T019, T011)

**Checkpoint**: The grammar reaches the assistant, identically, and never where it cannot be used

---

## Phase 5: User Story 3 - Nothing is captured by surprise (Priority: P3)

**Goal**: A reply that describes the syntax creates nothing

**Independent Test**: Drive a reply containing the command inside a code fence, indented under a bullet,
and mid-sentence. No task is created and every line is inserted as written.

- [X] T021 [P] [US3] Unit tests for fence tracking in `tests/unit/test_reply_lines.py`: a backtick fence,
      a tilde fence, a fence with an info string, a closing fence longer than its opener, a fence never
      closed (everything after it ineligible), a four-space-indented block, and a task line immediately
      after a closed fence still eligible. Must fail first
- [X] T022 [US3] Add fence tracking to `parse_reply_lines` in `src/choom/core/editor_commands.py` per
      contracts/reply-capture.md §2 — opener of three or more backticks or tildes after at most three
      leading spaces; closer of the same character, at least as long, no info string; unclosed means
      everything after it is inside (depends on T009)
- [X] T023 [P] [US3] Add a `reply_explaining` mode to `_STUB_SOURCE` in `tests/conftest.py` printing an
      explanation with a fenced `/task` example and an inline mention
- [X] T024 [US3] Integration test in `tests/integration/test_ai_command_tui.py` using `reply_explaining`:
      the reply lands verbatim, `tasks.md` is unchanged, and no capture count appears in the status bar.
      Confirm `test_reply_containing_a_slash_ai_line_is_inserted_as_literal_text` still passes unchanged
      (depends on T022, T023)

**Checkpoint**: The boundary holds — SC-005 is provable

---

## Phase 6: User Story 4 - The captured tasks behave like every other task (Priority: P4)

**Goal**: Provenance and two-way mirroring, inherited from 009 rather than reimplemented

**Independent Test**: Capture tasks from a reply inside a meeting, then confirm the task names the
meeting, the meeting's inbound links list the task, and completing it from either end updates the other.

- [X] T025 [P] [US4] Unit test in `tests/unit/test_capture_reply_tasks.py`: a task captured from a reply
      and one captured by `capture_task` with the same words produce lines differing only in id and
      timestamp (FR-021, SC-003)
- [X] T026 [US4] Extend the US1 integration test in `tests/integration/test_ai_command_tui.py`: complete
      one captured task from the tasks list and confirm the note's checklist item ticks; tick another in
      the note, save, and confirm the task completes — the reconcile paths 009 already owns
- [X] T027 [P] [US4] Test in `tests/integration/test_ai_command_tui.py` that a second save straight after
      an insert writes no spurious state change back to `tasks.md`, proving the baseline seeding of T013
      (FR-023)

**Checkpoint**: A reply-captured task is indistinguishable in behaviour from a typed one

---

## Phase 7: User Story 5 - A failed capture never costs the reply (Priority: P5)

**Goal**: Every line of the reply reaches the document under every failure

**Independent Test**: Make `tasks.md` unwritable, run a request whose reply contains task lines, and
confirm the whole reply lands, the failing lines are present as text, and a message names the failure.

- [X] T028 [P] [US5] Unit tests for partial failure in `tests/unit/test_capture_reply_tasks.py`: one
      failure among several (the rest still captured, in order), every capture failing (text identical to
      input, one warning per eligible line), `/task` with no description landing as text with a warning,
      a description that is only tags, and an unwritable `tasks.md`. Assert no line is ever lost. Must fail
      first
- [X] T029 [US5] Add per-line recovery to `capture_reply_tasks` in `src/choom/core/mirrors.py`: catch
      exactly `UsageError` and `WorkspaceError`, leave the line as written, record
      `ScanWarning(path=workspace.tasks_file, reason="reply_capture_failed", message=str(exc))`, continue
      to the next line. Anything else propagates (research R10; depends on T010)
- [X] T030 [US5] Compose the failure wordings in `src/choom/tui/edit_screen.py` per contracts §4:
      `N tasks captured; M could not be: <first reason>` with `⚠`, and the reason alone with `⚠` when
      everything failed (depends on T014, T029)
- [X] T031 [US5] Integration test in `tests/integration/test_ai_command_tui.py`: with `tasks.md` made
      read-only, every reply line reaches the buffer, the task lines are present as the assistant wrote
      them, and the status bar names the failure. Skip on Windows where the existing suite already does for
      permission-dependent cases (depends on T029, T030)
- [X] T032 [P] [US5] Test in `tests/integration/test_ai_command_tui.py` that a cancelled request whose
      reply would have contained task lines creates no task and restores the `/ai` line (FR-019, research
      R5)

**Checkpoint**: Principle IV holds under every failure this feature can produce

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T033 [P] Update the `/ai` bullet in `README.md` — what the assistant may now emit and what happens
      to it
- [X] T034 [P] Update the inline task capture bullet in `README.md` — the same syntax is available to the
      assistant, and a reply's task lines are captured on identical terms
- [X] T035 Confirm `src/choom/core/templates/AGENTS.md.tmpl` is deliberately unchanged and record why in
      the PR description (research R12): the prompt is self-contained, and duplicating the clause would
      split the one string FR-006 keeps single
- [X] T036 Run `scripts/dev-tests.sh` — full suite green on the baseline from T001, plus format, lint, and
      type checks
- [X] T037 Walk [quickstart.md](./quickstart.md) by hand in a scratch workspace with a real assistant
      installed, at least for US1 and US3 — the one thing no stub can prove is that an assistant actually
      emits the line when told about it

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: blocks every user story phase
- **US1 (Phase 3)**: needs Phase 2
- **US2 (Phase 4)**: needs Phase 2; T020 also needs T011 from Phase 3
- **US3 (Phase 5)**: needs T009 from Phase 3 — it extends that function
- **US4 (Phase 6)**: needs Phase 3 complete
- **US5 (Phase 7)**: needs T010 and T014 from Phase 3
- **Polish (Phase 8)**: after the stories being shipped are complete

### The one inversion worth stating

US3 is a P3 story that modifies code US1 (P1) writes. That is deliberate: the whole-line rule US1 needs is
the editor's existing rule, and fence tracking is a separate addition with its own failure mode. Building
them in story order would mean writing `parse_reply_lines` twice or shipping US1 with rules it does not
need.

If US1 is shipped alone as an MVP, a reply whose fenced example contains a task line **would** capture it.
That is the known gap the checkpoint leaves open, and it is why US3 follows immediately rather than being
deferred.

### Parallel Opportunities

- T002 and T003 are independent reads: parallel
- T007 and T008 are two different test files: parallel, and both must fail before T009/T010 land
- T017 (US2 tests) is independent of everything in Phase 3 except T020's call site — Phase 4 can be built
  alongside Phase 3
- T021 and T023 touch different files: parallel
- T025, T027, T028, and T032 are independent test tasks: parallel
- T033 and T034 are two bullets in one file — sequential in practice, though independent in content

---

## Parallel Example: Phase 3 opening

```bash
Task: "Unit tests for the classifier's whole-line rule in tests/unit/test_reply_lines.py"
Task: "Unit tests for the capture walk's success path in tests/unit/test_capture_reply_tasks.py"
Task: "Unit tests for the prompt clause in tests/unit/test_compose_prompt.py"
```

---

## Implementation Strategy

### MVP (US1 alone)

Phase 1 → Phase 2 → Phase 3. A reply's task lines become real, linked tasks with the count reported.
Shippable, with the fence gap noted above and no prompt instruction yet — useful immediately to anyone who
tells the assistant the syntax in their own `/ai` prompt.

### Recommended increment

Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5. This is the feature as specified: the assistant is told
the grammar, emits it, and nothing is captured by surprise.

### Finishing

Phase 6 (verification that costs no new source), Phase 7 (the failure guarantees), then Phase 8.

---

## Notes

- `[P]` = different files, no dependencies
- Every behaviour change lands with its test, in the same commit where practical
- Verify each test fails before writing the implementation it covers
- No test may sleep or read the wall clock (Principle VI)
- The classifier must never lose a line — assert line counts, not just contents
- Stop at any checkpoint to validate a story independently
