# Feature Specification: Assistant Discovery File

**Feature Branch**: `013-assistant-discovery-file`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Issue #37. You are spec 013."

**Source**: GitHub issue #37 "[Feature]: /config assistant should drop skill files", milestone v0.0.3.
The issue observes that `AGENTS.md` is generated into the workspace at `init`, so an assistant only
learns choom exists when it happens to be started with the workspace as its working directory —
which is the exception, because the workspace is a notes folder, not a project. Started anywhere
else, the assistant knows nothing about the tool, the workspace, or the file that explains both.

## Overview

Naming your assistant with `/config assistant <name>` (or `choom config assistant <name>`) today
records a setting and nothing else. This feature makes that same moment install a small,
choom-owned file in the assistant's own user-scope location — outside the workspace, in the user's
own profile — that says what choom is, where the current workspace is, and that the instructions
live in that workspace's `AGENTS.md`.

The file is a pointer, not a second copy of `AGENTS.md`. A duplicate of that content is a second
thing to keep in sync and would go stale the moment a workspace regenerates its own file, so the
same content rule that governs `AGENTS.md` — nothing an assistant could infer for itself, no
restating what another document already says — governs this one, more strictly.

Naming the assistant is not the only way in. choom already decides, without being asked, which
assistant `/ai` calls: with nothing configured and exactly one assistant installed on the machine,
it uses that one. A user in that position never types the command and so never gets the pointer.
So when choom starts and finds itself in that position with no discovery file installed, it offers
to install one — once. Answering no is recorded, and the question is not asked again.

The user-visible outcome: after naming the assistant once — or after answering one question at
launch, or after doing nothing but saying yes — starting the assistant in any directory on the
machine is enough. The user no longer opens each session by explaining where their notes live and
that there is a file describing how to write to them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The assistant finds choom from anywhere (Priority: P1)

Someone has a choom workspace in their OneDrive folder. They run `choom config assistant claude`
once, from that workspace. Later that week they start their assistant from a source repository on
the other side of the disk and ask it to note down what was just decided. The assistant already
knows choom is installed, knows the absolute path of the workspace, and knows to read that
workspace's `AGENTS.md` before touching anything — so it creates the meeting through the command
rather than by hand, with correct frontmatter, in the right partition.

Today the same request produces either a question ("where do you keep your notes?") or a file
written by hand into the wrong place with a made-up id.

**Why this priority**: This is the entire problem. Everything else in this spec is a refinement of
when the pointer is written or removed; without this story there is no feature. It is also the only
story that delivers the twenty seconds the tool exists to give back — the manual explanation at the
start of every session is the cost being removed.

**Independent Test**: Configure an assistant from inside a workspace, then start that assistant with
an unrelated directory as its working directory and ask it something that requires knowing where the
notes are. It identifies the workspace and reads its `AGENTS.md` without being told either. Delivers
the complete benefit on its own.

**Acceptance Scenarios**:

1. **Given** a workspace with a generated `AGENTS.md` and no discovery file installed, **When** the
   user sets the assistant to a supported assistant, **Then** a choom-owned discovery file exists at
   that assistant's user-scope location, outside the workspace.
2. **Given** the discovery file has been installed, **When** it is read, **Then** it states what
   choom is, gives the absolute path of the workspace it was installed from, and directs the reader
   to that workspace's `AGENTS.md` for the commands and file format.
3. **Given** the discovery file has been installed, **When** it is compared against the workspace's
   `AGENTS.md`, **Then** it restates none of that file's content — no layout, no frontmatter schema,
   no command list, no exit codes.
4. **Given** an assistant started with an unrelated working directory, **When** it is asked to
   record a meeting, **Then** it can locate the workspace and its `AGENTS.md` from the discovery
   file alone, with no path supplied by the user.
5. **Given** the user-scope directory for that assistant does not exist yet, **When** the assistant
   is configured, **Then** the directory is created and the file is written.
