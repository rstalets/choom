# Phase 0 Research: Local AI Assistant Invocation

**Feature**: `006-ai-assistant-invocation` | **Date**: 2026-07-30

Every open question from the Technical Context, resolved. Sources are the current Claude Code and
GitHub Copilot CLI documentation and the current Textual documentation, fetched during planning
rather than recalled.

---

## R1 — Subprocess or SDK?

**Decision**: Run the assistant's own command-line tool as a child process. No SDK, no API key, no
HTTP client.

**Rationale**: The spec's premise (and Issue #19's) is that the user *already has* Claude Code CLI
or GitHub Copilot CLI installed and authenticated against this workspace. Shelling out to it
inherits that authentication, that configuration, and that tool's own permissions model for free.

Principle III says to prefer the standard library and to justify every third-party dependency "by
what it would cost to do without". Here the cost of doing without is one `subprocess.Popen` call
with `["-p", prompt]`, so the bar is not met by any of the alternatives below.

**"SDK" covers two different things, and they fail for different reasons.** An *API* SDK talks to a
hosted service; a *CLI* SDK wraps the local binary. Both were considered.

**Alternatives considered**:

- **Anthropic API SDK.** Rejected: adds a package, requires endpaper to hold and store an API key it
  has no business holding, and opens its own network connection — against the Platform constraint
  that no operation may require network access. It also ignores the premise: the user has already
  installed and authenticated a tool, and this would bypass it and bill them twice over.
- **GitHub Copilot CLI SDK** (`github/copilot-sdk`). **This one is not an API client** — it spawns
  the Copilot CLI and talks JSON-RPC to it, managing the process lifecycle. So it needs no API key,
  opens no separate network path, and would give better structured responses and error handling than
  parsing stdout. It is rejected on three grounds instead:
  1. **The Python SDK ships its own runtime.** Installation includes `python -m copilot
     download-runtime`, and if that step is skipped "the SDK will attempt to download it
     automatically on first use". A tool that downloads a runtime on first use is the wrong shape
     for a locked-down corporate machine, and it would run *its* bundled CLI rather than the one the
     user installed and authenticated — losing the exact property that makes shelling out
     attractive.
  2. **It is per-assistant.** Claude Code has no equivalent wrap-the-CLI package in the same shape
     (the Claude Agent SDK is a different product with a different model), so adopting it would mean
     one integration path for Copilot and another for Claude — the asymmetry FR-020 exists to
     prevent. Adding a third assistant would mean adding a third dependency, where the chosen design
     makes it a row in a table.
  3. **The payoff is small here.** endpaper needs one string back from one prompt. Session
     management, streaming, and structured tool events are real advantages for an application built
     around an agent loop; this feature is a single request whose reply goes straight into a
     document.
- **Claude Agent SDK.** Rejected for the mirror-image reason: it is Claude-only, so pairing it with
  a Copilot integration of any kind reintroduces the same asymmetry.

**What this decision does not claim.** Shelling out is not richer than the CLI SDKs — it is
narrower on purpose. If a future feature needs multi-turn sessions or streaming partial output into
the editor, the CLI SDK route deserves a fresh look, and the profile registry's `build_args` seam is
where that change would land.

---

## R2 — How is each assistant invoked non-interactively?

**Decision**: `<binary> -p <prompt>`, reply read from standard output. Identical shape for both.

| Assistant | Binary | Non-interactive form | Reply | Failure |
|---|---|---|---|---|
| Claude Code CLI | `claude` | `claude -p "<prompt>"` | stdout | non-zero exit |
| GitHub Copilot CLI | `copilot` | `copilot -p "<prompt>"` | stdout | non-zero exit |

**Rationale**: Claude Code documents `-p` / `--print` as its headless mode — "To run Claude Code
non-interactively, use the `-p` or `--print` flag" — printing the response to the console.
Copilot documents `-p, --prompt [TEXT]` as "Run in non-interactive prompt mode", a single-request
session for scripting that streams to stdout and returns a non-zero exit code on failure.

That the two converge on the same flag letter and the same stdout contract is what makes FR-020
cheap: a profile is a binary name plus an argument builder, and the default builder
(`["-p", prompt]`) already serves both. A future assistant that needs a different shape overrides
the builder and nothing else moves.

**Alternatives considered**:

