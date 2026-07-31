---

description: "Task list for 006-ai-assistant-invocation"
---

# Tasks: Local AI Assistant Invocation

**Input**: Design documents from `/specs/006-ai-assistant-invocation/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. Constitution Principle VI requires risk-based coverage, and
[quickstart.md](./quickstart.md) assigns a layer per risk. Test tasks below follow that assignment —
they are not one contract test plus one integration test per story.

**Organization**: Grouped by user story so each can be implemented, tested, and delivered
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1, US2, US3)
- Exact file paths are in every description

## Path Conventions

Single project: `src/endpaper/` and `tests/` at the repository root, matching the existing
`core` / `cli` / `tui` split.

---

## Phase 1: Setup

**Purpose**: Confirm the baseline before touching anything. The project already exists — there is no
scaffolding to create and no dependency to add (this feature adds none).

- [ ] T001 Confirm the working tree is on `006-ai-assistant-invocation` and `uv run pytest -q` is green (337 passing) before any change

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `core` layer every story sits on — parsing, profiles, resolution, and the process
plumbing — plus the test fixture that makes all of it verifiable without an assistant installed.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Models and errors

- [ ] T002 [P] Add `EditorCommand` and `ParsedCommand` frozen dataclasses to `src/endpaper/core/models.py` per [data-model.md](./data-model.md)
- [ ] T003 [P] Add `AssistantProfile`, `ResolvedAssistant`, and `AssistantReply` frozen dataclasses to `src/endpaper/core/models.py` per [data-model.md](./data-model.md)
- [ ] T004 [P] Add `AssistantError` (exit_code 1) to `src/endpaper/core/errors.py`

### In-editor command parsing

- [ ] T005 Create `src/endpaper/core/editor_commands.py` with `EDITOR_COMMANDS` (the single `ai` entry) and `parse_line()` implementing the grammar in [contracts/editor-commands.md](./contracts/editor-commands.md); it must return `None` rather than raise for any unrecognised line
- [ ] T006 Create `tests/unit/test_editor_commands.py` covering the worked-cases table: mid-line `/ai`, leading whitespace, `/aim`, `//ai`, unregistered `/summarise`, case-insensitive match, argument stripping, and bare `/ai`

### Assistant registry, detection, and resolution

- [ ] T007 Create `src/endpaper/core/assistants.py` with the `PROFILES` registry (claude, copilot) and the default `build_args` returning `["-p", prompt]`, per [contracts/assistants.md](./contracts/assistants.md)
- [ ] T008 Implement `available_assistants()` in `src/endpaper/core/assistants.py` using `shutil.which` so `PATHEXT` resolves `.cmd`/`.exe` on Windows
- [ ] T009 Implement `resolve_assistant(configured)` in `src/endpaper/core/assistants.py` covering all six rows of the decision table in [data-model.md](./data-model.md), including that `none` does not fall back to detection
- [ ] T010 [P] Create `tests/unit/test_assistant_resolve.py` asserting every row of the resolution table, with `available_assistants` patched so the test needs nothing installed

### Process plumbing

- [ ] T011 Implement `compose_prompt(user_prompt, document)` in `src/endpaper/core/assistants.py`, prepending the four FR-010 instructions and naming the saved document path
- [ ] T012 Implement `start_request()` and `AssistantRequest.wait()` in `src/endpaper/core/assistants.py`: no shell, argument list, `cwd` at the workspace root, stdin `DEVNULL`, stdout/stderr captured, new process group per platform. `wait()` returns an `AssistantReply` for every row of the failure taxonomy and never raises. **Cancellation is not implemented here — it belongs to US2 (T028).**

### Test fixture

- [ ] T013 Add the `stub_assistant` fixture to `tests/conftest.py`: writes an executable Python script named as the profile binary into `tmp_path`, prepends its directory to `PATH`, and selects `echo`/`reply`/`empty`/`fail`/`sleep` behaviour by environment variable, per [quickstart.md](./quickstart.md)
- [ ] T014 Add `tests/unit/test_assistant_invoke.py` driving `start_request` against the stub for the success, non-zero-exit, empty-output, and missing-binary rows; assert `wait()` never raises and that the composed prompt reached argv in `echo` mode

**Checkpoint**: `core` can parse an editor line, decide which assistant to call, run it, and report every outcome — all without a terminal, an event loop, or an installed assistant.

---

## Phase 3: User Story 1 — Ask the assistant without leaving the note (Priority: P1) 🎯 MVP

**Goal**: `/ai <prompt>` on its own line saves the document, runs the assistant, and puts the reply where the command was.

