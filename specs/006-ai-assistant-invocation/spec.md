# Feature Specification: Local AI Assistant Invocation

**Feature Branch**: `006-ai-assistant-invocation`

**Created**: 2026-07-30

**Status**: Draft

**Input**: User description: "Issue 19"

**Source**: GitHub issue #19 "[Feature]: Local AI assistant invocation from inside endpaper"
(milestone v0.0.2), which asks for an in-editor `/ai <prompt>` command, support for Claude Code CLI
and GitHub Copilot CLI, two ways to configure which of them to call, and reusable scaffolding for
future in-editor commands.

**Builds on**: Feature `004-viewing-editing`, which delivered the editor, its save path, and the
bottom status area; and feature `005-ui-layout-refresh`, which delivered the `/` command bar's verb
table and the help pane. The in-editor command framework specified here is a *second* command
surface: the existing `/` verbs are typed into a command bar on the list screen, while these are
typed into the document itself.

## Overview

endpaper assumes its user already has a local AI assistant — Claude Code CLI or GitHub Copilot
CLI — pointed at the workspace. Today that assistant is only reachable from another terminal:
the user leaves the note they are writing, describes what they want, copies the answer back, and
returns. This feature closes that loop. While editing a document, typing `/ai <prompt>` on a fresh
line and pressing Enter sends the prompt to the configured assistant and drops its reply into the
document at that spot.

It also establishes two things the next features will reuse: a way to run commands from inside the
editor (so `/task`, `/pic`, and others can follow), and a way to record which assistant this user
runs.

**Scope note**: `AI invocation from inside endpaper` and `Any configuration beyond workspace paths`
are both listed in `REQUIREMENTS.md` §5 as out of scope for v0.0.1. This specification moves both
into v0.0.2, which is the sanctioned way to lift an out-of-scope item (Constitution, *Development
Workflow & Quality Gates*).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask the assistant without leaving the note (Priority: P1)

A user is part-way through writing a meeting note. They want a flowchart of the process they just
described, or a tidier summary of the three bullets above the cursor. They start a new line, type
`/ai Write a flowchart of the process described on lines 15-18`, and press Enter. The document
saves, the command line is replaced by a working indicator, and a few seconds later the assistant's
reply sits in the document where the command was.

**Why this priority**: This is the entire point of the feature. It is the one capability a user
would notice missing, and it delivers value on its own — a user who never touches the configuration
commands still gets this the moment they have an assistant installed.

**Independent Test**: Open any document, type `/ai <prompt>` on its own line, press Enter, and
confirm the reply lands in the document at that position with the rest of the file untouched.
Testable without any configuration when exactly one supported assistant is installed.

**Acceptance Scenarios**:

1. **Given** a document open for editing with an assistant available, **When** the user types
   `/ai summarise the bullets above` as the entire content of a line and presses Enter, **Then**
   the document is saved, the command line is replaced by a working indicator, and on completion
   the assistant's reply occupies that position in the document.
2. **Given** a multi-line reply, **When** it is inserted, **Then** every line of the reply appears
   in order and no line of the surrounding document is altered, reordered, or lost.
3. **Given** the reply itself contains a line beginning with `/ai`, **When** it is inserted,
   **Then** it is inserted as plain text and is not executed.
4. **Given** the user types `Did you know you can type /ai in endnotes?`, **When** they press
   Enter, **Then** nothing is sent to any assistant and the text remains exactly as typed.
5. **Given** the user types `/ai` with no prompt after it, **When** they press Enter, **Then** a
   message explains that `/ai` needs a prompt, the line is left as typed, and control stays with
   the user.
6. **Given** no supported assistant is configured or installed, **When** the user runs `/ai`,
   **Then** the error names the command to run to configure one and the document is unchanged.
7. **Given** a user who has never used the feature, **When** they open the editor's help, **Then**
   `/ai` is listed with its argument shape and a one-line description.
8. **Given** the user types `/summarise the bullets above` — a command word the editor does not
   know — **When** they press Enter, **Then** the line stays as ordinary text, no error appears,
   and typing continues uninterrupted.

---

