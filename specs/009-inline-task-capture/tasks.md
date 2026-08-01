---

description: "Dependency-ordered tasks for 009-inline-task-capture"
---

# Tasks: Inline Task Capture

**Input**: Design documents from `/specs/009-inline-task-capture/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. Constitution Principle VI requires every user-facing behaviour to be covered, with the
layer and the count chosen by risk rather than generated from acceptance scenarios. Coverage here is
concentrated on the three things that can actually break: mirror recognition, the byte-preservation of the
splice, and the save-time conflict matrix. One performance test guards the only new hot path.

**Organization**: Grouped by user story so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: The user story this serves (US1…US7)
- Every task names the exact file it touches

## Path Conventions

Single Python package at the repository root: `src/endpaper/{core,cli,tui}/`, tests in
`tests/{unit,integration,contract,performance}/`.

---

## ⚠️ Hard prerequisite

`008-document-links` must be merged before any task below is started. This feature consumes `find_links`,
`resolve_id`, `relative_destination`, `Task.links`, `render_task_line(links=…)`, and `ScanWarningReason`
from it, and reimplements none of them. T001 is the gate.

---

## Phase 1: Setup

**Purpose**: Confirm the dependency landed and create the module this feature lives in.

- [ ] T001 Confirm `008-document-links` is merged into this branch and its surface is importable: `find_links`, `resolve_id`, `relative_destination` from `src/endpaper/core/links.py`, plus `Task.links` and `render_task_line(links=…)` in `src/endpaper/core/tasks.py`. If any is absent, stop — nothing below can be built on a partial link primitive.
- [ ] T002 Create `src/endpaper/core/mirrors.py` with a module docstring stating its scope: the edge between a checkbox in a document and a task in `tasks.md`, owning recognition, splicing, conflict resolution, and the non-stamping write — and owning neither the link grammar (`links.py`) nor `tasks.md` itself (`tasks.py`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The records and the parser changes every story below needs.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 Add `Mirror`, `MirrorResolution`, and `MirrorReport` frozen dataclasses to `src/endpaper/core/models.py` per [data-model.md](data-model.md#in-memory); add `"mirror_conflict"` and `"mirror_ambiguous"` to `ScanWarningReason`; add `suffix: str = ""` to `ParsedCommand` and `accepts_suffix: bool = False` to `EditorCommand`. Dead mirrors reuse 008's `"link_dead"` rather than gaining a third reason.
- [ ] T004 [P] Add `links: Sequence[str] = ()` to `add_task` in `src/endpaper/core/tasks.py`, passed straight through to `render_task_line`. A call without it must produce a line identical to today's.
- [ ] T005 [P] Unit test in `tests/unit/test_task_add_links.py`: a task added with links renders the field between `tags` and `created`; a task added without them is byte-identical in shape to what `add_task` writes today (FR-019).
- [ ] T006 Teach `parse_line` the dotted verb suffix in `src/endpaper/core/editor_commands.py` — one `partition(".")` on the verb before the table lookup, mirroring `src/endpaper/tui/command_bar.py:114` so the editor and the command bar never disagree about what `/task.followup` means. A suffix on a command whose `accepts_suffix` is `False` parses and is rejected by the dispatcher with a message, never silently discarded.
- [ ] T007 [P] Extend `tests/unit/test_editor_commands.py`: `/task.followup call Terry` yields verb `task`, suffix `followup`, argument `call Terry`; `/task call Terry` yields an empty suffix; `/ai.foo bar` parses with a suffix the dispatcher will reject; a line that is not entirely a command still returns `None`.
- [ ] T008 Export the new names from `src/endpaper/core/__init__.py` and extend `tests/unit/test_core_imports.py` to guard them.

**Checkpoint**: Records exist, `/task.followup` parses, and a task can carry links. Stories can begin.

---

## Phase 3: User Story 1 — Capture a followup without leaving the editor (Priority: P1) 🎯 MVP

**Goal**: `/task.followup call Terry about the renewal #procurement` on its own line creates the task and
leaves a checklist item linking to it, with the cursor at the end of that line and nothing on screen moved.

**Independent Test**: Open a document, type the command, press enter. A task appears in the tasks list with
the right description, type, and tags; the document shows a checklist item pointing at it; the editor did
not move.