**Independent Test**: With exactly one assistant on `PATH` and nothing configured, open a note, type `/ai <prompt>`, press Enter, and confirm the reply lands at that position with every surrounding line untouched.

### Implementation for User Story 1

- [ ] T015 [US1] Create the `EditorTextArea` subclass in `src/endpaper/tui/edit_screen.py` overriding `_on_key` to call `core.editor_commands.parse_line` on Enter, calling `event.prevent_default()` and posting an `EditorCommandSubmitted` message only when the line parses; every other line falls through to Textual's own newline handling
- [ ] T016 [US1] Add the in-flight state to `EditScreen` in `src/endpaper/tui/edit_screen.py`: replace the command line with `⋯`, set `TextArea.read_only = True`, and record the line index and the current request so a stale reply can be identified later
- [ ] T017 [P] [US1] Add the working and cancel text to `src/endpaper/tui/status_bar.py` (`⋯ working — ctrl+c to cancel`) alongside the existing `EDIT_HELP`
- [ ] T018 [US1] Wire the `/ai` handler in `src/endpaper/tui/edit_screen.py`: save via the existing `save_buffer` path first, then `resolve_assistant(None)`, then `compose_prompt`, then `start_request`, running `wait()` on a `@work(thread=True)` worker and returning the reply to the main thread with `call_from_thread`
- [ ] T019 [US1] Implement reply insertion in `src/endpaper/tui/edit_screen.py`: normalise `\r\n` to `\n`, strip the trailing newline, replace the placeholder line with the reply's lines in order, leave the buffer dirty with the cursor after the inserted text
- [ ] T020 [P] [US1] List in-editor commands in `src/endpaper/tui/help_screen.py`, generated from `EDITOR_COMMANDS` so a command cannot exist without appearing in help

### Tests for User Story 1

- [ ] T021 [US1] Create `tests/integration/test_ai_command_tui.py::test_reply_replaces_the_command_line` driving the editor against the stub in `reply` mode: assert the document was saved before invocation, the reply occupies the command's position, surrounding lines are unchanged, and the buffer is dirty
- [ ] T022 [P] [US1] Add a case to `tests/integration/test_ai_command_tui.py` asserting a reply containing a line starting with `/ai` is inserted as literal text and is not executed

**Checkpoint**: US1 is demoable on any machine with one assistant installed and no configuration.

---

## Phase 4: User Story 2 — Stay in control while the assistant works (Priority: P2)

**Goal**: Cancel always works, every failure returns control, and no path ever costs the user a line they wrote.

**Independent Test**: Point `/ai` at an assistant that never returns, press `ctrl+c`, and confirm control returns in under a second with the `/ai <prompt>` line restored exactly as typed and no orphaned child process.

### Implementation for User Story 2

- [ ] T023 [US2] Implement `AssistantRequest.cancel()` in `src/endpaper/core/assistants.py`: terminate the process **group** (`os.killpg` on POSIX, `terminate()` with `CREATE_NEW_PROCESS_GROUP` on Windows), idempotent and safe after the process already exited
- [ ] T024 [US2] Set `cancelled=True` on the reply produced by a cancelled request in `src/endpaper/core/assistants.py` so the editor can suppress the error message
- [ ] T025 [US2] Bind `ctrl+c` in `EditScreen` in `src/endpaper/tui/edit_screen.py`, active only while a request is in flight, calling `request.cancel()`
- [ ] T026 [US2] Implement the restore path in `src/endpaper/tui/edit_screen.py`: on cancel, failure, or empty reply, put back the original `/ai <prompt>` line exactly as typed, clear `read_only`, and return focus
- [ ] T027 [US2] Discard a reply whose request is no longer the current one in `src/endpaper/tui/edit_screen.py`, so a reply arriving after cancel is never inserted
- [ ] T028 [US2] Short-circuit on save failure in `src/endpaper/tui/edit_screen.py`: report the save error and return control **without invoking any assistant**
- [ ] T029 [US2] Surface failure messages in the existing status bar via `src/endpaper/tui/edit_screen.py`, naming the assistant by `display_name` so a configured-but-missing assistant is distinguishable from a generic failure

### Tests for User Story 2