- **`--output-format json` (Claude) for structured replies.** Rejected: Copilot has no equivalent,
  so using it would fork the two profiles' response handling and re-introduce the asymmetry FR-020
  exists to prevent. Plain stdout text is exactly what FR-014 needs to insert.
- **Piping the prompt on stdin.** Both tools support it, but passing the prompt as an argument
  avoids a second failure mode (a half-written pipe on cancel) and keeps the invocation inspectable
  in one line for error messages.

---

## R3 — How do the instructions (FR-010) reach the assistant?

**Decision**: Prepend them to the prompt text. One argv shape for every assistant.

**Rationale**: Claude Code has `--append-system-prompt`; Copilot does not expose an equivalent
non-interactive flag. Using a per-assistant flag would mean a capability matrix inside the profile
registry — precisely the kind of divergence FR-020 rules out. Folding the instructions into the
prompt string keeps every profile to `["-p", text]` and makes the composed prompt trivially
testable: a stub binary can echo its argv back and assert the instructions are present.

**Alternatives considered**: A per-profile `system_prompt_flag` with a fallback to prepending.
Rejected as machinery serving a difference the user can never observe — the reply is the same
either way, and the fallback path would be the only one ever exercised in tests.

---

## R4 — Cancelling an in-flight request

**Decision**: `core` returns a request handle. `cancel()` terminates the child **process group**;
the worker thread unblocks as a consequence.

**Rationale**: This is the constraint that shaped the design. Textual's own documentation is
explicit: "you can't cancel threads in the same way as coroutines, but you *can* manually check if
the worker was cancelled." Checking a flag is useless here, because the thread is parked inside
`communicate()` waiting on a process that may never return. Calling `worker.cancel()` would mark the
worker cancelled and leave the child running and the thread blocked forever.

Killing the process is therefore not an optimisation, it is the mechanism. `communicate()` returns
as soon as the child dies, the worker finishes, and control returns — comfortably inside SC-002's
one-second budget.

The **group** matters because assistant CLIs spawn children of their own; terminating only the
direct child can orphan them. Platform branch:

| Platform | Launch | Terminate |
|---|---|---|
| POSIX | `start_new_session=True` | `os.killpg(os.getpgid(pid), SIGTERM)` |
| Windows | `creationflags=CREATE_NEW_PROCESS_GROUP` | `proc.terminate()` |

The reply is discarded whether or not it arrives after cancel (FR-013): the editor checks that the
request it is completing is still the current one before inserting anything.

**Alternatives considered**:

- **`asyncio.create_subprocess_exec` in an async worker.** Genuinely cancellable, but it puts an
  event loop between `core` and its tests, which Principle I forbids — core must be callable
  "without a terminal, a TTY, or an event loop". Synchronous `subprocess` in a thread worker keeps
  `core` plain and testable.
- **A timeout instead of cancel.** Rejected by the spec: there is no time limit, and cancel is the
  answer to a slow assistant.

---

## R5 — Intercepting `Enter` in the editor

**Decision**: Subclass `TextArea`, override `_on_key`, call `event.prevent_default()` when the
current line parses as a registered command.

**Rationale**: This is the documented extension point — Textual's `TextArea` guide shows exactly
this pattern ("Hooking into key presses": override `_on_key` in a subclass and call
`event.prevent_default()`), using auto-closing parentheses as the worked example. It runs before the
built-in newline insertion, which is what FR-006 needs: on a command line, Enter must run the
command instead of splitting the line.

The subclass posts a message; the screen handles it. Parsing itself stays in `core`
(`editor_commands.parse_line`), so the widget only asks "is this a command?" and never owns the
grammar.

**Alternatives considered**: A screen-level `Binding("enter", ...)` with `priority=True`. Rejected:
it would intercept Enter on *every* line, and the screen would then have to re-implement newline
insertion for the 99% case — reimplementing a core editing behaviour to add a rare one.

---

## R6 — Locking the editor during a request

**Decision**: `TextArea.read_only = True` for the duration.

**Rationale**: The constructor documents `read_only` as "Enable read-only mode. This prevents edits
using the keyboard" — exactly FR-012, with no custom key filtering. The cursor stays visible
(`show_cursor` defaults to `True` in read-only mode), so the editor still looks like the user's
document rather than a modal takeover. `ctrl+c` is a screen binding and is unaffected by the
widget's read-only state, so cancel keeps working while typing does not.

