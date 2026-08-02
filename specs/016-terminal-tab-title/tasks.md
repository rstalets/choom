---

description: "Task list for 016-terminal-tab-title"
---

# Tasks: The Terminal Tab Names the Workspace

**Input**: Design documents from `/specs/016-terminal-tab-title/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included, and **not staged into a trailing phase**. The constitution's Development Workflow
gate requires a behaviour change to land with the tests that cover it, so each task below that adds a
rule adds that rule's test in the same task — the truncation task writes the truncation test. Coverage
is risk-based per Principle VI and follows the placement argued at the plan's gate VI: `unit/` for the
composition rules and the emitter's branches, `contract/` for the FR-016 prohibition, one
`integration/` slice for the launcher wiring. **No performance test** — this feature does two writes at
startup and two at exit and nothing in between (FR-009), so there is no budget to protect, and a timing
assertion here would be exactly the wall-clock flake Principle VI forbids and that this milestone
already had to repair once (#84).

**Organization**: Grouped by user story. US1 and US2 share one module by design — a context manager's
enter and exit are one unit — so Phase 3 lands both halves and Phase 4 proves the exit guarantees that
only appear once the launcher is wired.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: US1–US4 — maps to the user stories in spec.md

## Path Conventions

Single project: `src/choom/` and `tests/` at the repository root, per plan.md.

---

## Phase 1: Setup

**Purpose**: Establish a green baseline and confirm nothing existing is being replaced.

- [x] T001 Run `scripts/dev-tests.sh` plus `uv run ruff format --check . && uv run ruff check . && uv run mypy src` from the repository root and confirm all green before touching anything
- [x] T002 Read the three touch points before editing: `_run_tui()` at src/choom/cli/main.py:233 (which already refuses when `sys.stdout.isatty()` is false — that refusal stays exactly as it is), tests/contract/test_no_ansi.py (already asserts `"\x1b" not in` output across part of the subcommand surface; T013 extends it), and tests/integration/test_tui_launch.py. Confirm no existing test asserts any terminal-title behaviour, so this feature replaces nothing and no test needs rewriting

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The core composition function. Everything else writes its output to a terminal, so nothing
can start until it exists.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

Each task adds one rule from the derivation table in [data-model.md](./data-model.md) §2 **and that
rule's tests**, in tests/unit/test_workspace_title.py. Order is derivation order, so the function is
correct-as-far-as-it-goes at every checkpoint and the tree is never broken.

- [x] T003 Implement `workspace_title(workspace: Workspace) -> str` in src/choom/core/workspace.py per contracts/core-api.md C1 — steps 1, 2, 5 and 7 of the derivation: name from `workspace.root.name`, falling back to `str(workspace.root)` when that is empty (a filesystem or drive root), returning `"choom"` alone when nothing usable survives, otherwise `f"choom — {name}"` with an em dash. Full type hints and a docstring stating what it returns and that it never raises. Export it from src/choom/core/__init__.py's imports and `__all__`, following the existing `find_workspace` / `init_workspace` entries. **Add no import to workspace.py** — the implementation needs only builtins, which is what keeps the Principle I gate honest. Same task: unit tests in tests/unit/test_workspace_title.py for the ordinary case (`/Users/rs/work-notes` → `choom — work-notes`), root `/` → `choom — /`, root `C:\` → `choom — C:\`, non-ASCII and spaces passing through verbatim (`Notas de reunión`, FR-006/G6), that the result always begins with `choom` (G3), and that `from choom.core import workspace_title` resolves
- [x] T004 Add derivation steps 3 and 4 to `workspace_title` in src/choom/core/workspace.py: keep each character where `ch.isprintable()` is true or it is a space, drop the rest, then collapse runs of whitespace to a single space and strip the ends (FR-004). Same task: unit tests in tests/unit/test_workspace_title.py that a name containing `\x07` yields a result with no `\x07` in it — the injection case, since an unfiltered `BEL` would close the OSC sequence early and hand the rest to the terminal as commands — plus `\x1b`, `\n`, `\r` and `\t` all absent from the result (G2), and a name made only of control characters yielding exactly `"choom"` (depends on T003)
- [x] T005 Add derivation step 6 to `workspace_title` in src/choom/core/workspace.py: when `len("choom — " + name) > 64`, replace the name with its first 55 characters plus `…` (U+2026), so the title is exactly 64 (FR-005). Count characters, not bytes, so a multi-byte name is never cut mid-character. Same task: unit tests in tests/unit/test_workspace_title.py at the boundary either side — a 56-character name gives a 64-character title untruncated, a 57-character name gives 55 characters plus `…` — a 70-character name, and a long non-ASCII name asserting the result is still exactly 64 characters and contains no replacement character (G1) (depends on T004)

**Checkpoint**: `workspace_title()` is complete, exported, and fully tested with no terminal involved.
`scripts/dev-tests.sh tests/unit/test_workspace_title.py` is green. Stories can begin.

---

## Phase 3: User Story 1 — Find the choom tab without hunting for it (Priority: P1) 🎯 MVP

**Goal**: Launching choom names the terminal tab for the open workspace, and nothing is emitted where it
should not be.

**Independent Test**: Launch choom in a terminal that shows tab titles and confirm the tab reads
`choom — <workspace>` with no configuration changed first; pipe a subcommand and confirm nothing appears.

**Note on scope**: this phase lands the whole emitter, enter *and* exit. A context manager whose
`__exit__` is deferred to a later phase would leave the tree in a state that renames the user's tab and
never gives it back — worse than not shipping. Phase 4 proves the exit guarantees rather than adding
them.

### Implementation for User Story 1

- [x] T006 [US1] Create src/choom/tui/terminal_title.py with `_enable_windows_vt() -> bool` per contracts/terminal.md T3: return `True` immediately when `os.name != "nt"`, having called nothing (FR-023); on Windows use `ctypes.windll.kernel32` — `GetStdHandle(-11)` for `STD_OUTPUT_HANDLE`, `GetConsoleMode`, then `SetConsoleMode` with `ENABLE_VIRTUAL_TERMINAL_PROCESSING` (`0x0004`) ORed into the current mode — returning `False` on any failure or exception. **Standard library only**; `colorama` is rejected in research R3 and must not be added. Same task: unit tests in tests/unit/test_terminal_title.py that it returns `True` on a non-Windows platform without touching `ctypes` (E6), and returns `False` rather than raising when a patched `kernel32` fails at `GetConsoleMode` and again at `SetConsoleMode`
- [x] T007 [US1] Add the four sequence constants and the `terminal_title(title, *, stream=None)` context manager to src/choom/tui/terminal_title.py per contracts/terminal.md T1 and T2. Constants: `PUSH = "\x1b[22;0t"`, `SET = "\x1b]0;{title}\x07"`, `CLEAR = "\x1b]0;\x07"`, `POP = "\x1b[23;0t"`. Enter: if `not stream.isatty()`, or `_enable_windows_vt()` returns `False`, write nothing now **or on exit** and yield; otherwise write `PUSH + SET` in one call and flush. Exit, in a `finally`: write `CLEAR + POP` in one call and flush. **The exit order is `CLEAR` then `POP`, and it is load-bearing — not a detail to tidy.** Clear-then-pop restores exactly on a terminal with a title stack (the pop wins) and clears on one without (the pop is ignored); pop-then-clear would wipe the title it just restored on every stack-capable terminal, silently losing the restore this feature exists to provide. Wrap every write and flush so any `Exception` — `OSError`, `ValueError` on a closed stream, `UnicodeEncodeError` from a console code page that cannot encode the em dash — is swallowed. Same task: unit tests in tests/unit/test_terminal_title.py against a fake stream with a controllable `isatty()`, covering nothing written at all when `isatty()` is `False` (E1, FR-015); the exact enter bytes and the exact exit bytes **asserted as an ordered sequence, so a reversed `POP`/`CLEAR` fails the test** (E2); nothing written between enter and exit (E4); the exit bytes still written when the block raises, with the exception propagating unchanged (E3); a `write` that raises and a `flush` that raises both swallowed with no stderr output and no change to what the block raises (E5); and nothing written on exit when enter wrote nothing because VT was unavailable (FR-022) (depends on T006)
- [x] T008 [US1] Wire the launcher in src/choom/cli/main.py `_run_tui()` per contracts/terminal.md T4: after the existing TTY refusal and `find_workspace` call, wrap the app in `with terminal_title(workspace_title(workspace)): ChoomApp(workspace).run()`. **The wrapping must be around `run()`, outside it — this ordering is required, not stylistic, and must not later be "tidied" into `on_mount`/`on_unmount` or an `atexit` hook.** Two reasons, both verified against the installed textual==8.2.8 (research R3, R4): (a) on Windows, `win32.enable_application_mode()` snapshots the console mode on entry and `stop_application_mode()` writes that snapshot back, so choom's VT bit must be set *before* `run()` to survive into the exit write — enable it after, or rely on Textual, and the restore lands on a console with VT already turned back off; (b) the `finally` of a `with` block is what covers a clean `ctrl+q`, a `ctrl+q` through the discard confirmation, an unhandled exception, and a `KeyboardInterrupt`, with **no key binding** — `ctrl+c` MUST NOT be bound, in any state (Principle V), and does not need to be. Import `terminal_title` from `choom.tui.terminal_title` and `workspace_title` from `choom.core`; keep the import inside `_run_tui()` alongside the existing deferred `ChoomApp` import so no argparse dispatch path pulls in the emitter. Same task: an integration test in tests/integration/test_tui_launch.py that stubs `ChoomApp.run` and passes a fake TTY stdout, asserting the enter bytes are written before `run()` is entered and the exit bytes after it returns (depends on T005, T007)

**Checkpoint**: launching choom names the tab and hands it back. US1 is demonstrable, and US2's happy
path already works.

---

## Phase 4: User Story 2 — Get your terminal back when choom exits (Priority: P2)

**Goal**: Every exit route choom can observe restores the title, and no route that is *not* an exit
restores it early.

**Independent Test**: Leave choom by each route in turn and confirm the tab no longer reads choom's
title; cancel a quit and confirm it still does.

### Implementation for User Story 2

- [x] T009 [US2] Integration tests in tests/integration/test_tui_launch.py for the three exit routes through `_run_tui()`, each with a stubbed `ChoomApp.run` and a fake TTY stdout: a normal return (the `ctrl+q` and confirmed-discard paths both reduce to this, since `App.exit()` ends `run()`); a `KeyboardInterrupt` raised out of `run()`, which must still restore and must re-raise unchanged — Textual's own handler is `except Exception` (textual/app.py:3515) so a `BaseException` propagates, which is precisely why no `ctrl+c` binding is needed; and an arbitrary exception out of `run()`, which must restore and propagate. Assert the exit bytes appear exactly once in each case, never twice (FR-011, FR-014)
- [x] T010 [US2] Integration test in tests/integration/test_tui_launch.py for FR-012 — a quit that is raised and then cancelled must not restore. Assert it from *inside* the stubbed `ChoomApp.run`: at that point the stream must already hold the enter bytes and must **not** hold `CLEAR` or `POP`. This is the non-tautological form of the requirement — it fails an implementation that restores from `on_unmount`, from an eager `atexit`, or from anywhere other than leaving `run()`, which is what a cancelled confirmation never does
- [ ] T011 [US2] Verify by hand the exit routes that only exist in a real app, per quickstart.md step 3: `ctrl+q` with nothing unsaved; `ctrl+q` with a dirty editor then confirming the discard; `ctrl+q` with a dirty editor then cancelling, confirming the tab **still** reads choom's title and the app is still running; and `kill -INT <pid>` from another tab. Confirm none of them adds a pause between the keypress and the shell prompt returning (FR-013). Confirm also that `ctrl+c` inside the running app does not exit — Textual binds it to its own `action_help_quit`, which shows "Press ctrl+q to quit" (research R4) — and that this feature has neither changed nor relied on that
  - **Deferred.** This requires a real terminal and a running interactive session; it cannot be observed headlessly. Left unticked rather than fabricated. Deferred to the pre-release verification gate the constitution's Development Workflow section already requires ("TUI changes MUST be verified before release on the target terminals listed in `docs/REQUIREMENTS.md`") — a release-time activity, not a per-PR one. All exit-route logic this task would exercise by hand is already proven by T009/T010's integration tests, which cover the same routes through `_run_tui()` with a stubbed `ChoomApp.run`.

**Checkpoint**: every observable exit restores; a cancelled quit does not. US1 and US2 are both complete.

---

## Phase 5: User Story 3 — Windows Terminal gets the same signal, older consoles are unharmed (Priority: P3)

**Goal**: The same behaviour on Windows Terminal, and a legacy console that is untouched rather than
littered with escape characters.

**Independent Test**: Run choom in Windows Terminal and confirm the tab renames and restores; run it in
a legacy console host and confirm the session is byte-identical to today's.

**Note on scope**: the Windows code path is the same code path — `_enable_windows_vt()` landed in T006
and the emitter's "write nothing when VT is unavailable" branch in T007, each with its unit tests, because
a behaviour and its test belong in one task. What remains is the verification that only a real Windows
console can give, which the constitution's Development Workflow gate requires before release anyway.

### Implementation for User Story 3

- [ ] T012 [US3] Verify on Windows per quickstart.md step 6: in Windows Terminal, confirm the tab renames on launch and restores on exit; in a legacy console host (`conhost.exe`), confirm launching and quitting choom produces output identical to today's with **no literal `←]0;…` text anywhere** (FR-022), and that the session is otherwise unchanged. Confirm no administrator rights and no network access were involved (FR-021)
  - **Deferred.** This needs a Windows machine, which this implementation session does not have. Left unticked rather than fabricated. Deferred to the pre-release verification gate the constitution's Development Workflow section already requires — a release-time activity, not a per-PR one. `_enable_windows_vt()`'s failure branches (T006) are covered by unit tests against a patched `kernel32`, which is as far as this can be verified without the real console API.

**Checkpoint**: Windows is first-class and legacy consoles are unharmed.

---

## Phase 6: User Story 4 — Nothing leaks into piped or scripted output (Priority: P3)

**Goal**: The FR-016 prohibition becomes a standing check rather than a property of today's import graph.

**Independent Test**: Capture stdout and stderr for every subcommand, piped and on a terminal, and find
no title sequence.

### Implementation for User Story 4

- [x] T013 [P] [US4] Extend tests/contract/test_no_ansi.py to the subcommands it does not yet reach, using its existing `_assert_clean` helper on both streams: `config assistant` (both the get and the set form), `links <id>`, `links check`, `links heal --dry-run`, `task show`, `task undone`, `task delete`, `meeting delete`, and `note delete`. Add one case asserting that `main([])` with a non-TTY stdout writes no escape byte to either stream — it must still emit only the existing refusal and its existing exit code (FR-015, FR-016, US4 scenario 3). This is what turns the structural guarantee — the emitter lives in `choom/tui/` and no argparse dispatch path imports it — into something a future change cannot quietly break

**Checkpoint**: all four stories complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T014 **Leave README.md alone — this is a deliberate skip, not an oversight.** Per CLAUDE.md the README feature list describes the *released* version, and `/release` folds a version's user-visible changes in when it cuts that version; adding or extending a bullet for this unreleased work would promise behaviour a reader installing from PyPI does not get. The feature is recorded in this feature's own `specs/016-terminal-tab-title/` artifacts instead, which is what a "document it" task is actually for at implementation time. Confirm no README.md edit appears in the diff
- [x] T015 [P] Confirm no other documentation needs amending: `docs/REQUIREMENTS.md` is unchanged because this feature adds no exit code, no frontmatter key, no id-scheme change, and no layout change; `AGENTS.md.tmpl` is unchanged because nothing here is AI-facing — the CLI's behaviour is explicitly untouched (FR-016, FR-018)
- [ ] T016 Work through the remaining quickstart.md scenarios by hand: step 1 (the title appears with three or more tabs open), step 2 (it does not churn — navigate collections, months, filter, open, edit, save, and confirm the title never changes, FR-009), step 4 (non-ASCII, over-length, and `BEL`-injecting workspace names), and step 5 (inside tmux with `set-titles on` and `off`, confirming the `off` case is tmux's setting and not a choom bug, FR-020)
  - **Deferred.** This needs a real terminal (and tmux) to observe visually; it cannot be run headlessly. Left unticked rather than fabricated. Deferred to the pre-release verification gate the constitution's Development Workflow section already requires — a release-time activity, not a per-PR one. FR-009 (no churn) is already proven for the emitter's own contract by `tests/unit/test_terminal_title.py::test_nothing_written_between_enter_and_exit`; step 4's title-composition cases are proven by `tests/unit/test_workspace_title.py`.
- [x] T017 Run the full gates from the repository root: `scripts/dev-tests.sh`, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src`. Confirm ruff's TID251 ban still passes for core (the new function adds no import at all) and that tests/unit/test_core_imports.py::test_core_does_not_reference_sys_stdout still passes
- [ ] T018 Verify the TUI on the target terminals in docs/REQUIREMENTS.md §4.3 — Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux — covering launch, no-churn, and restore-on-exit for each (T012 already covers the Windows pair)
  - **Deferred.** This needs each of the five target terminals running interactively; iTerm2, PuTTY, and tmux are visual, terminal-hosted checks this session cannot perform headlessly, and the Windows pair is covered by T012's own deferral. Left unticked rather than fabricated. Deferred to the pre-release verification gate the constitution's Development Workflow section already requires ("TUI changes MUST be verified before release on the target terminals listed in `docs/REQUIREMENTS.md`") — a release-time activity, not a per-PR one.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: after Setup — **blocks every user story**