- [ ] T030 [US2] Add `test_cancel_restores_the_line_and_kills_the_process` to `tests/integration/test_ai_command_tui.py` using the stub in `sleep` mode: assert control returns, the command line is restored verbatim, and the child is gone
- [ ] T031 [P] [US2] Add failure cases to `tests/integration/test_ai_command_tui.py` for non-zero exit, empty reply, and missing binary: each shows a message, restores the line, and leaves the document byte-identical to its saved state
- [ ] T032 [P] [US2] Add `test_save_failure_never_invokes_the_assistant` to `tests/integration/test_ai_command_tui.py` using a read-only directory, asserting the buffer is intact and no process was spawned

**Checkpoint**: Every terminal branch of the state machine returns control with the user's words intact.

---

## Phase 5: User Story 3 — Choose which assistant endpaper calls (Priority: P3)

**Goal**: The assistant choice is settable from both interfaces, persists, and is reportable.

**Independent Test**: Set the assistant, restart endpaper, and confirm the value is still in effect and reported back — verifiable without invoking any assistant.

### Implementation for User Story 3

- [ ] T033 [P] [US3] Create `src/endpaper/core/config.py` with `get_assistant()` returning `None` for a missing file, missing table, malformed file, or illegal value — never raising
- [ ] T034 [US3] Implement `set_assistant()` in `src/endpaper/core/config.py` as a line-targeted edit covering all three file shapes in [contracts/config.md](./contracts/config.md), validating before writing and writing atomically via a same-directory temp file and `os.replace`
- [ ] T035 [P] [US3] Create `tests/unit/test_config_write.py`: key created in each file shape, comments and unknown keys survive, an invalid value writes nothing, `workspace.schema` is untouched
- [ ] T036 [US3] Add the keyword-only `assistant` parameter to `init_workspace()` in `src/endpaper/core/workspace.py`, recording the choice when given and leaving existing callers unaffected
- [ ] T037 [US3] Pass the stored setting into `resolve_assistant()` from `src/endpaper/tui/edit_screen.py`, replacing the `None` placeholder from T018 so a configured assistant wins over detection
- [ ] T038 [US3] Add the `config assistant [<value>] [--json]` subcommand to `src/endpaper/cli/main.py` with exit codes 0 / 2 / 3 and the four-key JSON schema from [contracts/config.md](./contracts/config.md)
- [ ] T039 [US3] Add `--assistant` to `endpaper init` in `src/endpaper/cli/main.py`, still non-blocking and still never prompting
- [ ] T040 [P] [US3] Add the `config` verb to `VERB_TABLE` in `src/endpaper/tui/commands.py` with its argument shape and help description
- [ ] T041 [US3] Dispatch the `config` verb in `src/endpaper/tui/command_bar.py`, reporting the current value with no argument and naming the accepted values on a bad one

### Tests for User Story 3

- [ ] T042 [US3] Update `tests/unit/test_command_parsing.py::test_existing_verbs_unchanged` to include `config` — a deliberate edit to a guarded list, flagged in the spec's Dependencies
- [ ] T043 [P] [US3] Create `tests/integration/test_config_assistant.py` asserting the CLI and TUI produce an identical config file, parametrized across the two adapters rather than duplicated into separate files
- [ ] T044 [P] [US3] Extend `tests/contract/test_exit_codes.py` for `config assistant`: 0 on success, 2 on a bad value, 3 outside a workspace
- [ ] T045 [P] [US3] Extend `tests/contract/test_json_schema.py` for the exact four-key `config assistant --json` shape, asserting `available` is `[]` and never `null`
- [ ] T046 [P] [US3] Extend `tests/contract/test_non_blocking.py` with `config assistant` and `init --assistant`, confirming both terminate promptly with stdin closed
- [ ] T047 [P] [US3] Add a case to `tests/integration/test_config_assistant.py` for a config predating this feature (no `[assistant]` table): everything works and reading the setting is not an error

**Checkpoint**: All three stories work independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T048 [P] Record the `[assistant]` config key, the `endpaper config assistant` command, and `init --assistant` in `CHANGELOG.md` with their version (FR-032, Principle VI)
- [ ] T049 [P] Update `README.md` with `/ai` and the configuration commands
- [ ] T050 [P] Update the `AGENTS.md` template in `src/endpaper/core/templates/AGENTS.md.tmpl` if the new command belongs there, keeping the file under roughly 60 lines
- [ ] T051 Amend `REQUIREMENTS.md` §5 to move "AI invocation from inside endpaper" and "Any configuration beyond workspace paths" out of the v0.0.1 out-of-scope list into v0.0.2
- [ ] T052 Run formatting, linting, and type checking; confirm the full suite is green including the three modified pinned tests
- [ ] T053 Work through all 7 scenarios in [quickstart.md](./quickstart.md) by hand
- [ ] T054 Verify `ctrl+c` on Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux — the binding is the one justified deviation from Principle V, so this is the gate that confirms the justification holds
- [ ] T055 Verify a workspace path containing spaces and non-ASCII characters works end to end, and that generated paths stay well under the Windows 260-character limit

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (T001)**: no dependencies
- **Foundational (T002–T014)**: depends on Setup — **blocks every user story**
- **US1 (T015–T022)**: depends on Foundational only
- **US2 (T023–T032)**: depends on Foundational; touches `edit_screen.py` alongside US1, so in practice runs after US1 rather than beside it
- **US3 (T033–T047)**: depends on Foundational. T037 is its only touchpoint with US1's code
- **Polish (T048–T055)**: depends on every story being complete