**Alternatives considered**: `disabled = True`. Rejected: it greys the widget and drops focus,
which reads as "the editor broke" rather than "endpaper is thinking", and would take the cancel
binding's focus context with it.

---

## R7 — The working indicator

**Decision**: The document line shows a static `⋯`; the status bar carries a randomly chosen
corporate-jargon breadcrumb — `Leveraging synergies… — ctrl+c to cancel`. One pick per request. No
animation, no timer.

**Rationale**: Issue #19 asks for "a working icon such as three dots or a spinning wheel, plus
'ctrl+c to cancel'" — three dots is one of the two options it names, and it is the one that needs no
timer. An animated spinner in the document would mean rewriting a document line several times a
second, which churns `TextArea`'s undo checkpoints for no user benefit. Putting the motion-free
placeholder in the document satisfies FR-011's "replaced in place", and the status bar carries the
cancel affordance for the whole wait, satisfying both FR-011 and Principle V's footer rule.

**Why the breadcrumb costs nothing.** Choosing one phrase when the request starts and holding it
until control returns needs no timer, so the no-animation decision survives intact. Cycling phrases
would need a `set_interval` — harmless on the status bar, unlike the document line — but it would
also *imply progress*, and there is none to imply: the assistant either returns or it does not. A
phrase that changes every two seconds while nothing has actually advanced is a progress bar that
lies.

The register is deliberate. endpaper's user is, per the Platform constraints, a corporate employee
on a managed machine, frequently screen-sharing — so the whimsy is drawn from meeting jargon rather
than from developer in-jokes. It is the vocabulary of the meetings they are taking notes in, which
makes it land for this audience specifically and stay safe on a shared screen.

The full list, the width fallback, and the testing rule live in
[contracts/editor-commands.md](./contracts/editor-commands.md) so there is one place to edit when a
phrase stops being funny.

**Crash safety**: the indicator exists only in the buffer and is never saved. The pre-invocation
save (FR-008) writes the document *including* the `/ai <prompt>` line, so a crash mid-request leaves
a file containing the user's prompt — recoverable and self-explanatory — never a stray `⋯`.

---

## R8 — What the assistant is told about the document

**Decision**: Pass the saved document's absolute path in the composed prompt and let the assistant
read it with its own tools.

**Rationale**: FR-008 saves before invoking precisely so there is a file on disk to point at, and
FR-009 requires the assistant to be able to resolve "the process described on lines 15-18". Both
tools are agents with file access already scoped to this directory. Passing a path rather than
embedding contents keeps the invocation small regardless of document size, avoids a second copy of
the user's notes in a process argument list, and leaves the decision of *how much* to read to the
assistant.

The composed prompt also tells the assistant that the `/ai` line it will find in the file is the
command being answered and that its reply replaces that line — otherwise a careful assistant might
treat the command text as content worth preserving.

**Alternatives considered**: Embedding the document text in the prompt. Rejected: unbounded argument
size on large notes, and it duplicates content the assistant can already read.

---

## R9 — Writing the config setting without a TOML writer

**Decision**: Read with `tomllib`; write with a line-targeted edit of the raw file text.

**Rationale**: `tomllib` is read-only — the standard library ships no TOML writer, and adding
`tomli-w` would be a third-party dependency for one key. A whole-file rewrite from a parsed dict
would silently drop comments and any key a future version added, which sits badly beside Principle
IV's instinct not to destroy what the user wrote by hand.

The repo already has the pattern: `core.editing.stamp_updated` replaces exactly one line of
frontmatter and changes no other byte. `config.set_assistant` does the same thing — replace the
`name = "..."` line inside `[assistant]` if it exists, append the two-line table if it does not,
and leave every other byte untouched.

**Alternatives considered**:

- **`tomli-w`.** Rejected: a dependency for one key, and it discards comments on round-trip.
- **`tomlkit`** (style-preserving). Rejected: a much larger dependency, and the same result is a
  dozen lines of targeted editing here.

**Schema impact**: none. `[assistant]` is a new top-level table; `workspace.schema` stays `1`.
`_check_schema` reads only `workspace.schema`, so a config written by this version still opens in an
older build, and a config written by an older build is missing the table — which resolution already
treats as "detect" (FR-030). Adding a key is a minor change under Principle VI.

---

## R10 — Detecting an installed assistant

