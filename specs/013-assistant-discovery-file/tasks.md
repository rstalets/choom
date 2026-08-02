---

description: "Task list for 013-assistant-discovery-file"
---

# Tasks: Assistant Discovery File

**Input**: Design documents from `/specs/013-assistant-discovery-file/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. The constitution (Principle VI) requires every user-facing behaviour to be
covered, at a layer chosen by risk rather than one test per acceptance scenario. Placement follows
research R12; the risks being covered are: computing the wrong path, writing content that breaks its
own content rule, corrupting a hand-edited config, deleting a file choom did not write, and asking
the launch question twice.

**Organization**: grouped by user story so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable — different files, no dependency on an incomplete task
- **[Story]**: US1–US5, on user-story tasks only

## Path Conventions

Single project: `src/choom/` and `tests/` at the repository root, per plan.md.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: create the module and, before anything writes to a profile directory, the seam that
keeps tests out of the developer's real `~/.claude`.

- [X] T001 Create `src/choom/core/discovery.py` with `profile_root() -> Path` returning `Path.home()`, plus the module docstring stating this is the only place the user's profile directory is resolved (research R3, R13)
- [X] T002 Add an autouse fixture to `tests/conftest.py` that monkeypatches `choom.core.discovery.profile_root` to a per-test `tmp_path`, so no test can write to the real profile directory
- [X] T003 [P] Add a guard test in `tests/unit/test_discovery_paths.py` asserting `profile_root()` under the fixture is inside `tmp_path` and is not `Path.home()`

**Checkpoint**: the seam exists and is proven closed before any install code is written.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: per-assistant locations, the rendered content, and the config writer. Every user story
depends on these; no story is deliverable until they are done.

- [X] T004 Add the `discovery_relpath: PurePosixPath | None` field to `AssistantProfile` in `src/choom/core/models.py`, with a comment recording that `None` is the FR-017 case
- [X] T005 Populate `discovery_relpath` for both entries in `PROFILES` in `src/choom/core/assistants.py`: `.claude/skills/choom/SKILL.md` and `.copilot/instructions/choom.instructions.md` (research R1, R2)
- [X] T006 Implement `discovery_path(profile: AssistantProfile) -> Path | None` in `src/choom/core/discovery.py`, joining `profile_root()` with the profile's relative path and returning `None` when the profile has none
- [X] T007 [P] Add unit tests in `tests/unit/test_discovery_paths.py` covering both assistants' resolved paths and the `None` profile
- [X] T008 Implement the marker constant and `render_discovery_file(workspace: Workspace, profile: AssistantProfile) -> str` in `src/choom/core/discovery.py`, per `contracts/discovery-file.md` — frontmatter for `claude`, plain heading for `copilot`, workspace path alone on its own line, marker comment last
- [X] T009 [P] Add unit tests in `tests/unit/test_discovery_content.py`: the marker is present for both assistants; the workspace path appears verbatim including for a path with spaces and non-ASCII characters; the output is at most 20 lines; rendering the same workspace twice is byte-identical; and none of `AGENTS.md.tmpl`'s distinctive strings (`meetings/YYYY/MM/`, `id: meeting_`, `choom task add`, `Exit codes:`) appear
- [X] T010 Generalise `_apply_assistant_value` in `src/choom/core/config.py` into a key-taking helper that performs the same three-case line-targeted edit (replace the key line, insert into an existing `[assistant]` table, append the table), leaving `set_assistant`'s observable behaviour byte-identical (research R5)
- [X] T011 [P] Extend `tests/unit/test_config_write.py` to prove the generalised writer still preserves comments, key order, and unknown keys, and still handles CRLF files

**Checkpoint**: paths resolve, content renders within its rules, and the config can carry a second key without disturbing a hand-edited file.

---

## Phase 3: User Story 1 — The assistant finds choom from anywhere (P1) 🎯 MVP

**Goal**: naming an assistant installs the pointer in that assistant's user-scope location.

**Independent test**: configure an assistant from inside a workspace, start that assistant with an
unrelated working directory, and confirm it can name the workspace and its `AGENTS.md` unaided.

- [X] T012 [US1] Implement `install_discovery_file(workspace: Workspace, profile: AssistantProfile) -> Path | None` in `src/choom/core/discovery.py`, writing through `write_text_atomic` (which already creates parent directories, satisfying FR-011) and returning `None` for a profile with no location
- [X] T013 [US1] Implement `installed_discovery_path() -> Path | None` in `src/choom/core/discovery.py`, returning the path of the one choom-owned file currently on disk, or `None`
- [X] T014 [US1] Call `install_discovery_file` from the set branch of `_cmd_config_assistant` in `src/choom/cli/main.py`, after the setting write succeeds, catching `WorkspaceError` so the command cannot fail on it (FR-013)
- [X] T015 [US1] Call the same core function from `handle_config_command` in `src/choom/tui/app.py`, so the two interfaces install through one path and neither assembles content of its own
- [X] T016 [P] [US1] Add unit tests in `tests/unit/test_discovery_install.py`: a file appears at the expected path with the expected content; missing parent directories are created; an existing file at that path is overwritten in full rather than merged; a profile with no location writes nothing and does not raise
- [X] T017 [US1] Add an integration test in `tests/integration/test_discovery_install.py` parametrized across the CLI and TUI adapters, asserting that setting the assistant through either one leaves the same file on disk

**Checkpoint**: US1 is complete and shippable on its own. Everything below is reachable through a different door or is a refinement.

---

## Phase 4: User Story 2 — Offered at launch, asked once (P2)

**Goal**: users who never run the command are offered the pointer once, through the shared
confirmation, and never asked again.

**Independent test**: in a workspace with no assistant configured and exactly one installed, start
choom and confirm the offer appears; press `Esc`, restart, confirm silence; elsewhere press `Enter`
and confirm the pointer is installed.

**⚠️ Constitution note**: this phase implements the Gate V violation recorded in plan.md's Complexity
Tracking. If that trade is rejected, this whole phase is the unit to cut; nothing in Phases 3, 5, 6,
or 7 depends on it.

- [X] T018 [US2] Implement `get_launch_offer_made(workspace) -> bool` and `set_launch_offer_made(workspace, value)` in `src/choom/core/config.py` on top of the T010 helper; the reader must never raise on a missing file, missing table, malformed TOML, or non-boolean value (Principle IV)
- [X] T019 [P] [US2] Add unit tests in `tests/unit/test_config_write.py` for the new key: round-trip, absent-key default, malformed TOML, non-boolean value, and that writing it leaves `name` and any unknown keys untouched
- [X] T020 [US2] Implement `should_offer_discovery(workspace, resolved: ResolvedAssistant) -> AssistantProfile | None` in `src/choom/core/discovery.py` — the whole suppression matrix in one pure function: no offer when a file is installed, when the setting is `none`, when resolution is ambiguous or unset, or when the offer has already been made; otherwise the profile to offer (FR-022, FR-029)
- [X] T021 [P] [US2] Add unit tests in `tests/unit/test_discovery_offer.py` covering every row of that matrix, including the configured-assistant-with-missing-file case the spec deliberately includes
- [X] T022 [US2] Raise the offer in `ChoomApp.on_mount` in `src/choom/tui/app.py`: push `ListScreen`, then `call_after_refresh` a `ConfirmDialog` built from the profile and workspace, with a dismiss callback that installs on `Enter`, installs nothing on `Esc`, and records `launch_offer_made` on either key (research R6, R7)
- [X] T023 [US2] Hand the outcome to `ListScreen` through the existing pending-status mechanism in `src/choom/tui/list_screen.py` rather than rendering directly, so the dialog's pop-triggered refresh cannot race and overwrite the message
- [X] T024 [US2] Add an integration test in `tests/integration/test_launch_offer.py` driving the TUI: the question appears once; `Enter` installs and records; `Esc` installs nothing and still records; a second launch asks nothing; and each suppression case shows no dialog

**Checkpoint**: the feature now reaches users who never type a command.

---

## Phase 5: User Story 3 — Repointing and removal (P3)

**Goal**: one pointer at a time, following the workspace, removable on request — and choom never
deletes a file it did not write.

**Independent test**: configure from workspace A then B and confirm the file names only B; switch
assistants and confirm exactly one file remains; set `none` and confirm none remain.

- [X] T025 [US3] Implement `remove_discovery_files(*, keep: AssistantProfile | None = None) -> tuple[list[Path], list[str]]` in `src/choom/core/discovery.py`, deleting a file at a choom-owned path **only** when it contains the marker, and returning the paths removed plus a warning for each path left alone (FR-010, research R11)
- [X] T026 [US3] Call it from `install_discovery_file` so a successful install leaves exactly one file across all assistants' locations (FR-008)
- [X] T027 [US3] Handle `none` in the set branch of both adapters — `src/choom/cli/main.py` and `src/choom/tui/app.py` — removing every choom-owned file and succeeding when there is nothing to remove (FR-009)
- [X] T028 [US3] Clear `launch_offer_made` on every explicit set of the assistant, in the same core call so neither adapter has to remember (FR-028)
- [X] T029 [P] [US3] Add unit tests in `tests/unit/test_discovery_install.py`: repointing rewrites the path and leaves no trace of the previous workspace; switching assistants leaves exactly one file; `none` removes all; removal is idempotent; and a file at a choom-owned path **without** the marker is left on disk and reported as a warning
- [X] T030 [P] [US3] Add a contract test in `tests/contract/test_config_assistant_cli.py` asserting the one-file invariant after any successful set

**Checkpoint**: the pointer is correct over time, not just at first install.

---

## Phase 6: User Story 4 — The command says what it did (P4)

**Goal**: the user can see what was written and can tell a silent failure from a silent success.

**Independent test**: run the set command and read its output; make the profile directory unwritable
and confirm the setting is still recorded and the problem named.

- [X] T031 [US4] Report the discovery-file outcome on **stderr** from `_cmd_config_assistant` in `src/choom/cli/main.py` — path written, path removed, "no discovery file for `<name>`", or the failure and its reason — leaving stdout empty on a set (research R8, FR-014, FR-015)
- [X] T032 [US4] Add `discovery_file` and `launch_offer_made` to the `--json` object and the two matching rows to the human-readable read output in `src/choom/cli/main.py`, renaming and removing nothing (FR-016, FR-033, `contracts/cli-config-assistant.md`)
- [X] T033 [US4] Report the same outcomes in the TUI status bar from `handle_config_command` in `src/choom/tui/app.py`, in that interface's idiom (FR-015)
- [X] T034 [US4] Confirm the exit code reports only the setting write: a discovery-file failure leaves it `0`, a rejected value `2`, a config that cannot be read or written `3` (FR-013)
- [X] T035 [P] [US4] Add contract tests in `tests/contract/test_config_assistant_cli.py`: stdout empty on set; a read writes nothing anywhere; the four pre-existing `--json` keys keep their names and types; the unwritable-profile case records the setting, names the path on stderr, and exits `0`

**Checkpoint**: the feature is legible and safe on a locked-down machine.

---

## Phase 7: User Story 5 — Naming the assistant at init (P5)

**Goal**: `choom init --assistant <name>` installs the pointer for the workspace it just created.

**Independent test**: run `init` with an assistant named in a fresh directory and confirm the file
exists and points at the new workspace.

- [ ] T036 [US5] Install the discovery file at the end of `init_workspace` in `src/choom/core/workspace.py` when `assistant` names a supported assistant, and remove any choom-owned file when it is `none`; a failure here must not fail `init` (FR-020)
- [ ] T037 [P] [US5] Add unit tests in `tests/unit/test_discovery_install.py`: `init --assistant claude` installs pointing at the new workspace; `init` with no assistant installs nothing; `init --assistant none` installs nothing; a discovery-file failure still leaves a valid workspace

**Checkpoint**: all five stories delivered.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T038 [P] Document the discovery file in `README.md` where `config assistant` is described: what it installs, where, that it is rewritten on every run, and that `none` removes it
- [ ] T039 Run `uv run ruff format`, `uv run ruff check`, and the type checker over the changed files, fixing what they report
- [ ] T040 Run the full suite with `uv run pytest` and confirm the pre-existing `AGENTS.md` line-budget contract test still passes untouched
- [ ] T041 Walk `specs/013-assistant-discovery-file/quickstart.md` end to end against a scratch workspace, and correct the quickstart if reality differs

---

## Dependencies

```
Phase 1 (Setup) ──► Phase 2 (Foundational) ──┬──► Phase 3 (US1, P1) ──┬──► Phase 5 (US3, P3)
                                             │                        ├──► Phase 6 (US4, P4)
                                             │                        └──► Phase 7 (US5, P5)
                                             └──► Phase 4 (US2, P2) ───────► (independent of 5/6/7)