6. **Given** a workspace whose path contains spaces and non-ASCII characters, **When** the assistant
   is configured, **Then** the path in the discovery file reads unambiguously and can be used as
   given.

---

### User Story 2 - Offered at launch, asked once (Priority: P2)

Someone has choom and exactly one assistant installed. They have never run `config assistant`,
because they never had a reason to — `/ai` already works, since choom picks the only assistant on
the machine on its own. They open choom. It asks, once: an assistant was found, may choom tell it
where this workspace is? They answer yes, and the pointer is installed without them learning that a
command existed. Had they answered no, they would never be asked again.

**Why this priority**: US1 gives the pointer to users who type a command. This story gives it to
everyone else — the users who never had to name their assistant because choom named it for them,
which is the default path for anyone with a single assistant installed. It ranks below US1 because
it is the same install through a different door, and above the rest because a feature only reachable
by a command the user has no reason to run is a feature most users never get.

**Why it is a question and not an automatic install**: choom would be writing into the user's own
profile directory, outside the workspace, for a program choom does not own. That is not a default to
assume on someone's behalf. The constitution warns that confirmations which guard nothing teach
users to dismiss them reflexively (Principle V); the protection here is that this one is asked at
most once and the answer is durable in both directions, so it can never become the dialog a user
learns to swat away.

**Independent Test**: In a workspace with no assistant configured and exactly one assistant
installed, start choom and confirm the offer appears; answer no, restart, and confirm silence;
in a second workspace answer yes and confirm the pointer is installed.

**Acceptance Scenarios**:

1. **Given** a workspace with no assistant configured, exactly one assistant installed on the
   machine, and no discovery file for it, **When** choom starts, **Then** the user is asked whether
   to install the discovery file, and the question names the assistant and the workspace.
2. **Given** that question, **When** the user answers yes, **Then** the discovery file is installed
   for that assistant pointing at that workspace, the assistant is recorded as the workspace's
   setting, and the outcome is reported.
3. **Given** that question, **When** the user answers no, **Then** nothing is installed, the refusal
   is recorded in the workspace's configuration, and choom continues to start normally.
4. **Given** the user has answered no, **When** choom starts again in that workspace — on that
   launch or any later one — **Then** the question is not asked again.
5. **Given** that question, **When** the user dismisses it without answering — by closing it, or by
   quitting choom — **Then** nothing is installed and nothing is recorded, and the question may be
   asked again on the next launch.
6. **Given** a discovery file is already installed for the assistant choom would use, **When** choom
   starts, **Then** no question is asked.
7. **Given** two or more assistants are installed and none is configured, **When** choom starts,
   **Then** no question is asked, because choom does not know which assistant the user means.
8. **Given** the assistant is configured as `none`, **When** choom starts, **Then** no question is
   asked — an explicit opt-out is never re-litigated at launch.
9. **Given** the user has previously answered no, **When** they later run the set command naming an
   assistant, **Then** the file is installed and the recorded refusal is cleared, because an
   explicit request outranks an earlier declined offer.
10. **Given** the question is showing, **When** the user answers either way, **Then** it takes one
    keystroke and choom is fully usable immediately afterwards.

---

### User Story 3 - Repointing and removal (Priority: P3)

The user starts a second workspace — a new job, a separate personal vault — and runs
`choom config assistant claude` from it. The pointer now names the new workspace. Later they decide
they would rather their assistant not know about choom at all, and run
`choom config assistant none`; the file is gone.

**Why this priority**: A pointer that can only be written once is a pointer that is wrong as soon as
anything changes, and a stale absolute path is worse than no path — it sends the assistant to a
directory that may not exist. Removal is the same guarantee in the other direction: a user who opts
out must actually be opted out, with nothing left behind in their profile.

**Independent Test**: Configure the assistant from workspace A, then from workspace B, and confirm
the file names B and only B. Then set the assistant to `none` and confirm no choom-installed file
remains anywhere in user scope.

**Acceptance Scenarios**:

1. **Given** a discovery file pointing at workspace A, **When** the user configures the same
   assistant from workspace B, **Then** the file points at workspace B and mentions workspace A
   nowhere.
2. **Given** a discovery file installed for one supported assistant, **When** the user configures a
   different supported assistant, **Then** the new assistant's file is installed and the previous
   assistant's choom-installed file is removed, leaving exactly one.
3. **Given** a discovery file is installed, **When** the user sets the assistant to `none`, **Then**
   the file is removed and the setting is recorded as `none`.
4. **Given** no discovery file has ever been installed, **When** the user sets the assistant to
   `none`, **Then** the command succeeds and nothing is reported as an error.
5. **Given** a discovery file has been hand-edited by the user, **When** the assistant is configured
   again, **Then** the file is rewritten in full from choom's own content rather than merged, and it
   carries a line saying it is generated and will be overwritten.
6. **Given** the user reads the setting rather than writing it — the command invoked with no value —
   **When** it completes, **Then** no file is written, moved, or removed.

---

### User Story 4 - The command says what it did (Priority: P4)

The user runs `choom config assistant copilot` and sees, in one line, that the setting was recorded
and where the discovery file was written. On a locked-down machine where their profile directory is
not writable, they see instead that the setting was recorded but the file could not be written, and
which path failed and why.

**Why this priority**: This feature writes a file the user did not name, in a directory they did not
choose, outside the workspace they were standing in. Silence there is the wrong default: the user
cannot confirm the thing that makes the feature work, and cannot tell a silent failure from a silent
success. It ranks below the write itself because the write is still correct without the message.

**Independent Test**: Run the set command and read its output; make the user-scope location
unwritable and run it again, confirming the setting is still recorded and the problem is named.

**Acceptance Scenarios**:

1. **Given** a supported assistant is configured successfully, **When** the command completes,
   **Then** it reports the path of the file it wrote.
2. **Given** the discovery file cannot be written — the location is unwritable, or the path is
   otherwise unusable — **When** the assistant is configured, **Then** the setting is still recorded,
   the failure is reported on the error stream naming the path and the reason, and the command does
   not fail hard.
3. **Given** the assistant is set to `none` and a file is removed, **When** the command completes,
   **Then** it reports that the discovery file was removed.
4. **Given** the user reads the setting in machine-readable form, **When** the output is parsed,
   **Then** it reports where the discovery file is installed, or that it is not installed, alongside
   the existing fields, with no existing field renamed or removed.
5. **Given** the same set command is issued from the TUI command bar, **When** it completes, **Then**
   the same outcome is reported in the status bar — the two interfaces report the same result in
   their own idiom.

---

### User Story 5 - Naming the assistant at init (Priority: P5)

Someone creating their first workspace runs `choom init --assistant claude`. The discovery file is
installed then and there; they never run a second command.

**Why this priority**: `init --assistant` is the same act of naming an assistant, and it is the very
first moment the user has a workspace worth pointing at. It is last because it is a convenience on a
path the user can already complete with one more command, and dropping it leaves every other story
intact.

**Independent Test**: Run `init` with an assistant named, in a fresh directory, and confirm the
discovery file exists and points at the new workspace.

**Acceptance Scenarios**:

1. **Given** a fresh directory, **When** the user runs `init` naming a supported assistant, **Then**
   the workspace is created, the setting is recorded, and the discovery file points at the new
   workspace.
2. **Given** a fresh directory, **When** the user runs `init` naming no assistant, **Then** no
   discovery file is written.
3. **Given** a fresh directory, **When** the user runs `init` naming `none`, **Then** no discovery
   file is written and any previously installed one is removed.

---

### Edge Cases

- **The user-scope location is unwritable.** A managed Windows profile, a read-only home, a
  permission error: the setting write must not be reversed and the command must not fail hard. The
  user is told what could not be written and why.
- **The workspace moves or is deleted after the file is installed.** The pointer names a path that
  no longer resolves. choom does not detect this; the file is corrected the next time the assistant
  is configured. The file's wording must therefore not promise that the path still exists.