### User Story 2 - Stay in control while the assistant works (Priority: P2)

The assistant is slow, or offline, or the prompt was a mistake. The user needs a guaranteed way
back to their document, and a guarantee that whatever happened, the words they had already written
are still there.

**Why this priority**: A feature that can strand the user in a locked editor, or that can eat a
paragraph on failure, is worse than not having the feature — the vault is the user's own notes
(Constitution IV). This story is separable from US1 because it is exercised entirely through the
failure and cancel paths, and it can be tested against a stubbed slow or failing assistant.

**Independent Test**: Invoke `/ai` against an assistant that never returns; press `ctrl+c`; confirm
control returns immediately and the document matches its pre-command state with the prompt text
recoverable.

**Acceptance Scenarios**:

1. **Given** the editor is waiting on a reply, **When** the user presses `ctrl+c`, **Then** control
   returns to the editor immediately, the request is abandoned, and no reply is inserted even if
   one arrives afterwards.
2. **Given** the user cancelled, **When** control returns, **Then** the original `/ai <prompt>` line
   is restored exactly as typed so it can be edited and retried.
3. **Given** the editor is waiting on a reply, **When** the user presses any other key, **Then**
   the document buffer is unchanged by that keystroke.
4. **Given** the assistant exits with an error, is not installed, or has no network, **When** the
   failure is detected, **Then** a transient message naming the problem appears at the bottom of
   the screen, control returns to the user, and the document is byte-identical to its saved state.
5. **Given** the pre-invocation save fails, **When** the failure is detected, **Then** no assistant
   is invoked, the save error is reported, and control returns with the buffer intact.
6. **Given** the assistant returns an empty reply, **When** it is processed, **Then** the user is
   told the reply was empty and the original `/ai <prompt>` line is restored.
7. **Given** the editor is not waiting on a reply, **When** the user presses `ctrl+c`, **Then**
   existing behaviour is unchanged.
8. **Given** the document on disk was modified by something else while the request was in flight,
   **When** the reply arrives, **Then** the user is warned that the file changed and is not left to
   discover afterwards that those changes were overwritten.
9. **Given** an assistant that would normally wait for input, **When** it is invoked, **Then**
   endpaper never sits waiting on a prompt the user cannot see; the request either completes,
   fails with a message, or remains cancellable.

---

### User Story 3 - Choose which assistant endpaper calls (Priority: P3)

A user has both Claude Code CLI and GitHub Copilot CLI installed, or has neither, or wants a
particular workspace to use the assistant they did not install first. They need to say which
assistant is theirs, once, and have it stick.

**Why this priority**: Auto-detection covers the common case (US1 works without this story), so this
is the smaller slice. It becomes necessary only when the choice is ambiguous — but when it is
ambiguous, nothing else works.

**Independent Test**: Set the assistant, restart endpaper, and confirm the setting is still in
effect and reported back; verify without invoking any assistant.

**Acceptance Scenarios**:

1. **Given** a workspace with no assistant recorded, **When** the user runs `/config assistant
   claude` in the TUI, **Then** the setting is written, takes effect immediately for the next `/ai`,
   and survives a restart.
2. **Given** a configuration that has no assistant setting, **When** one is set, **Then** the
   setting is created rather than the command failing.
3. **Given** the user passes a value that is not a supported assistant, **When** the command runs,
   **Then** the error lists the accepted values and nothing is written.
4. **Given** the CLI, **When** `endpaper config assistant claude` is run, **Then** it has the same
   effect as the TUI command and exits 0 without prompting for anything.
5. **Given** the CLI, **When** the current setting is read with structured output requested, **Then**
   it is printed to stdout as structured data and the command exits 0.
6. **Given** `endpaper init --assistant copilot`, **When** the workspace is created, **Then** the
   assistant is recorded as part of initialisation with no interactive prompt.
7. **Given** the assistant is set to `none`, **When** the user runs `/ai`, **Then** it reports that
   no assistant is configured and does not attempt auto-detection.
8. **Given** no assistant is recorded and both supported assistants are available, **When** the user
   runs `/ai`, **Then** they are told to choose one explicitly and named the command that does it,
   rather than one being picked for them.