**Decision**: `shutil.which(profile.binary)`.

**Rationale**: Standard library, and it is the one call that is correct on Windows — it consults
`PATHEXT`, so `claude.cmd` and `claude.exe` resolve without endpaper knowing anything about
extensions. It answers exactly the question FR-023 asks ("is this assistant available to run on this
machine") without launching anything, so detection costs nothing and cannot hang.

Detection runs when the setting is absent. With exactly one match it is used (SC-007); with more
than one the user is told to choose (FR-023) rather than having one picked for them.

**Alternatives considered**: Running `<binary> --version` to confirm the tool works. Rejected: it
spawns a process on a path that is supposed to be free, and a binary that resolves but fails to run
already produces a clear error at invocation time.

---

## R11 — Where `/config` lives

**Decision**: `config` is a **command-bar** verb (the existing `/` bar on the list screen), not an
in-editor command.

**Rationale**: The two command surfaces have different subjects. In-editor commands act on the
document under the cursor; command-bar verbs act on the workspace. Changing which assistant endpaper
calls is a workspace action with no relationship to any open document.

This is also a testable answer rather than a preference:
`tests/unit/test_command_parsing.py::test_existing_verbs_unchanged` pins the verb table to an exact
set, so adding `config` is a deliberate edit to a guarded list — the spec's Dependencies section
already names this test as one the feature must update.

---

## R12 — Test strategy for a feature that shells out

**Decision**: A **stub binary** fixture — a Python script written into `tmp_path`, made executable,
and named as the profile's binary — with modes for echo, non-zero exit, empty output, and sleep.

**Rationale**: Principle VI wants risk-based coverage, and the risks here are the failure paths:
missing binary, non-zero exit, empty reply, cancel mid-flight, save failure before invoke. All five
are reachable with a stub and none require an installed assistant, a network, or an API key — which
also keeps CI honest on a machine that has neither tool.

The stub doubles as the FR-010 check: an echo mode that prints its own argv proves the instructions
and the document path actually reached the command line.

Layer assignment (Principle VI — a behaviour is not re-verified at every layer it touches):

| Risk | Layer |
|---|---|
| `/ai` mid-line, `/aim`, `//ai`, unknown `/word` are plain text | `unit/` — pure parser |
| Resolution: configured, absent-with-one, absent-with-two, `none` | `unit/` — pure logic |
| Config write creates the key, preserves comments and unknown keys | `unit/` |
| Editor round trip: save → lock → indicator → insert reply | `integration/` |
| Cancel returns control and restores the prompt line | `integration/` |
| Assistant fails / returns nothing → message shown, document intact | `integration/` |
| `endpaper config assistant` exit codes, `--json` shape, non-blocking | `contract/` |

---

## R13 — Granting the assistant permission to read the document

**Decision**: Each profile's `build_args` adds a read-only tool-permission flag —
`--allowedTools "Read"` for Claude Code CLI, `--allow-tool "read"` for GitHub Copilot CLI — on top
of the shared `["-p", prompt]` shape.

**Rationale**: `compose_prompt` (R8) deliberately passes a file path and a line number rather than
the document's contents, so that positional requests ("the paragraph above") are answered by the
assistant reading the file itself. Both CLIs' own documentation is explicit that this does not work
for free: `-p`/print mode does not auto-approve tool calls, including a plain file read, because the
approval prompt that would normally ask the user has no TTY to appear on. Claude Code's headless
docs give exactly this shape as the fix (`--allowedTools "Bash,Read,Edit"`); Copilot CLI's
equivalent is `--allow-tool "read"`. Without the flag, the assistant's read attempt is silently
denied and R8's whole design — small invocation, no duplicated document contents, assistant decides
how much to read — quietly stops working while `/ai` still appears to run normally.

**Read only, nothing else.** Granting `Bash`, `Edit`, or a write-capable tool was not considered:
FR-018 already instructs the assistant not to edit any file, and enforcing that at the permission
level — rather than trusting the model to follow the instruction — costs nothing extra here, since
the two flags are string literals in the profile registry, not a new argument or a new failure mode.

**Alternatives considered**: Embedding the document text in the prompt instead of a path, removing
the need for the assistant to read anything. Rejected for the same reasons R8 already rejected it —
unbounded prompt size, and a second copy of the user's notes traveling through a process argument
list.