- **One synced workspace, two people.** The discovery file lives in each user's own profile, never
  in the workspace, so a shared or synced notes folder cannot carry one person's pointer onto
  another person's machine — the per-user-state rule the constitution already sets.
- **Two workspaces, both wanted.** Only one pointer exists; the last one configured wins. A user who
  keeps two workspaces gets the most recently configured one and runs the command again to switch.
- **A file already sits at the path choom owns.** It is overwritten. The path is choom-named, so the
  only realistic occupants are an older version of this same file or a copy the user made
  deliberately; choom never touches neighbouring files in that directory.
- **An unsupported or misspelled value.** Rejected exactly as it is today, with nothing written and
  nothing removed.
- **A supported assistant with no user-scope location that fits.** The setting is recorded and the
  command says plainly that no discovery file was installed for that assistant, rather than writing
  a file nothing will read.
- **A very long workspace path.** Combined with a long user-profile path, the discovery file's own
  path must still stay inside the Windows limit.
- **Repeat runs with nothing changed.** Running the same command twice leaves the same single file
  with the same content; there is no accumulation and no second copy.
- **The launch offer is dismissed rather than answered.** Closing the question, or quitting choom
  while it is up, is not an answer: nothing is installed, nothing is recorded, and the question is
  asked again next launch. Only an explicit no is durable.
- **The install fails after the user says yes.** The refusal is not recorded — the user did not
  refuse — so the offer stands for the next launch, and the failure is reported like any other.
- **The user declines, then changes their mind.** Running the set command installs the file and
  clears the recorded refusal. There is no state a user can get into where the explicit command is
  refused because of an earlier answer at launch.
- **The user declines, then removes the assistant and installs a different one.** The recorded
  refusal covers the workspace, not one assistant, so they are not asked again. Naming the new
  assistant with the set command still installs the pointer.
- **An assistant is installed after choom has been used for a while.** A workspace that previously
  resolved to no assistant starts resolving to one; the offer appears at the next launch, since it
  is the first launch at which there is anything to offer.
- **A second person opens the same synced workspace.** The refusal is recorded in the workspace, so
  a colleague sharing the folder inherits it and is not asked. What they lose is a question, not a
  setting — their own discovery file, if they want one, is still one command away.
- **The launch check runs where there is nothing to check.** No assistant installed, an unreadable
  configuration, or a workspace whose configuration cannot be written: choom starts normally and
  asks nothing. The check must never be what stops the app from opening.
- **A command-line invocation in the same situation.** The CLI never asks — it cannot, and must not.
  Nothing about the launch offer changes what any CLI command does or prints.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Setting the assistant to a supported assistant MUST install a discovery file at that
  assistant's user-scope location — the place that assistant reads on every session regardless of
  its working directory — outside the workspace directory.
- **FR-002**: The discovery file MUST state what choom is, the absolute path of the workspace it was
  installed from, and that the workspace's `AGENTS.md` holds the commands and file format.
- **FR-003**: The discovery file MUST NOT restate `AGENTS.md`: not the folder layout, the
  frontmatter schema, the task line format, the link syntax, the command list, or the exit codes. It
  carries only what an assistant cannot get by following the pointer.
- **FR-004**: The discovery file MUST stay short enough to be cheap to load in every session. The
  content rule in FR-003 is what binds; roughly 20 lines is its checkable backstop, not a budget to
  be spent.
- **FR-005**: The discovery file MUST identify itself as generated by choom and state that it is
  rewritten whenever the assistant is configured.
- **FR-006**: Every set of the assistant MUST rewrite the discovery file in full rather than merging
  into what is already there, so a pointer can never be half-updated.
- **FR-007**: Configuring an assistant from a different workspace MUST leave the discovery file
  naming the new workspace and nothing of the previous one.
- **FR-008**: After any successful set, at most one choom-installed discovery file MUST exist across
  all supported assistants' user-scope locations — the one for the configured assistant. Switching
  assistants removes the file choom installed for the previous one.