### Within Foundational

- T002–T004 (models, errors) are parallel and come first
- T005 → T006 (parser then its test)
- T007 → T008 → T009 → T010 (registry, detection, resolution, test)
- T011, T012 depend on T007 and the models
- T013 → T014 (fixture then the tests that use it)

### Within each story

- Implementation before its tests here, deliberately: the parser and resolution logic that *could*
  be written test-first already were, in Foundational. The story-level tests are editor round trips
  against a live widget, which are written against working behaviour rather than as red-first specs.
- Within US1: T015 → T016 → T018 → T019; T017 and T020 are independent
- Within US2: T023 → T024 → T025 → T026 → T027; T028 and T029 are independent of the cancel chain
- Within US3: T033 → T034 → T035; T038 and T041 both depend on T034

### Parallel opportunities

| Group | Tasks |
|---|---|
| Foundational models and errors | T002, T003, T004 |
| Foundational resolution test | T010 alongside T011 |
| US1 presentation | T017, T020 alongside the T015→T019 chain |
| US1 tests | T022 alongside T021 |
| US2 tests | T031, T032 alongside T030 |
| US3 core and CLI | T033, T035, T040 |
| US3 contract tests | T044, T045, T046, T047 — four different files |
| Polish docs | T048, T049, T050 |

**Cross-story parallelism**: US3 is genuinely independent of US1 and US2 — it touches
`core/config.py`, `cli/main.py`, `tui/commands.py`, and `tui/command_bar.py`, none of which US1 or
US2 modify, apart from the single line in T037. It can be built by a second person as soon as
Foundational lands. US1 and US2 both rewrite `edit_screen.py` heavily and should not be worked in
parallel by different people.

---

## Parallel Example: Foundational

```bash
# The three model/error tasks touch two files and have no interdependencies:
Task: "Add EditorCommand and ParsedCommand to src/endpaper/core/models.py"
Task: "Add AssistantProfile, ResolvedAssistant, AssistantReply to src/endpaper/core/models.py"
Task: "Add AssistantError to src/endpaper/core/errors.py"
```

## Parallel Example: User Story 3 contract tests

```bash
# Four separate files, no shared state:
Task: "Extend tests/contract/test_exit_codes.py for config assistant"
Task: "Extend tests/contract/test_json_schema.py for the four-key shape"
Task: "Extend tests/contract/test_non_blocking.py for the new commands"
Task: "Add the pre-existing-config case to tests/integration/test_config_assistant.py"
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. T001 — confirm baseline
2. T002–T014 — Foundational
3. T015–T022 — US1
4. **Stop and validate**: quickstart Scenarios 1, 2, and 7

That is a working `/ai` for anyone with exactly one assistant installed — the headline capability,
with no configuration surface at all.

**Do not ship the MVP on its own.** US2 is what makes `/ai` safe: without it there is no way out of
a hung request and no defined behaviour when the assistant fails. Treat US1 + US2 as the smallest
releasable unit; US1 alone is the smallest *demoable* one.

### Incremental delivery

1. Foundational → `core` is complete and unit-tested with no UI
2. + US1 → demoable
3. + US2 → releasable
4. + US3 → complete against the spec
5. + Polish → shippable

### Suggested commit boundaries

One commit per checkpoint, plus one per polish task. The Foundational phase is a natural single
commit: it adds three `core` modules and their unit tests and changes no user-visible behaviour.

---

## Notes

- `[P]` means different files and no dependency on an incomplete task
- Every task names its file; none should require reading another task to interpret
- The one deliberate ordering departure from the template is noted above: tests follow
  implementation inside the story phases, because those tests drive a live widget
- Three existing tests are modified rather than added to — T042, T044/T045/T046 — and are called out
  in the spec's Dependencies so they read as planned work rather than breakage
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