9. **Given** a workspace whose configuration predates this feature and has no assistant setting,
   **When** endpaper is used, **Then** everything behaves as before and reading the setting is not
   an error.
10. **Given** two workspaces configured with different assistants, **When** the user works in each,
    **Then** each uses its own setting and neither is affected by the other.

---

### Edge Cases

- **`/ai` that is not a command**: `/ai` preceded by any character on the line (including a space or
  a list marker like `- `), `/aim`, `//ai`, or `/ai` appearing mid-line. All are plain text. A line
  whose entire content is `/ai <prompt>` is a command regardless of whether it sits inside a fenced
  code block — fence awareness is deliberately not modelled (see Assumptions).
- **Unregistered in-editor commands**: a line reading `/summarise this` is plain text, not an error.
  The editor does not warn about commands it does not know, because the user is writing prose.
- **Assistant configured but missing**: the configured assistant is recorded as `claude` but the
  Claude Code CLI is not available — the error names the configured assistant and the fact that it
  could not be found, rather than reporting a generic failure.
- **Assistant edits the file itself**: the assistant is capable of writing to the workspace. If it
  modifies the open document while endpaper holds a buffer, the buffer would overwrite its edits on
  the next save. The request instructs the assistant to reply rather than edit, and the user is
  warned if the file on disk changed while the request was in flight.
- **Very long or never-returning request**: there is no time limit. The cancel affordance stays on
  screen for the entire wait so the user is never without a way out.
- **No network**: `/ai` fails with a clear message. Every other endpaper operation continues to work
  offline exactly as before (Constitution, *Platform & Distribution Constraints*).
- **Reply with unusual content**: replies containing frontmatter delimiters (`---`), trailing
  whitespace, or foreign line endings are inserted without corrupting the document's own frontmatter
  or its line-ending convention.
- **Terminal resize during the wait**: the working indicator and the cancel hint remain legible.
- **Two workspaces, different assistants**: the setting is read from the workspace in scope, not
  from a global one, so a user working in two workspaces gets the right assistant in each.

## Requirements *(mandatory)*

### Functional Requirements