### Tests for User Story 1

- [ ] T009 [US1] Integration test in `tests/integration/test_inline_capture.py`: submitting the command creates the task with the description, type, and tag parsed identically to the command bar, records the source document in `links`, and returns the mirror line to insert. TUI-only — the gesture is inherently interactive, so there is no CLI arm to parametrize across.
- [ ] T010 [P] [US1] Unit test in `tests/unit/test_mirror_line.py`: the destination is correct from `meetings/YYYY/MM/`, from `notes/daily/YYYY/MM/`, and from a document outside the dated layout — the depth table in [contracts/mirror-format.md](contracts/mirror-format.md#the-line). Assert no `../` prefix is constructed by this feature.
- [ ] T011 [P] [US1] Unit test in `tests/unit/test_capture_task.py` for the failure modes: an empty description raises before anything is written; a rejected type or tag token raises and writes nothing; a task is created with exactly one link.

### Implementation for User Story 1

- [ ] T012 [US1] Implement `mirror_line(task, *, source, tasks_file)` in `src/endpaper/core/mirrors.py`. The destination comes from `links.relative_destination`; the link text is the task's stored description with tags already extracted. Pure string arithmetic, touches no filesystem.
- [ ] T013 [US1] Implement `capture_task(workspace, description, *, type, source, source_id, now)` in `src/endpaper/core/mirrors.py`, returning `(Task, mirror_line)`. Everything about the task's shape goes through `tasks.add_task` (FR-004); this adds the link and the mirror and nothing else. It deliberately does not save `source` — the caller does, because only the caller knows whether the buffer is dirty.
- [ ] T014 [US1] Register `EditorCommand(name="task", argument="<description>", requires_argument=True, accepts_suffix=True)` in `EDITOR_COMMANDS` in `src/endpaper/core/editor_commands.py`, with a description that says the line becomes a link to the task.
- [ ] T015 [US1] Dispatch `/task` in `EditScreen._on_editor_command_submitted` in `src/endpaper/tui/edit_screen.py`, alongside the existing `/ai` branch.
- [ ] T016 [US1] Implement the capture sequence in `src/endpaper/tui/edit_screen.py` in the order fixed by [research R8](research.md#r8-the-capture-sequence-and-what-happens-when-a-step-fails): validate the description → `self._save()` the pre-command state (abort on failure) → `capture_task` → replace the typed line with the mirror using the same `TextArea.replace(..., maintain_selection_offset=False)` call `/ai` uses, so it is one undo step → put the cursor at the end of the inserted line. No screen push, no collection change, no scroll change.
- [ ] T017 [US1] Report every capture failure through the existing `_render_status` in `src/endpaper/tui/edit_screen.py`, leaving the typed line exactly as entered and control in the editor (FR-009) — empty description, rejected token, unwritable `tasks.md`, failed document save.
- [ ] T018 [P] [US1] Extend `tests/unit/test_footer_bindings.py` (or the help-pane test beside it) to assert `/task` appears in the editor's command list, since the help pane reads `EDITOR_COMMANDS` and no help text is written by hand (FR-010).

**Checkpoint**: Capture works end to end. This is the MVP — it already removes the reason followups go
uncaptured, with or without anything below it.

---

## Phase 4: User Story 2 — Promote something already written (Priority: P2)

**Goal**: Prefixing an existing line with `/task.followup ` turns that line's own words into the task and
rewrites the line as the checklist item.

**Independent Test**: Write a plain line of prose, prefix it with the command, submit. The task's
description is the pre-existing text and the line has become the mirror.

**Note**: Promotion rides entirely on US1's mechanism — the same parse, the same capture, the same
replacement. The work here is the guards and the proof, not a second code path. That is the point of the
prefix reading chosen in [spec Assumptions](spec.md#assumptions).

### Tests for User Story 2

- [ ] T019 [P] [US2] Integration test in `tests/integration/test_inline_capture.py`: a line reading `chase the security review with Priya` prefixed with `/task.followup ` produces a task with exactly that description and rewrites the line as a mirror.
- [ ] T020 [P] [US2] Integration test in the same file: a promoted line containing `#tags` has them extracted into the task's tags and removed from its description, identically to a freshly typed description.

### Implementation for User Story 2

- [ ] T021 [US2] Guard the no-description cases in `src/endpaper/tui/edit_screen.py`: a line that is entirely `/task`, and a line that is entirely `/task.followup`, both report `/task needs a description`, leave the line untouched, and write nothing — a `.type` suffix is not a description (FR-007).
- [ ] T022 [P] [US2] Unit test in `tests/unit/test_editor_commands.py` and an integration assertion that `Did you know you can type /task here?` is ordinary document text and creates nothing (FR-003).

**Checkpoint**: Both capture gestures work, and neither can be triggered by prose.

---

## Phase 5: User Story 3 — The task remembers the conversation (Priority: P3)

**Goal**: A captured task names the document it came from, opens it in one keystroke, and appears when that
document's inbound links are asked for.

**Independent Test**: Capture from inside a meeting, then confirm the task names the meeting, the open key
reaches it, and the meeting's inbound links list the task.

**Note**: The link is written by US1. This story is where it is proved to work through 008's existing
consumers — which is the whole argument for using the link primitive instead of a bespoke field.

### Tests for User Story 3

- [ ] T023 [P] [US3] Integration test in `tests/integration/test_capture_provenance.py`: a task captured from a meeting is returned by `links.inbound_links(workspace, <meeting-id>)`, and by `endpaper links <meeting-id> --direction in --json` — parametrized across the CLI and TUI arms, since both surface inbound links.
- [ ] T024 [P] [US3] Integration test in the same file: after the source document is moved to a different month directory, the task's link still resolves by id (FR-017, 008's contract).
- [ ] T025 [P] [US3] Integration test in the same file: after the source document is deleted, reading the task produces a `link_dead` warning naming it, the link is not removed, and nothing raises (FR-018).

### Implementation for User Story 3

- [ ] T026 [US3] Confirm the task preview names the originating document and that the open key reaches it, in `src/endpaper/tui/preview_screen.py` and the task preview added by feature 007. If 008's Links section already renders this, the task here is the assertion, not new rendering — do not add a second surface.

**Checkpoint**: Provenance is live in both directions with no code this feature owns beyond the write.

---

## Phase 6: User Story 4 — Tick it off in the tasks list, the note agrees (Priority: P4)

**Goal**: Completing a task from the tasks list splices the checkbox in every document the task links to,
without stamping those documents' `updated`.

**Independent Test**: Capture a task from a document, complete it from the tasks list, confirm both files
show it complete and the document's `updated` is unchanged.

**Note**: This phase builds the recognition and splice machinery that US5 and US6 both reuse. It is the
largest phase for that reason.

### Tests for User Story 4

- [ ] T027 [P] [US4] Unit tests in `tests/unit/test_mirror_recognition.py` covering the full qualify / does-not-qualify table in [contracts/mirror-format.md](contracts/mirror-format.md#recognition): indented, `*` and `+` bullets, fragment-only destinations, prose around the link, uppercase `X`; and the negatives — a prose link with no checkbox, a checkbox with no link, a link with no fragment, a non-task fragment, a link inside a code span or fence, a numbered list item, and a bullet with no following space.
- [ ] T028 [P] [US4] Unit tests in `tests/unit/test_mirror_splice.py`: applying a state changes exactly one character; link text, indentation, surrounding prose, and line endings are byte-identical afterwards; a mirror already in the target state produces the identical text object; CRLF and LF documents both round-trip.
- [ ] T029 [P] [US4] Integration test in `tests/integration/test_mirror_propagation.py`, parametrized across the CLI (`task done`) and TUI (`space`) arms: completing a task splices the mirror in the linked document, leaves that document's `updated` frontmatter unchanged, and writes `tasks.md` first.
- [ ] T030 [P] [US4] Integration test in the same file: a mirror that has been reworded and reindented since insertion is still found and flipped, proving location is by id and never by line number or text match (FR-015).
- [ ] T031 [P] [US4] Integration test in the same file: a document that is missing or unwritable produces a warning naming it, `tasks.md` is still updated, and the toggle is neither blocked nor reversed (FR-032).
- [ ] T032 [P] [US4] Integration test in the same file: a task with no links does no document work at all — assert no document is read (FR-034).

### Implementation for User Story 4

- [ ] T033 [US4] Implement `find_mirrors(text, *, source)` in `src/endpaper/core/mirrors.py`: the checklist prefix match plus `links.find_links`, returning `Mirror` records carrying the character offset of the single state character. Where a line holds several task-id links, the first is the mirror. Never raises.
- [ ] T034 [US4] Implement the one-character splice helper in `src/endpaper/core/mirrors.py` — `text[:offset] + state_char + text[offset+1:]` — and make it return the input object unchanged when the state already matches, so callers can test identity (FR-030).
- [ ] T035 [US4] Implement `write_document(path, text, file)` in `src/endpaper/core/mirrors.py`: same-directory temp file plus `os.replace`, restoring the read line-ending and trailing-newline policy, and **not** calling `stamp_updated` (FR-029). This is the sync path; `editing.save_buffer` remains the user-save path and is not modified.
- [ ] T036 [US4] Implement `propagate_to_documents(workspace, task, *, skip)` in `src/endpaper/core/mirrors.py` per [contracts/mirror-format.md](contracts/mirror-format.md#propagation--from-the-tasks-list-outward): resolve each of the task's link ids, read, splice, write without stamping; warn and continue on every failure; skip documents the caller names as open with unsaved changes. Never raises.
- [ ] T037 [US4] Call `propagate_to_documents` from `toggle_task_and_track` in `src/endpaper/tui/app.py`, after `set_task_state` succeeds and never before, passing the paths of any document currently open with unsaved changes as `skip` (FR-033). Surface warnings through the existing `last_task_error` channel rather than adding a reporting surface.
- [ ] T038 [US4] Call `propagate_to_documents` from `_cmd_task_done` and `_cmd_task_undone` in `src/endpaper/cli/main.py`, printing warnings to stderr and exiting 0 when `tasks.md` was written ([research R11](research.md#r11-propagation-warnings-never-fail-the-operation)).

**Checkpoint**: The note never goes stale when the task is completed from the list, and the machinery US5
and US6 need now exists.

---

## Phase 7: User Story 5 — Tick it off in the note, the tasks list agrees (Priority: P5)

**Goal**: Ticking a mirror in a document and saving marks the task done, with the conflict cases reported
rather than silently resolved.

**Independent Test**: Tick a mirror in a document, save, confirm the task is complete; untick, save, confirm
it is open again.

### Tests for User Story 5

- [ ] T039 [P] [US5] Unit tests in `tests/unit/test_mirror_reconcile.py` covering every row of the save-time matrix in [contracts/mirror-format.md](contracts/mirror-format.md#on-save--the-users-edit-wins-but-only-where-they-made-one): unchanged, mirror wins, task wins, both changed (writes *and* warns), a mirror absent from the baseline, two disagreeing mirrors, and a dead mirror. This is the highest-risk logic in the feature and gets the densest coverage.
- [ ] T040 [P] [US5] Integration test in `tests/integration/test_mirror_reconcile_save.py`: ticking a mirror and saving marks the task done; unticking and saving reopens it; saving with no mirror changed writes nothing to `tasks.md` (FR-030).
- [ ] T041 [P] [US5] Integration test in the same file: a save that writes `tasks.md` does not trigger a write back into the document that supplied the state — assert one write per file, no cascade (FR-027).

### Implementation for User Story 5

- [ ] T042 [US5] Implement `reconcile_on_save(workspace, text, *, source, baseline)` in `src/endpaper/core/mirrors.py`, returning a `MirrorReport`. Resolve each mirror against the matrix, write `tasks.md` through `tasks.set_task_state` where the mirror wins, and apply corrections that flow the other way to the returned text in the same pass. A task id absent from the baseline counts as the user's edit.
- [ ] T043 [US5] Emit `mirror_conflict` when a mirror and its task both changed since the baseline — the save wins and the divergence is named (FR-024) — and `mirror_ambiguous` when one document holds two disagreeing mirrors for the same task, leaving `tasks.md` untouched for it (FR-025). Both in `src/endpaper/core/mirrors.py`.
- [ ] T044 [US5] Leave a mirror whose id resolves to no task byte-identical, warn `link_dead`, and never block the save (FR-028), in `src/endpaper/core/mirrors.py`.
- [ ] T045 [US5] Hold the baseline on `EditScreen` in `src/endpaper/tui/edit_screen.py` as a `dict[str, bool]`, captured when the document is opened or reconciled and refreshed after every save. It is never persisted anywhere.
- [ ] T046 [US5] Insert reconciliation into `EditScreen._save()` in `src/endpaper/tui/edit_screen.py`, **before** `save_buffer`: reconcile the buffer, update the buffer to the returned text so corrections are visible, then save as today (stamping `updated`, because this is a user edit), then refresh the baseline. Do not add a baseline argument to `save_buffer` ([research R5](research.md#r5-the-two-write-paths-and-why-save_buffer-is-not-overloaded)).
- [ ] T047 [US5] Render reconciliation warnings in the status bar in `src/endpaper/tui/edit_screen.py`. None of them blocks or fails the save.

**Checkpoint**: The checkbox is a control surface in both directions, and a disagreement is reported rather
than quietly resolved.

---

## Phase 8: User Story 6 — Opening a document is enough to make it agree (Priority: P6)

**Goal**: Every mirror converges the next time its document is opened, with no repair command and nothing
watching the filesystem.

**Independent Test**: With the app closed, hand-edit `tasks.md` to complete a task, then open the document
holding its mirror and confirm the checkbox is now ticked.

### Tests for User Story 6

- [ ] T048 [P] [US6] Integration test in `tests/integration/test_mirror_reconcile_open.py`: a task completed outside the app is reflected in the mirror when the document is opened; a mirror copy-pasted into a second document reflects the task's real state when that document is opened (US6 scenarios 1 and 2).
- [ ] T049 [P] [US6] Integration test in the same file: reconciliation that changes nothing writes nothing — assert the document's mtime is unchanged after an open-and-close (FR-030).
- [ ] T050 [P] [US6] Integration test in the same file: reconciliation that does change something writes only that document, does not stamp its `updated`, and modifies no other file in the workspace (FR-029, FR-031).
- [ ] T051 [P] [US6] Performance test in `tests/performance/test_reconcile_open.py` asserting **two** things: reconcile-on-open stays under 50 ms on a synthetic multi-year workspace (SC-008), **and** a document containing no mirrors triggers no read of `tasks.md` at all (SC-007). The second assertion is on behaviour, not duration — a duration check alone would pass on a fast machine even if the read happened.

### Implementation for User Story 6

- [ ] T052 [US6] Implement `reconcile_on_open(workspace, text, *, source)` in `src/endpaper/core/mirrors.py`: the task is authoritative, a dead mirror is left byte-identical and warned about, and the input object is returned unchanged when nothing needed correcting. Return before reading `tasks.md` at all when `find_mirrors` finds none.
- [ ] T053 [US6] Call `reconcile_on_open` in `open_editor` in `src/endpaper/tui/edit_screen.py`, before the buffer is handed to `EditScreen`, so the buffer and the file agree from the first keystroke. Write the corrected text through `write_document` (not `save_buffer`) when it changed.
- [ ] T054 [US6] Call `reconcile_on_open` in `open_task_editor` in `src/endpaper/tui/edit_screen.py` on the same terms.
- [ ] T055 [US6] Call `reconcile_on_open` in `PreviewScreen` on mount and on resume in `src/endpaper/tui/preview_screen.py`, before rendering — the preview is the most common way a document is looked at, and FR-026 requires that what is displayed is never a stale checkbox.
- [ ] T056 [US6] Seed `EditScreen`'s baseline from the reconciled text at open, in `src/endpaper/tui/edit_screen.py`, so a correction applied at open is not mistaken at save time for an edit the user made.

**Checkpoint**: Every convergence case in the spec is handled, with no background process and no repair
command.

---

## Phase 9: User Story 7 — The same capture from the command line (Priority: P7)

**Goal**: `endpaper task add "…" --link <id>` captures with the same relationship the editor writes, and an
unknown id fails cleanly.

**Independent Test**: Add a task with a link from the command line; the resulting line is indistinguishable
from one captured in the editor. An unknown id exits non-zero and creates nothing.

### Tests for User Story 7

- [ ] T057 [P] [US7] Contract test in `tests/contract/test_task_link.py`: `--link` with a resolvable id records it; `--link` supplied twice records both, in the order given; the resulting task line is identical in shape to one captured in the editor.
- [ ] T058 [P] [US7] Contract test in the same file: an unresolvable `--link` id exits **1** with the id named on stderr and creates no task ([research R10](research.md#r10---link-validation-and-its-exit-code)); a genuine usage error still exits 2, so an assistant can tell the two apart.
- [ ] T059 [P] [US7] Contract test in `tests/contract/test_task_done_json.py` for the `--json` schema in [contracts/cli.md](contracts/cli.md#output-1): `id`, `done`, `links`, `documents_updated`, `warnings`; `documents_updated` lists only documents actually written; paths are workspace-relative with forward slashes.
- [ ] T060 [P] [US7] Contract test in the same file for stream separation: with a linked document made read-only, `task undone --json` exits **0**, stdout parses cleanly with the warning inside the JSON, and the human-readable warning is on stderr. Nothing prompts, blocks, or pages.

### Implementation for User Story 7

- [ ] T061 [US7] Add `--link` (`action="append"`, matching the existing `--tag`) to the `task add` parser in `src/endpaper/cli/main.py`.
- [ ] T062 [US7] Resolve every `--link` id with `links.resolve_id` in `_cmd_task_add` in `src/endpaper/cli/main.py` **before** anything is written; an unresolvable id exits 1 naming it, and no task is created (FR-036).
- [ ] T063 [US7] Pass the validated ids to `add_task(links=…)` in `_cmd_task_add` in `src/endpaper/cli/main.py`.
- [ ] T064 [US7] Add `documents_updated` and `warnings` to the `task done`/`undone` `--json` output in `src/endpaper/cli/output.py` and `src/endpaper/cli/main.py`, with warnings written to stderr as well.

**Checkpoint**: Both interfaces are peers for everything that is not the typing gesture itself.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T065 [P] Document in-editor `/task` capture, `task add --link`, and the fact that a checklist item linking to a task is a control surface rather than a copy, in the `AGENTS.md` template at `src/endpaper/` (FR-040). Keep the file under roughly 60 lines — trim rather than append.
- [ ] T066 [P] Record in `CHANGELOG.md` the new `--link` option, the `--json` schema additions, and the reconciliation behaviour, with their version (FR-041, Principle VI).
- [ ] T067 [P] Update `README.md` with the capture gesture and the two-way checkbox, in the section that covers tasks.
- [ ] T068 [P] Update `REQUIREMENTS.md` where it describes the task line and the checkbox scan, so §3.3's hand-edit tolerance covers mirrors.
- [ ] T069 Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src`; fix what they find.
- [ ] T070 Verify the TUI on the target terminals — Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux — focusing on the cursor landing at the end of the inserted mirror line.
- [ ] T071 Verify cross-platform paths: a workspace with spaces and non-ASCII in its path, and a mirror destination that stays well under the Windows 260-character limit.
- [ ] T072 Walk [quickstart.md](quickstart.md) end to end on a throwaway workspace, including the conflict-reporting section and the stream-separation check.
- [ ] T073 Confirm the Constitution Check in [plan.md](plan.md#constitution-check) still holds against the code as built, and that the single Principle IV deviation is still bounded to the sync write path.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)** — gated on `008-document-links` being merged. Nothing starts before T001 passes.
- **Foundational (Phase 2)** — depends on Setup. **Blocks every user story.**
- **US1 (Phase 3)** — depends on Foundational only. This is the MVP.
- **US2 (Phase 4)** — depends on US1. It is the same mechanism plus guards; there is no second code path to build.
- **US3 (Phase 5)** — depends on US1 (the link is written there). Independent of US2 and of everything after it.
- **US4 (Phase 6)** — depends on Foundational only. **Does not depend on US1** — a mirror can be hand-written to test it. It builds the recognition, splice, and sync-write machinery.
- **US5 (Phase 7)** — depends on US4 (T033–T035).
- **US6 (Phase 8)** — depends on US4 (T033–T035). Independent of US5.
- **US7 (Phase 9)** — depends on Foundational (T004) for `--link`, and on US4 (T036) for propagation.
- **Polish (Phase 10)** — depends on every story that is being shipped.

### The one dependency worth stating plainly

US4's T033–T035 — recognition, splice, and the non-stamping writer — are the substrate for US5, US6, and
US7's propagation. Everything from Phase 7 onward is blocked on them. If work is being sequenced for a
single implementer, doing US4 before US2 and US3 gets more of the feature unblocked sooner, at the cost of
delivering a less complete MVP increment.

### Within each story

- Tests are written before the implementation they cover and must fail first.
- Core before adapters, always. Nothing in `cli/` or `tui/` implements behaviour.
- `tasks.md` writes before document writes, in every propagation path.

### Parallel opportunities

- **Phase 2**: T004+T005 (tasks.py) and T006+T007 (editor_commands.py) are different files and can run in parallel; T003 must land first because both depend on the new model fields.
- **Phase 3**: T010 and T011 in parallel; T018 in parallel with the implementation tasks.
- **Phase 6**: all six tests (T027–T032) in parallel; then T033→T034→T035 in sequence (same file, layered), with T037 and T038 in parallel afterwards.
- **Phase 9**: all four contract tests (T057–T060) in parallel.
- **Phase 10**: T065–T068 are four different documents and run in parallel.
- **Across stories**: once Phase 2 is done, US1 and US4 can be worked simultaneously by two people — they share no file until the edit screen, and US4 touches `app.py` and `cli/main.py` while US1 touches `edit_screen.py`.

---

## Parallel Example: User Story 4

```bash
# All six tests first, together:
Task: "Unit tests for mirror recognition in tests/unit/test_mirror_recognition.py"
Task: "Unit tests for the splice in tests/unit/test_mirror_splice.py"
Task: "Integration test for propagation in tests/integration/test_mirror_propagation.py"
Task: "Integration test for a reworded, reindented mirror"
Task: "Integration test for an unwritable document"
Task: "Integration test for a task with no links"

# Then core, in sequence (one file, layered):
#   T033 find_mirrors → T034 splice → T035 write_document → T036 propagate_to_documents

# Then both adapters, together:
Task: "Propagate from toggle_task_and_track in src/endpaper/tui/app.py"
Task: "Propagate from _cmd_task_done/_cmd_task_undone in src/endpaper/cli/main.py"
```

---

## Implementation Strategy

### MVP first (User Story 1 only)

1. Phase 1 — Setup, gated on 008.
2. Phase 2 — Foundational.
3. Phase 3 — US1.
4. **Stop and validate**: capture works, the task is indistinguishable from one typed anywhere else, the
   editor never moves.
5. This is shippable on its own. The note keeps a link that is correct and clickable; nothing yet syncs
   state, and nothing is stale, because nothing has been completed.

### Incremental delivery

1. Setup + Foundational → foundation ready.
2. + US1 → **MVP**: capture without leaving the editor.
3. + US2, US3 → promotion and provenance. Cheap; both mostly ride on US1.
4. + US4 → the note stops going stale. This is where the checkbox becomes a control surface rather than a
   record of the moment it was written.
5. + US5 → the second direction.
6. + US6 → the backstop that makes the whole thing correct without background work.
7. + US7 → CLI parity for capture-with-a-link.

Each step is a coherent thing to hand someone. The one place to resist stopping is between US4 and US6: a
mirror that can be ticked from the document but is never reconciled on open will drift the first time
anyone hand-edits `tasks.md`.

### Parallel team strategy

With two people, after Phase 2: one takes US1 → US2 → US3 (the editor side), the other takes US4 → US6 (the
reconciliation side). They meet at `edit_screen.py` for US5, which is the only story needing both halves.

---

## Notes

- **`[P]` means a different file.** Several phases have long sequential runs inside `core/mirrors.py`
  because that module is built in layers; those are not parallelizable and are not marked so.
- **No task adds a key binding, a screen, a dialog, a setting, or a dependency.** If one appears to,
  re-read the Constitution Check in [plan.md](plan.md#constitution-check) before writing it.
- **The `updated` rule is the easiest thing here to get wrong.** A user save stamps; a sync write does not.
  T035 is where that lives, and T029 is the test that catches a regression.