- **FR-009**: Setting the assistant to `none` MUST remove every choom-installed discovery file, and
  MUST succeed when there is none to remove.
- **FR-010**: choom MUST write and remove only the single path it names for itself in each
  assistant's user-scope location, and MUST NOT read, modify, or delete any other file there.
- **FR-011**: Missing directories in the user-scope location MUST be created; the feature MUST NOT
  require that the assistant has been run before.
- **FR-012**: Reading the setting — the command invoked with no value, in either interface — MUST
  NOT write, move, or remove any file.
- **FR-013**: The recorded setting MUST be written independently of the discovery file: a discovery
  file that cannot be written MUST NOT prevent or reverse the setting, and MUST NOT be fatal. The
  command's success or failure reports the setting write; the discovery file is reported alongside
  it, never in place of it.
- **FR-014**: A failure to write or remove the discovery file MUST be reported in both interfaces —
  in the CLI on the diagnostic stream, in the TUI in the status bar — naming the path and the
  reason.
- **FR-015**: A successful set MUST report the path written, or that the file was removed, in both
  the CLI and the TUI, each in its own idiom.
- **FR-016**: The machine-readable read output MUST report where the discovery file is installed, or
  that it is not installed, as an addition to the existing fields; no existing field is renamed or
  removed.
- **FR-017**: If a supported assistant has no user-scope location that it reads from every
  directory, the command MUST record the setting and say plainly that no discovery file was
  installed for it, rather than writing a file that nothing reads.
- **FR-018**: The workspace path MUST be written into the discovery file so that a path containing
  spaces or non-ASCII characters reads unambiguously and is usable as given.
- **FR-019**: The feature MUST require no network access, no administrative rights, and no
  interactive prompt or confirmation, in either interface.
- **FR-020**: `init` naming a supported assistant MUST install the discovery file for the workspace
  it just created; `init` naming no assistant MUST install nothing.
- **FR-021**: Rejected values MUST behave as they do today — the setting is unchanged, and no
  discovery file is written or removed.
- **FR-022**: When choom starts in a workspace where an assistant will be used but no discovery file
  is installed for it, and no refusal has been recorded, the user MUST be asked whether to install
  one. "Will be used" covers both the assistant choom selects on its own — nothing configured,
  exactly one installed on the machine — and an assistant explicitly configured whose file is
  missing.
- **FR-023**: The question MUST name the assistant it would tell and the workspace it would point
  at, so the user is not agreeing to an unnamed action.
- **FR-024**: Answering yes MUST install the discovery file exactly as the set command does, record
  that assistant as the workspace's setting, and report the outcome.
- **FR-025**: Answering no MUST install nothing and MUST record the refusal in the workspace's
  configuration, in a form that survives restarts.
- **FR-026**: A recorded refusal MUST suppress the question on every subsequent launch of that
  workspace.
- **FR-027**: Dismissing the question without answering MUST record nothing and install nothing,
  leaving the question to be asked again at the next launch. Only an explicit no is durable.
- **FR-028**: Setting the assistant explicitly MUST clear any recorded refusal, so an earlier
  declined offer can never suppress an install the user has directly asked for.
- **FR-029**: The question MUST NOT be asked when a discovery file is already installed for the
  assistant that will be used, when the assistant is configured as `none`, when two or more
  assistants are installed with none configured, or when no assistant is installed at all.
- **FR-030**: The launch check MUST NOT prevent, delay perceptibly, or fail the start of the app.
  A configuration that cannot be read or written means no question is asked, not an error.
- **FR-031**: Answering the question MUST take one keystroke, and choom MUST be fully usable
  immediately afterwards.
- **FR-032**: The question MUST be asked only in the interactive interface. No command-line
  invocation may prompt, block, or install without being told to.
- **FR-033**: The machine-readable read output MUST report whether the offer has been refused,
  so the state is visible without opening the interactive interface.

### Key Entities