**In-editor command framework** (reusable scaffolding — issue #19 item 4)

- **FR-001**: The editor MUST recognise a command only when the submitted line's entire content is
  a registered command word prefixed with `/`, optionally followed by a space and argument text.
  Any other occurrence of `/word` MUST be treated as ordinary document text.
- **FR-002**: A line beginning with `/` whose command word is not registered MUST be treated as
  ordinary document text, with no error and no interruption to typing.
- **FR-003**: The set of in-editor commands MUST be extensible: adding a command MUST NOT change
  how existing commands are recognised, dispatched, or displayed.
- **FR-004**: In-editor commands MUST be discoverable from the editor's help without the user
  having to know them in advance.
- **FR-005**: Text inserted into the document by any command MUST NOT itself be interpreted as a
  command.

**Invoking the assistant** (issue #19 item 1)

- **FR-006**: Users MUST be able to send a prompt to the configured assistant by submitting a line
  whose content is `/ai` followed by prompt text.
- **FR-007**: `/ai` with no prompt text MUST report that a prompt is required, leave the line as
  typed, and return control to the user without contacting any assistant.
- **FR-008**: On invocation the system MUST save the document in its current state before
  contacting the assistant. If the save fails, the assistant MUST NOT be contacted and the save
  error MUST be reported.
- **FR-009**: The request MUST identify the saved document to the assistant so the assistant can
  read the content the prompt refers to (for example, "the process described on lines 15-18").
- **FR-010**: The request MUST include instructions to the assistant stating that its reply is being
  inserted directly into a working-notes editor, that it should answer the user's query directly in
  a form appropriate to that medium, and that it should reply rather than edit files itself.
- **FR-011**: While a request is in flight the command text MUST be replaced in place by a working
  indicator together with a visible statement that `ctrl+c` cancels.
- **FR-012**: While a request is in flight the editor MUST NOT accept edits to the document buffer;
  the only input that acts is cancel.
- **FR-013**: `ctrl+c` during a request MUST return control to the user immediately, abandon the
  request, restore the `/ai <prompt>` line exactly as typed, and discard any reply that arrives
  afterwards.
- **FR-014**: On success the reply MUST replace the working indicator at the same position in the
  document, preserving every line of surrounding content, the document's line-ending convention, and
  its trailing-newline state.
- **FR-015**: An empty reply MUST be reported to the user and MUST restore the `/ai <prompt>` line
  rather than inserting nothing silently.
- **FR-016**: Any failure — assistant not found, assistant exits with an error, no network,
  unreadable output — MUST display a transient message at the bottom of the screen naming what went
  wrong, return control to the user, and leave the document as it was saved in FR-008.
- **FR-017**: A failed or cancelled request MUST NEVER remove, truncate, or reorder any line the
  user wrote.
- **FR-018**: The system MUST detect that the document changed on disk while the request was in
  flight and warn the user rather than silently overwriting those changes.

**Assistant support** (issue #19 item 2)

- **FR-019**: The system MUST support Claude Code CLI and GitHub Copilot CLI as assistants.
- **FR-020**: Adding support for a further assistant MUST NOT require changes to `/ai`'s user-facing
  behaviour, its error messages, or the in-editor command framework.
- **FR-021**: All supported assistants MUST be invoked non-interactively — no assistant may leave
  endpaper waiting on a prompt, a pager, or a confirmation the user cannot see.

**Configuration** (issue #19 item 3)

- **FR-022**: The system MUST record which assistant the user runs, as one of the supported
  assistants or `none`.
- **FR-023**: When no assistant has been recorded, the system MUST resolve one by detecting which
  supported assistants are available; if exactly one is available it MUST be used, and if more than
  one is available the user MUST be told to choose explicitly.
- **FR-024**: When the recorded assistant is `none`, `/ai` MUST report that no assistant is
  configured and MUST NOT fall back to detection.
- **FR-025**: Users MUST be able to set the assistant from the TUI with `/config assistant
  <claude|copilot|none>`, taking effect immediately and creating the setting if it does not exist.
- **FR-026**: Users MUST be able to set and read the assistant from the CLI, non-interactively,
  with the read form available as structured output (Constitution II).
- **FR-027**: `endpaper init` MUST accept the assistant choice as an argument and record it during
  initialisation. `endpaper init` MUST remain non-blocking and MUST NOT prompt (Constitution II).
- **FR-028**: An unsupported assistant value MUST be rejected with an error listing the accepted
  values, writing nothing.
- **FR-029**: The recorded assistant MUST be stored in the workspace's own configuration alongside
  the existing workspace settings, MUST persist across restarts, and MUST NOT leak between
  workspaces.
- **FR-030**: A workspace whose configuration contains no assistant setting MUST continue to work
  exactly as before, and reading it MUST NOT be an error.

**Boundaries**

- **FR-031**: No endpaper operation other than `/ai` may require an assistant, a network connection,
  or an installed assistant. A machine with no assistant installed MUST retain full use of every
  other feature.
- **FR-032**: Public-surface changes introduced here — the configuration key, the new CLI command,
  the new `init` argument — MUST be recorded in the changelog with their version
  (Constitution VI).

### Key Entities

- **Assistant profile**: A supported AI assistant. Carries the name the user configures it by
  (`claude`, `copilot`), how it is detected as available, and how a prompt is handed to it and a
  reply read back. New profiles are added without touching command behaviour.
- **Assistant setting**: The user's recorded choice of assistant profile for a workspace — one of
  the supported names, or `none`. Absent means "detect".
- **In-editor command**: A command word usable from inside the editor, its argument shape, and its
  one-line description for the help pane. `/ai` is the first; `/task` and others follow.
- **Assistant request**: One in-flight invocation — the user's prompt, the saved document it refers
  to, the instructions given to the assistant, and its cancellable state.
- **Assistant reply**: The text returned for a request, destined for insertion at the position the
  command occupied.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from a question in their head to the answer in their document without
  leaving the editor, switching windows, or copying text — one line typed and one Enter.
- **SC-002**: Cancelling a request returns control to the editor within one second, every time,
  regardless of what the assistant is doing.
- **SC-003**: Across every failure path — no assistant, wrong assistant, no network, error exit,
  empty reply, cancel, failed save — 100% of attempts leave the user's own words intact, with no
  partial insertion and no lost line.
- **SC-004**: Text containing `/ai` that is not a command produces zero invocations. A user can
  write about the feature in their notes without triggering it.
- **SC-005**: A user who switches from one supported assistant to the other sees identical `/ai`
  behaviour — same keystrokes, same indicator, same error wording — with no relearning.
- **SC-006**: On a machine with no assistant installed, 100% of endpaper's other functionality
  continues to work, offline, unchanged.
- **SC-007**: A user with exactly one supported assistant installed can use `/ai` successfully
  without having configured anything.
- **SC-008**: The assistant choice, once set, is still in effect after restarting endpaper and is
  reportable without guesswork.

## Assumptions

Defaults chosen where issue #19 did not specify, and the one place where it was reconciled against
the constitution.

**Reconciled with the constitution** — this deviates from the literal text of issue #19 and should
be confirmed before planning:

- **`endpaper init` does not prompt.** Issue #19 item 3 says the user "should be asked" at `init`
  which assistant they use. Constitution II states the CLI "MUST NOT block on input. No prompts, no
  confirmations, no pagers" — as a hard requirement, because the CLI is an AI assistant's only
  interface and a prompt turns an automation into a hang. This spec therefore records the choice via
  an argument to `init` (FR-027) and provides `/config assistant` (FR-025) as the interactive path,
  which together preserve the intent — configure at init, change later — without the prompt.

**Straightforward defaults**:

- **A workspace belongs to one user**, so the assistant setting lives in that workspace's own
  configuration file alongside the existing workspace settings, exactly as issue #19 describes. The
  constitution's rule that per-user state must not go in the shared workspace directory is aimed at
  two people overwriting each other's choice, which cannot happen while a workspace has a single
  user. When shared workspaces arrive they will nest each user's workspace one level below a parent
  workspace with its own configuration file, so the per-user workspace file stays per-user and this
  setting does not have to move. Adding a setting at all still needs a justification against
  Constitution III ("configuration beyond workspace paths is out of scope") in the plan's Complexity
  Tracking table.

- The assistant is invoked once per `/ai`, with no conversation carried between invocations. Session
  continuity is out of scope.
- The prompt is a single line. Multi-line prompts, and prompts that span a selection, are out of
  scope.
- The document is saved before invocation (FR-008) specifically so the assistant can read it from
  disk; the request passes the document's location rather than embedding its contents. What the
  assistant then does with that content is governed by the assistant's own configuration, not by
  endpaper.
- After a reply is inserted the document is left unsaved, exactly as if the user had typed the text.
  The user saves with the existing binding.
- There is no time limit on a request. Cancel is the answer to a slow assistant, and the cancel hint
  is visible for the whole wait.
- Fenced code blocks are not modelled. A line whose whole content is `/ai <prompt>` is a command
  wherever it appears. The alternative — tracking fence state to decide whether Enter runs a command
  — is more machinery than the case is worth, and the workaround (indent the line, or put text
  before it) is immediate.
- Auto-detection means "is this assistant available to run on this machine". Detecting more than one
  is reported rather than resolved by a precedence order, so endpaper never silently picks the
  assistant the user did not mean.
- `ctrl+c` is used as the cancel key per issue #19. Constitution V reserves `ctrl+c`; it is accepted
  here only for the duration of an in-flight request, where the editor is locked and cancelling is
  the only action available, and it returns to its reserved meaning as soon as control returns.
- The transient error message uses the editor's existing bottom-of-screen status area rather than a
  new surface.
- Only `/ai` is delivered. `/task` and other in-editor commands are named here to shape the
  framework, and are not implemented by this feature.

**Dependencies**:

- Requires the editor delivered by feature 004 and the status area it already uses.
- Requires that the user has separately installed and authenticated their assistant. endpaper does
  not install, update, or authenticate assistants.
- Moves two items out of `REQUIREMENTS.md` §5's v0.0.1 out-of-scope list, as noted in the Overview.