- **US1 (Phase 3)**: after Phase 2
- **US2 (Phase 4)**: after Phase 3 — its tests exercise the launcher wiring from T008
- **US3 (Phase 5)**: after Phase 3; independent of Phase 4, and needs a Windows machine
- **US4 (Phase 6)**: after Phase 2 only. T013 touches no file any other phase touches and asserts an
  absence, so it can be written and run at any point once the tree builds
- **Polish (Phase 7)**: after all stories

### Within Phase 2

Strictly sequential — T003 → T004 → T005 all edit the same function in the same file, each adding one
derivation step and its tests. The function is correct as far as it goes after each, so the tree is green
at every point.

### Within Phase 3

Strictly sequential — T006 → T007 build one module in dependency order (the enter gate calls
`_enable_windows_vt`), and T008 needs both plus T005.

### Parallel Opportunities

- T013 [P] (US4) is the only implementation task that can run alongside another phase: different file, no
  dependency on incomplete work
- T015 [P] in Polish is independent of the other polish tasks
- Everything else is sequential by file: Phase 2 is one function, Phase 3 is one module plus its caller

### Independently Checkable

Every task states its own verification. T003–T005 and T006–T007 are checked with
`scripts/dev-tests.sh tests/unit/test_workspace_title.py` and
`scripts/dev-tests.sh tests/unit/test_terminal_title.py`; T008–T010 with
`scripts/dev-tests.sh tests/integration/test_tui_launch.py`; T013 with
`scripts/dev-tests.sh tests/contract/test_no_ansi.py`. T011, T012, T016 and T018 are manual and name the
quickstart step they follow.

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Phase 1 → Phase 2 → Phase 3.
2. **Stop and validate**: launch choom in a real terminal, confirm the tab names the workspace and hands
   it back on `ctrl+q`.