- **Discovery file**: A short, choom-owned, fully generated file in the user's own profile. Holds a
  one-line description of choom, the absolute workspace path, and a pointer to that workspace's
  `AGENTS.md`. Exactly one exists at a time, or none.
- **Assistant user-scope location**: Per supported assistant, the path that assistant reads on every
  session irrespective of working directory, plus the file name choom claims within it. An assistant
  may have none, which is a reportable outcome rather than an error.
- **Workspace pointer**: The absolute path recorded in the discovery file — the workspace the
  command was run from, resolved. Correct as of the last time the assistant was configured; not
  monitored afterwards.
- **Assistant setting**: The existing per-workspace record of which assistant `/ai` calls. Unchanged
  by this feature, except that writing it now has a second, user-scope effect.
- **Recorded refusal**: A per-workspace record that the user was offered a discovery file at launch
  and said no. Set only by an explicit no, cleared by explicitly setting an assistant, and read only
  to decide whether to ask. It suppresses a question, never an install.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After naming their assistant once, a user starting that assistant from any directory
  on the machine — home, an unrelated project, the workspace itself — gets an assistant that can
  name the workspace path and locate its `AGENTS.md` without being told either, in all three cases.
- **SC-002**: The discovery file duplicates none of `AGENTS.md`: no instruction, heading, or example
  from that file appears in it.
- **SC-003**: Pointing choom at a different workspace takes exactly one command, after which no
  reference to the previous workspace remains in user scope.
- **SC-004**: Opting out takes exactly one command, after which no choom-installed file remains in
  any supported assistant's user-scope location.
- **SC-005**: When user scope cannot be written, the setting is still recorded in 100% of cases, and
  the message names both the path and the reason.
- **SC-006**: The discovery file stays within its 20-line backstop.
- **SC-007**: Configuring an assistant still completes without a perceptible pause and without
  reaching the network.
- **SC-008**: A user who has just created a workspace reaches "my assistant can work in it from
  anywhere" with no manual explanation of the workspace path and no hand-written file — at most one
  command beyond creating the workspace, and none when the assistant is named while creating it.
- **SC-009**: A user who has never run the assistant command, and has exactly one assistant
  installed, is offered the pointer without having to discover that any command exists, and reaches
  a working pointer in one keystroke.
- **SC-010**: A user who declines is asked exactly once, ever: zero further questions across any
  number of subsequent launches of that workspace.
- **SC-011**: The launch check adds no perceptible delay to opening choom, and no state it can
  encounter — no assistant, several assistants, an unreadable or unwritable configuration — prevents
  the app from starting.

## Assumptions

- **Where each assistant reads from.** For `claude`, a user-scope skill under the user's Claude Code
  profile directory; for `copilot`, a user-level instructions file under the user's Copilot CLI
  profile directory — the location Copilot CLI documents as applying across all repositories. Both
  exist today, so FR-017's "no location that fits" branch is a rule for future assistants rather
  than a case either current assistant hits. Confirming the exact paths and file names is planning
  work; this spec fixes the behaviour, not the spelling.
- **Only one pointer.** A single workspace is named at a time, and switching assistants removes the
  file installed for the previous one (FR-008). The opposite — leaving each configured assistant's
  file in place — would spread choom's footprint across the profile for assistants the user has
  stopped using, and `none` would have to hunt all of them down anyway.
- **`init --assistant` installs it too** (US5, FR-020). The issue names `/config assistant` as the
  moment the user names their assistant; `init --assistant` is the same act at an earlier moment. It
  is scoped as the lowest-priority story so it can be dropped without touching the rest.
- **The setting itself does not move.** Which assistant `/ai` calls stays where it is today, in the
  workspace config. Only the discovery file is user-scope, because it is the thing that must not be
  shared between two people using one synced folder.
- **The discovery file is choom's to overwrite.** It sits at a choom-named path and is regenerated
  in full on every run (FR-006); the file says so (FR-005). choom does not attempt to preserve hand
  edits.
- **No new per-user state store.** The discovery file is the only thing this feature puts in the
  user's profile; nothing else about the workspace is cached there.
