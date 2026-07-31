# Implementation Plan: Local AI Assistant Invocation

**Branch**: `006-ai-assistant-invocation` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-ai-assistant-invocation/spec.md`

## Summary

Typing `/ai <prompt>` on its own line in the editor saves the document, hands the prompt to the
assistant the user already has installed, and drops the reply where the command was.

The approach is deliberately small. endpaper does not embed an AI SDK, hold an API key, or open a
network connection: it runs the assistant's own command-line tool as a child process and reads the
reply from its standard output. Both supported assistants take the same shape — `claude -p
"<prompt>"` and `copilot -p "<prompt>"` — so an assistant profile is a binary name plus an argument
builder, and adding a third changes no behaviour (FR-020).

Three pieces land in `core`, none of which need a terminal: an in-editor command table and line
parser, an assistant registry that resolves or detects a profile and runs a cancellable request,
and a config reader/writer for the one new setting. The editor gains an `Enter` hook, a read-only
lock while a request is in flight, and a `ctrl+c` cancel. The command bar gains a `config` verb, and
the command line gains an `endpaper config assistant` peer.

The one design constraint that shapes everything: **Textual thread workers cannot be interrupted
mid-call**. Cancelling therefore has to terminate the child process itself, so `core` returns a
request handle whose `cancel()` kills the process group — which is also what makes SC-002's
one-second cancel achievable.

## Technical Context

**Language/Version**: Python 3.11+ (`tomllib` requires 3.11; the repo already targets 3.11+)

**Primary Dependencies**: None added. `subprocess`, `shutil.which`, `os`, `signal`, and `tomllib`
are all standard library. Textual is already a dependency; this feature uses no new Textual
capability beyond `TextArea(read_only=...)`, overriding `TextArea._on_key`, and `@work(thread=True)`
— all documented public extension points.

**Storage**: The existing `.endpaper/config.toml`. One new `[assistant]` table with one key. No new
file, no index, no cache.

**Testing**: `pytest`. Assistant invocation is tested against a **stub binary** — a small Python
script written to `tmp_path` that echoes, exits non-zero, or sleeps — so every failure path is
exercised without installing Claude Code or Copilot and without a network.

**Target Platform**: Windows, macOS, Linux. Windows is first-class: `shutil.which` resolves
`claude.cmd` / `claude.exe` through `PATHEXT`, and termination uses a platform branch
(`CREATE_NEW_PROCESS_GROUP` + `terminate()` on Windows, `start_new_session=True` + `killpg` on
POSIX).

**Project Type**: Single project — a CLI and a TUI over a shared `core` library.

**Performance Goals**: Cancel returns control in under one second (SC-002). Nothing else here has a
latency budget — the assistant's own response time dominates and is not endpaper's to control.

**Constraints**: endpaper itself requires no network; the assistant makes its own connections. A
machine with no assistant installed keeps 100% of every other feature (FR-031). No admin rights. No
failure path may leave the document corrupted (FR-017).

**Scale/Scope**: One in-editor command, two assistant profiles, one config key, one new CLI
subcommand, one new command-bar verb.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Status |
|---|------|--------|
| I | All logic lands in `endpaper.core`; no I/O formatting, widget code, or argument parsing there. Core is testable without a terminal. | **PASS** — command parsing, profile resolution, detection, request lifecycle, and config read/write all live in `core` and are driven by a stub binary in tests. The request handle is synchronous `subprocess`, not `asyncio`, so no event loop is needed. |
| II | Behaviour is reachable from both CLI and TUI (or is inherently interactive/non-interactive). CLI never opens an editor, never blocks on input, never decorates non-TTY stdout. `--json` schema and exit codes are stable. | **PASS** — `/config assistant` gains the peer `endpaper config assistant [<value>] [--json]`. `/ai` is exempt as inherently interactive: it is defined by a cursor position in an open editor, and a command-line `ai` would be an assistant invoking an assistant. `init` takes `--assistant` and still never prompts. |
| III | No new source of truth (index, database, cache). No new external binary dependency. Every new third-party dependency is justified. No new configuration knob that could be a default. | **FAIL** — two violations, both justified in Complexity Tracking: the assistant binary is an external dependency, and the assistant setting is a new configuration knob. No new source of truth and no new third-party package. |
| IV | Parsers skip malformed input without raising and never lose or truncate a line. Writes preserve `created`, update `updated`, and leave files valid CommonMark. | **PASS** — the command parser returns `None` for anything unrecognised rather than raising (FR-002). The pre-invocation save is the existing `save_buffer`, unchanged. The working indicator lives only in the buffer and is never written to disk. Config writing is a line-targeted edit that preserves comments and unknown keys. |
| V | TUI stays one screen with one-keystroke transitions; every binding is in the footer; confirmations fire only when data would be lost; bindings avoid `ctrl+c`, `ctrl+q`, and rely on no non-`ctrl` modifier. | **FAIL** — `ctrl+c` is bound, in the in-flight state only. Justified in Complexity Tracking. Everything else holds: no new screen, no new confirmation, and the cancel key is stated on screen for the whole wait. |
| VI | Type hints and docstrings on new public `core` functions; test coverage is risk-based (chosen for what could break, not one test per acceptance scenario) and placed in the right layer; public API changes recorded in the changelog. | **PASS** — the coverage plan in [quickstart.md](./quickstart.md) picks a layer per risk: `unit/` for line parsing and config writing, `integration/` for the editor round trip against a stub binary, `contract/` for the new command's exit codes and `--json` shape. The config key, CLI subcommand, and `init` flag go in the changelog. |
| — | Platform constraints hold: no admin rights, no network, Windows path length, spaces and non-ASCII in paths, per-user state outside the workspace. | **PASS** — no install step, no network required by endpaper, no new paths written. Per-user state does not apply: the author confirmed a workspace belongs to one user, and the future shared-workspace design nests each user's workspace below a parent, so the workspace config file already *is* per-user state (see spec Assumptions). |

### Post-design re-check (after Phase 1)

Re-run against the artifacts rather than the intent. No gate changed verdict; two got firmer and one
picked up a constraint worth recording.

| # | Verdict | What the design changed |
|---|---|---|
| I | **PASS**, firmer | The event-loop clause forced a real decision: `AssistantRequest` is synchronous `subprocess`, not `asyncio`, so `core` is callable from a bare pytest run. The cost is that cancellation cannot use task cancellation — it terminates the process group instead (R4). That is the design's load-bearing constraint, and it came from the constitution, not from convenience. |
| II | **PASS** | `endpaper config assistant [<value>] [--json]` is specified with its exit codes and a four-key schema in [contracts/config.md](./contracts/config.md). The `/ai` exemption survives review: it is defined by a cursor position in an open editor. |
| III | **FAIL**, unchanged | Both violations stand as justified. Design work reduced neither but bounded both: the binary is reached through one module nothing else imports (FR-031 becomes structural, not a promise), and the knob stayed one key with three values because detection is the default path. |
| IV | **PASS**, firmer | Three separate non-raising guarantees now written into signatures: `parse_line` returns `None` for anything unrecognised, `get_assistant` returns `None` for a malformed file, and `wait()` returns a failed reply rather than raising. Config writing became a line-targeted edit specifically so hand-written comments and unknown keys survive (R9). |
| V | **FAIL**, unchanged | `ctrl+c` remains the single justified violation. Design added the mitigation the justification promised: the cancel hint is on screen for the entire in-flight state, and the binding exists only in that state. |
| VI | **PASS** | Coverage is assigned per risk in [quickstart.md](./quickstart.md), and the stub binary makes every failure path testable with no assistant installed and no network — which is what makes risk-based coverage achievable here rather than aspirational. |
| — | **PASS** | Windows is handled explicitly rather than assumed: `shutil.which` for `PATHEXT`, and a documented platform branch for process termination. |

**New constraint discovered in design, not present at gate time**: Textual thread workers cannot be
interrupted mid-call. This is why `cancel()` terminates the process rather than setting a flag, and
it is the reason SC-002's one-second budget is reachable at all. Recorded here because it is the
kind of thing a reader of the finished code would otherwise assume was an arbitrary choice.

## Project Structure

### Documentation (this feature)

```text
specs/006-ai-assistant-invocation/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/               # Phase 1 output
│   ├── assistants.md        # Profile shape, invocation, instructions, failure taxonomy
│   ├── core-api.md          # New `endpaper.core` signatures
│   ├── editor-commands.md   # In-editor command grammar and the Enter contract
│   └── config.md            # Config schema + `endpaper config assistant` CLI contract
├── checklists/
│   └── requirements.md      # Spec quality checklist (already written)
└── tasks.md                 # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/endpaper/
├── core/
│   ├── assistants.py        # NEW — profile registry, detection, request lifecycle
│   ├── config.py            # NEW — read/write the assistant setting in config.toml
│   ├── editor_commands.py   # NEW — in-editor command table + line parser
│   ├── models.py            # MODIFIED — AssistantProfile, AssistantReply, EditorCommand
│   ├── errors.py            # MODIFIED — AssistantError
│   └── workspace.py         # MODIFIED — init records the assistant choice
├── cli/
│   └── main.py              # MODIFIED — `config assistant` subcommand, `init --assistant`
└── tui/
    ├── commands.py          # MODIFIED — `config` joins VERB_TABLE
    ├── command_bar.py       # MODIFIED — dispatch the config verb
    ├── edit_screen.py       # MODIFIED — Enter hook, in-flight lock, ctrl+c cancel
    ├── status_bar.py        # MODIFIED — working/cancel text, EDIT_HELP
    └── help_screen.py       # MODIFIED — list in-editor commands