```

- **Phase 1 before everything.** T002's fixture must exist before any code can write to a profile
  path, or the first test run touches the developer's real `~/.claude`.
- **Phase 2 before every story.** All five stories call `discovery_path` and `render_discovery_file`.
- **US2 depends on US1** for `install_discovery_file`, and on T018 for the record. It does not depend
  on US3, US4, or US5, and can be cut whole (see the Constitution note in Phase 4).
- **US3, US4, US5 each depend only on US1** and are mutually independent — they may be done in any
  order, or in parallel by separate hands.
- Within a phase, `[P]` tasks touch different files and may run together. Non-`[P]` tasks in the same
  phase touch a shared file and must be sequential.

## Parallel Execution Examples

- **Phase 2**: T007, T009, and T011 are three different test files and may be written together once
  their subjects (T006, T008, T010) exist.
- **Phase 3**: T016 and T017 may be written in parallel once T012–T015 land.
- **Phases 5–7**: with US1 complete, one person can take Phase 5, another Phase 6, and a third
  Phase 7 — they share no source file except `cli/main.py` between T031/T032 (same phase, sequential)
  and `core/discovery.py` between T025/T026 (same phase, sequential).

## Implementation Strategy

**MVP**: Phases 1–3. That delivers the pointer, installed from either interface, which is the whole
of issue #37's ask. Stop there and the feature is real.

**Then, in value order**: Phase 4 (US2) reaches the users who never run the command and is the
largest remaining increment; Phase 5 (US3) makes the pointer stay correct over time; Phase 6 (US4)
makes it legible and safe on a locked-down machine; Phase 7 (US5) is a convenience on a path that
already works.

**If the Gate V trade is rejected at review**: drop Phase 4 entirely. Nothing else references
`should_offer_discovery` or `launch_offer_made` except T028, which then becomes a no-op to delete.