At this point the feature is genuinely usable, because Phase 3 deliberately lands the restore alongside
the set — shipping the set alone would leave every user's tab renamed for good.

### Incremental Delivery

1. Phase 2 → core function, tested, exported. Nothing user-visible yet.
2. Phase 3 → US1 works end to end (MVP).
3. Phase 4 → every exit route proven, cancelled quit proven not to restore.
4. Phase 5 → Windows verified.
5. Phase 6 → the CLI prohibition locked down as a standing contract test.
6. Phase 7 → manual passes and gates.

---

## Notes

- **No README task exists, deliberately.** The tasks template would generate one; it is omitted per
  CLAUDE.md, and T014 records the omission and guards against an accidental edit. `/release` owns the
  README.
- **No performance task exists, deliberately.** The plan's gate VI argued the absence: there is no budget
  to protect, and a timing assertion would be the wall-clock flake Principle VI forbids.
- **No task binds, rebinds, or inspects `ctrl+c`.** Restoration is process teardown via `finally` (T008).
  Principle V reserves `ctrl+c` absolutely, and Textual's own pre-existing binding of it is out of scope
  for this feature — noted in research R4, not actioned here.
- **Two orderings are load-bearing and are stated in the task text rather than left to inference**: the
  exit sequence is `CLEAR` then `POP` (T007), and the Windows VT enable happens before `run()` (T008).
  Reversing either fails silently on the terminals that matter most.
- `[P]` means a different file with no dependency on incomplete work.
- Commit after each task or logical group; the tree is green at every checkpoint above.