tests/
├── contract/
│   ├── test_exit_codes.py       # MODIFIED — config assistant exit codes
│   ├── test_json_schema.py      # MODIFIED — config assistant --json shape
│   └── test_non_blocking.py     # MODIFIED — new commands terminate with stdin closed
├── integration/
│   ├── test_ai_command_tui.py   # NEW — success, cancel, and failure round trips
│   └── test_config_assistant.py # NEW — CLI/TUI parity for the setting
└── unit/
    ├── test_editor_commands.py   # NEW — line parsing, the `/ai`-as-plain-text cases
    ├── test_assistant_resolve.py # NEW — detection and resolution rules
    ├── test_config_write.py      # NEW — key created, comments and unknown keys preserved
    └── test_command_parsing.py   # MODIFIED — verb table gains `config`
```

**Structure Decision**: Single project, matching the existing `core` / `cli` / `tui` split. The
three new `core` modules are separate files rather than additions to existing ones because none of
them depend on documents, tasks, or meetings — `editor_commands.py` is a pure parser,
`assistants.py` owns process handling, and `config.py` owns the settings file. Keeping them apart is
what lets `assistants.py` be tested with a stub binary and no workspace at all.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **External binary dependency** (Principle III: "No external binary dependencies for core functionality") — `/ai` runs `claude` or `copilot`. | The assistant *is* the feature. Issue #19's premise is that the user already runs one of these tools against the workspace; without it there is nothing to invoke. | Two alternatives, rejected for different reasons ([research.md](./research.md) R1). An **API SDK** is worse against the same principle — a package, an API key endpaper has no business holding, and a network connection the constitution forbids requiring. A **CLI SDK** (`github/copilot-sdk`) is *not* an API client and avoids both of those, but its Python package downloads its own runtime on first use — wrong for a locked-down machine, and it would run its bundled CLI rather than the one the user authenticated — and it exists for Copilot only, so adopting it would fork the two integrations against FR-020. The binary is also **not** core functionality: FR-031 requires every other feature to work fully without it, and `shutil.which` turns a missing binary into a clear message rather than a crash. |
| **New configuration knob** (Principle III: "Configuration beyond workspace paths is out of scope"; "A setting that could be a sensible default MUST be a sensible default") — the `[assistant]` setting. | There is no sensible default when a machine has both assistants installed and nothing to indicate which one the user means, or when the user wants neither. | Auto-detection *is* the default and covers the common case (FR-023): with exactly one assistant present, `/ai` works with nothing configured (SC-007), and the setting exists only to disambiguate. A hard-coded precedence order was rejected because silently calling the assistant the user did not mean is worse than asking once. The knob is one key with three legal values, in a file endpaper already owns. |
| **`ctrl+c` binding** (Principle V: "`ctrl+c` and `ctrl+q` are reserved") — bound while a request is in flight. | Issue #19 specifies `ctrl+c`, and it is the key every terminal user already reaches for to stop something that is running. During the wait it is the only action available, so it collides with nothing. | A different key was rejected because the reservation exists to protect the user's reflex to abort — this is that reflex being served rather than surprised. The binding is scoped to the in-flight state, is stated on screen for the entire wait (satisfying Principle V's footer rule), and reverts to its reserved meaning the moment control returns. If a target terminal turns out to swallow it, the fix is the key, not the requirement that cancelling is always possible. |