- **`AGENTS.md` exists in the workspace.** It is generated at `init`. A workspace whose `AGENTS.md`
  the user deleted still gets a pointer to where it should be; regenerating it is not this feature's
  job.
- **The refusal is recorded in the workspace configuration**, alongside the assistant setting it
  belongs to, as directed. This is worth naming because the constitution requires per-user state to
  live outside the shared workspace, and two people sharing a synced folder do share this record.
  It is judged acceptable here on two grounds: the assistant setting itself already lives in the
  workspace configuration, so the refusal sits with the thing it qualifies rather than splitting one
  decision across two stores; and what a colleague inherits is the absence of a question, not an
  overwritten selection — their own pointer, in their own profile, remains one command away. The
  failure the constitution's rule exists to prevent is one person's state silently becoming another
  person's; that failure is not available here, because the discovery file itself is never shared.
- **The offer also covers a configured assistant whose file is missing** (FR-022). The narrower
  reading — offer only when choom picked the assistant itself — would permanently exclude every
  workspace configured before this feature existed, which is the entire current user base, and every
  user whose file was removed or whose earlier install failed. Since an explicitly configured
  assistant is a *stronger* statement of intent than one choom inferred, asking that user is the
  less presumptuous of the two cases, not the more.
- **Answering yes also records the assistant** (FR-024). Otherwise a workspace can hold a pointer to
  an assistant it has no record of, and installing a second assistant later would flip resolution to
  ambiguous while the pointer stayed behind. Recording it makes what choom will call and what got
  told about the workspace the same fact.
- **The refusal covers the workspace, not one assistant.** A user who says no is saying no to being
  asked, and re-asking them because they changed assistants would defeat the point. The set command
  remains the way back in, and it clears the refusal (FR-028).
- **The question belongs to the interactive interface only** (FR-032). A confirmation is inherently
  interactive, which is the constitution's own exemption to the two-interfaces rule; the CLI's peer
  behaviour is the set command, which installs the same file without asking anyone anything.

## Dependencies and Relationships

- **Depends on `AGENTS.md` being generated at `init`.** The discovery file is a pointer to it and
  carries none of its content; without that file the pointer leads nowhere.
- **Extends the existing assistant setting.** `config assistant` in both interfaces, and
  `init --assistant`, gain a side effect; their existing read, write, and validation behaviour is
  unchanged.
- **Related to #44** (linked task syntax in the composed prompt): the same problem — the assistant
  needs to be told how choom works — at the reply layer rather than the install and discovery layer.
  The two are independent and can land in either order.
- **Constrained by the constitution**: no network; no admin rights; paths stay well inside the
  Windows limit; the CLI never prompts, never blocks, and keeps data and diagnostics on separate
  streams; both interfaces offer every behaviour that is not inherently interactive. Two rules are
  in tension with this spec and are answered rather than ignored: per-user state normally lives
  outside the shared workspace (see the recorded-refusal assumption), and confirmations normally
  fire only when there is something to lose (see US2, where the protection is that the question is
  asked at most once and both answers are durable).

## Out of Scope

- A registry of several workspaces, or `workspace list` / `use` / `current`. One pointer; the last
  one configured wins.
- Copying, summarising, or paraphrasing `AGENTS.md` into user scope.
- Watching for a workspace that has been moved or deleted and repairing the pointer on its own.
- Installing anything for assistants choom does not support, or for editor and IDE integrations.
- Project-scope or repository-scope assistant files. `AGENTS.md` and `CLAUDE.md` at the workspace
  root already cover that surface and are unchanged.
- Teaching the assistant anything about choom's behaviour beyond where to find its instructions.
- Prompting, confirming, or installing anything from a command-line invocation. The launch offer is
  the interactive interface's alone.
- Re-asking a user who declined, on any trigger — a new assistant, a new machine, a later version.
  The set command is the only way back in.
- A general settings surface for suppressed prompts. This records one decision, not a framework.
