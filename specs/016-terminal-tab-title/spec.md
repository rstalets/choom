# Feature Specification: The Terminal Tab Names the Workspace

**Feature Branch**: `016-terminal-tab-title`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "issue #47. You are 016"

**Source**: GitHub issue #47 "[Feature]: Set terminal tab title to reflect active choom workspace",
which asks that a long-lived choom session identify itself — and the workspace it has open — in the
terminal's tab strip, and that it hand the title back when it exits.

**Scope settled in refinement**: the title reflects the **workspace only** and is set **once, at
startup**. Updating it as the active collection, month, or filter changes is out of scope and is
recorded as such below.

---

## Overview

choom is a tool you leave open. It sits in a terminal tab for the whole working day, next to a shell,
a log tail, an editor, and three other shells. Every one of those tabs is labelled by whatever the
terminal decided to call it — usually the shell name, sometimes the working directory. The choom tab
is labelled the same way, so from the tab strip it is indistinguishable from the others. Finding it
means clicking through tabs until the list screen appears.

The fix is small and old: terminals let the running program name the tab. Editors, pagers, and
monitoring tools have done it for decades. choom should do it too, saying the one thing that
identifies the tab — that this is choom, and which workspace is open in it.

Three properties define the feature:

1. **It identifies, it does not narrate.** The title is the workspace, fixed for the life of the
   session. A title that changes as the user moves between Notes and Tasks is not a label, it is a
   flicker in the corner of the eye, and it destroys the thing a tab strip is good at — being
   scannable without being watched.
2. **It gives the terminal back.** A tool that renames your tab and then leaves it renamed after it
   quits has taken something. Every exit choom can observe restores the title, including the ones
   that are not clean.
3. **It is invisible when it should be.** No configuration, no flag, nothing emitted when output is
   not a terminal, and nothing emitted on a console that would render it as literal garbage.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find the choom tab without hunting for it (Priority: P1)

Someone has seven terminal tabs open. One of them is choom, opened this morning against their
`work-notes` workspace. A meeting is starting and they need to take notes. They glance at the tab
strip, see the tab that names choom and the workspace, and click it directly.

**Why this priority**: This is the whole problem the issue reports. Without it there is no feature;
with it alone the feature already delivers its value.

**Independent Test**: Launch choom in a terminal that shows tab or window titles, and confirm the tab
is labelled with choom and the open workspace's name without any configuration being changed first.

**Acceptance Scenarios**:

1. **Given** a workspace whose root directory is named `work-notes`, **When** choom is launched in it,
   **Then** the terminal tab hosting choom is titled `choom — work-notes`.
2. **Given** choom is running with the title set, **When** the user switches from Tasks to Notes,
   changes the month in the scope pane, opens a filter, opens a record, edits it, and saves it,
   **Then** the tab title is unchanged throughout.
3. **Given** two workspaces, `work-notes` and `personal`, each with choom running in its own tab,
   **When** the user looks at the tab strip, **Then** each tab is titled for its own workspace and
   neither has affected the other.
4. **Given** a workspace directory whose name contains spaces and non-ASCII characters, **When** choom
   is launched in it, **Then** the tab title shows that name as written, with no substitution or
   mangling.

---

### User Story 2 - Get your terminal back when choom exits (Priority: P2)

The same user finishes with choom and quits it. The tab returns to being an ordinary shell tab,
labelled the way it was before choom started — not stuck reading `choom — work-notes` over a shell
prompt for the rest of the day. The same is true when they interrupt choom instead of quitting it, and
when choom falls over on its own.

**Why this priority**: Hygiene rather than headline value, but the issue names it explicitly and it is
what separates a good citizen from a tool that vandalises the terminal. It ships with US1 — the two are
the same lifecycle — but it is testable on its own.

**Independent Test**: With the title set, leave choom by each exit route in turn and confirm the tab no
longer reads choom's title afterwards.

**Acceptance Scenarios**:

1. **Given** choom is running with the title set, **When** the user presses `ctrl+q` with nothing
   unsaved, **Then** choom exits immediately and the tab no longer shows choom's title.
2. **Given** choom is running with a dirty editor open, **When** the user presses `ctrl+q`, is asked to
   confirm, and confirms the discard, **Then** choom exits and the tab no longer shows choom's title.
3. **Given** choom is running with a dirty editor open, **When** the user presses `ctrl+q` and then
   cancels the confirmation, **Then** choom stays running and the tab still shows choom's title.
4. **Given** choom is running with the title set, **When** the session is interrupted with `ctrl+c`,
   **Then** choom leaves and the tab no longer shows choom's title.
5. **Given** choom is running with the title set, **When** an unhandled error terminates the
   application, **Then** the error is reported as it is today and the tab no longer shows choom's
   title.
6. **Given** choom is running in a terminal that cannot restore a previously saved title, **When**
   choom exits by any route above, **Then** the tab does not show choom's title — it shows whatever the
   terminal or shell puts there when no program has claimed it.

---

### User Story 3 - Windows Terminal gets the same signal, older consoles are unharmed (Priority: P3)

A corporate user on a managed Windows machine runs choom in Windows Terminal alongside their other
tabs and gets exactly the behaviour above. A colleague who launches it from a legacy console window
sees no change at all — no renamed window, and crucially no stray characters printed into the console.

**Why this priority**: Windows is a first-class target, so this is not optional, but it is the same
behaviour as US1 verified on a second platform rather than a distinct journey. Its own risk is the
failure mode, not the success case.

**Independent Test**: Run choom in Windows Terminal and confirm the tab is renamed and restored; run it
in a legacy console host and confirm the session looks exactly as it does today.

**Acceptance Scenarios**:

1. **Given** Windows Terminal, **When** choom is launched in a workspace, **Then** the tab is titled for
   that workspace, and on exit it is no longer.
2. **Given** a console that does not interpret terminal escape sequences, **When** choom is launched and
   later exits, **Then** no title text and no escape-sequence characters appear anywhere in the console
   output, and the session is otherwise identical to today's.
3. **Given** any Windows console, **When** choom prepares the console at startup, **Then** it requires no
   administrator rights, no network access, and no third-party package.

---

### User Story 4 - Nothing leaks into piped or scripted output (Priority: P3)

An AI assistant runs `choom task list --json` and parses the result. A user runs `choom meeting list |
grep standup`. Neither ever sees a title escape sequence in the bytes they read, whether or not the
command happens to be attached to a terminal.

**Why this priority**: A single stray escape sequence turns a working automation into a corrupt parse,
and the failure is silent from the assistant's side. Low priority only because it is a guarantee to
preserve rather than a capability to add.

**Independent Test**: Capture stdout and stderr for every `choom` subcommand, both piped and on a
terminal, and confirm no title sequence appears in either stream.

**Acceptance Scenarios**:

1. **Given** any `choom` subcommand, **When** it is run with stdout redirected to a file or a pipe,
   **Then** neither its stdout nor its stderr contains a terminal-title sequence.
2. **Given** any `choom` subcommand, **When** it is run attached to a terminal, **Then** neither stream
   contains a terminal-title sequence and the terminal's tab title is unchanged before, during, and
   after the command.
3. **Given** choom is asked to open the interface with stdout redirected, **When** it refuses as it does
   today, **Then** nothing but the existing error is written and no title sequence is emitted.

---

### Edge Cases

- **Workspace at a filesystem or drive root.** The root has no final path segment to use as a name. The
  title falls back to the root's path text (`/`, `C:\`) rather than showing an empty name.
- **A very long workspace directory name.** The title is capped so it cannot crowd out neighbouring tabs
  or overflow the terminal's own title handling; the name is truncated with a single ellipsis and the
  beginning of the name stays readable.
- **A workspace directory name containing control characters.** A directory name may legally contain a
  newline or an escape character on POSIX filesystems. Left unfiltered, such a name would let the
  directory itself terminate choom's title and issue arbitrary commands to the terminal. Control
  characters are removed before the title is composed.
- **A name the console cannot encode.** On a console whose character encoding cannot represent part of
  the title, the attempt fails harmlessly: no title is set, no error is shown, and choom continues.
- **Cancelling a quit.** Confirming-then-cancelling `ctrl+q` leaves choom running; the title must still
  be choom's, not already restored.
- **Running inside a terminal multiplexer.** choom sets the title the same way it always does. Whether
  the multiplexer forwards it to the outer terminal's tab strip is that multiplexer's own setting, not
  something choom detects or overrides.
- **Running over SSH.** The title is set by the same mechanism and applies to the local terminal's tab,
  since the escape sequence travels the connection like any other output.
- **The process is killed outright.** A `SIGKILL`, a closed terminal window, or a lost machine leaves the
  title as choom set it, because no code of choom's runs. This is accepted; see FR-019.
- **A terminal that ignores the title sequence.** Nothing happens, visibly or otherwise. The escape
  sequence is consumed and discarded, exactly as it is by any program that sets a title today.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Composing the title

- **FR-001**: choom MUST compose a terminal title that identifies the running session and the workspace
  it has open, of the form `choom — <workspace name>`.
- **FR-002**: The workspace name MUST be the final path segment of the workspace root directory. When
  the root has no final segment (a filesystem or drive root), the name MUST fall back to the root's
  path as text; when that too is empty, the title MUST be `choom` alone.
- **FR-003**: Composing the title MUST be a pure function of the workspace, callable and testable with
  no terminal, no TTY, and no event loop, and MUST live in `choom.core`.
- **FR-004**: The composed title MUST contain no control characters. Any control character present in
  the workspace name — including escape, bell, carriage return, line feed, and tab — MUST be removed
  before the title is composed, so that no directory name can terminate the title or issue instructions
  to the terminal.
- **FR-005**: The composed title MUST be at most 64 characters. When the workspace name would push it
  past that, the name MUST be truncated and marked with a single ellipsis character, leaving the
  `choom` prefix and the start of the name intact.
- **FR-006**: Workspace names containing spaces and non-ASCII characters MUST be carried through
  verbatim, subject only to FR-004 and FR-005. No transliteration, no character substitution.

#### Setting and restoring it

- **FR-007**: Writing the title to the terminal, restoring it, and any preparation the terminal needs
  MUST live in the interface layer, not in `choom.core`. Core MUST contain no escape sequences, no
  terminal writes, and no TTY checks for this feature.
- **FR-008**: On starting the interface, choom MUST set the terminal title to the composed title,
  exactly once.
- **FR-009**: choom MUST NOT change the title again for the life of the session. Switching collection,
  changing month or scope, filtering, opening, editing, saving, creating, or deleting a record MUST
  leave the title as set at startup.
- **FR-010**: On exit, choom MUST leave the terminal no longer showing choom's title. Where the terminal
  supports saving and restoring a title, the title in effect before choom started MUST be restored;
  where it does not, choom MUST clear the title it set so the terminal or shell resumes control of it.
- **FR-011**: Restoration MUST run on every exit path choom can observe: quitting with `ctrl+q` when
  nothing would be lost; quitting with `ctrl+q` after confirming a discard; any other in-app quit; an
  interrupt (`ctrl+c`); and an unhandled error that terminates the application.
- **FR-012**: A quit that is raised and then cancelled MUST NOT restore the title. The title is restored
  when choom actually leaves, not when leaving is proposed.
- **FR-013**: Restoring the title MUST NOT delay exit, MUST NOT add a keystroke, and MUST NOT introduce
  any prompt or confirmation. `ctrl+q` stays immediate.
- **FR-014**: Failing to set, prepare, or restore the title MUST NOT raise to the user, MUST NOT change
  choom's exit code, MUST NOT write to stderr, and MUST NOT prevent choom from starting or exiting.

#### Where it must stay silent

- **FR-015**: choom MUST NOT emit a title sequence when stdout is not a terminal.
- **FR-016**: No `choom` subcommand invocation MUST ever emit a title sequence, on stdout or on stderr,
  attached to a terminal or not. Only the interactive interface sets a title. See "Interface parity"
  below.
- **FR-017**: The behaviour MUST NOT be configurable. It adds no command-line flag, no workspace
  setting, and no environment variable. The only conditions on it are FR-015 and the platform checks in
  FR-021 through FR-023.
- **FR-018**: The feature MUST add no new exit code, no new or changed `--json` key, and no change to
  any existing command's stdout or stderr.

#### Limits

- **FR-019**: When choom's process is ended without any of its own code running — a kill signal, a
  closed terminal window, a lost machine — the title is left as choom set it. choom MUST NOT persist
  state anywhere, in the workspace or outside it, to work around this.
- **FR-020**: choom MUST NOT detect or special-case a terminal multiplexer. Whether a multiplexer
  forwards the title outward is that multiplexer's configuration and is explicitly not choom's
  responsibility.

#### Windows

- **FR-021**: On Windows, choom MUST put the console into the mode that interprets terminal escape
  sequences, once, at startup, before setting the title. Doing so MUST require no administrator rights,
  no network access, and no new third-party dependency.
- **FR-022**: When that mode cannot be enabled — a legacy console host, a redirected handle, any other
  failure — choom MUST NOT emit the title sequence at all. The user MUST NOT see literal escape-sequence
  characters in the console, at startup, at exit, or anywhere between.
- **FR-023**: No console-mode change MUST be attempted on macOS or Linux.

#### Data safety

- **FR-024**: The feature MUST read nothing but the workspace root path and MUST write nothing to the
  workspace. No file is created, modified, moved, or read for it.

### Interface parity (constitution Principle II)

The CLI's answer to this feature is an explicit **inherently-interactive carve-out**, not an equivalent
command. Stated plainly: **the CLI does not set a terminal title, and must not.**

The reasoning, which is the part that matters:

- The behaviour being added is *"this tab is occupied by a running choom session against this
  workspace"*. That statement is only true while a session occupies the tab. A CLI invocation occupies
  it for a few hundred milliseconds and then gives it back to the shell — there is no interval during
  which a tab labelled for that command would be either accurate or useful.
- Implementing it in the CLI anyway leaves two outcomes, both bad. Restore on exit, and the title
  flickers for a fraction of a second — noise, not signal. Do not restore, and every `choom task add`
  permanently relabels the user's shell tab with a claim that stopped being true the moment the command
  returned.
- The CLI's stdout is a data stream read by AI assistants and by pipelines. Writing escape bytes into it
  risks corrupting a parse for zero user benefit, which is the failure Principle II's non-TTY rule exists
  to prevent. FR-016 states the prohibition; US4 tests it.

What the two interfaces *do* share is the part that carries behaviour: FR-003 puts title composition in
`choom.core`, where it is one pure function testable without a terminal. There is no logic in the TUI
for the CLI to be missing — only an escape sequence written to a device the CLI does not own.

This carve-out is narrow and does not extend to the underlying question "which workspace is active?".
If that question ever needs a CLI answer, it is a separate feature about reporting the workspace, not
about painting a tab.

### Layering (constitution Principle I)

The boundary runs between the *text* and the *bytes*:

| Concern | Side | Why |
|---|---|---|
| Deriving the workspace name from the workspace | `choom.core` | Logic over a workspace; no terminal involved. |
| Stripping control characters, truncating, assembling `choom — <name>` | `choom.core` | Pure string logic with rules worth unit-testing on their own. |
| Wrapping the text in a terminal escape sequence | interface | I/O formatting, which core may not contain. |
| Deciding whether stdout is a terminal | interface | A TTY check is exactly the terminal dependency core must not have. |
| Preparing the Windows console | interface | Platform I/O setup. |
| Writing at startup, restoring at exit | interface | Lifecycle of the running front-end. |

Core's contribution is one function taking a workspace and returning a string, with no import of
anything terminal-shaped and no knowledge that a terminal is the destination.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With choom running in one of five or more open tabs, a user identifies the choom tab, and
  the workspace open in it, from the tab strip alone — without switching tabs.
- **SC-002**: On every exit path choom can observe (quit, quit-after-discard-confirmation, interrupt,
  unhandled error), the tab no longer shows choom's title, in 100% of trials on each terminal choom is
  verified on before release.
- **SC-003**: A user who has read no documentation gets the behaviour on first launch, and there is no
  setting for them to find, change, or get wrong.
- **SC-004**: Startup and exit remain within the times a user experiences today — the title work adds no
  perceptible delay to either, and no pause between pressing `ctrl+q` and the shell prompt returning.
- **SC-005**: Across every `choom` subcommand, run both piped and attached to a terminal, zero bytes of
  title-setting output appear on stdout or stderr.
- **SC-006**: A workspace directory named with non-ASCII characters produces a readable tab title; a
  workspace directory whose name contains control characters produces a readable tab title and no
  observable change in terminal behaviour.
- **SC-007**: On a Windows console that does not interpret escape sequences, zero literal
  escape-sequence characters appear in the session's output.
- **SC-008**: Navigating the entire interface for a full session produces exactly one title change at
  startup and one at exit — no others.

---

## Assumptions

- **The workspace's name is its directory name.** A workspace has no separate display name today, and
  giving it one is a different feature. The final path segment of the root is what identifies it, and it
  is what the user already recognises.
- **No setting, by design.** Per the simplicity principle, a behaviour that could be a sensible default
  is a sensible default. Setting a tab title is what every long-running terminal program does, it is
  reversible on exit, and it changes nothing about choom's own display — so it is always on when stdout
  is a terminal, and there is nothing to configure.
- **The interface already requires an escape-sequence-capable terminal.** choom's interactive screen is
  drawn entirely with escape sequences and already refuses to open when stdout is not a terminal. A
  terminal that would render a title sequence as visible garbage could not draw the interface at all, so
  the stdout-is-a-terminal check plus the Windows console-mode check in FR-021/FR-022 are the only gates
  needed; no `TERM` sniffing is assumed.
- **Restoring the exact previous title depends on the terminal.** There is no reliable, universally safe
  way to ask a terminal what its title currently is. Terminals that support saving and restoring a title
  give an exact restore; the rest get the clear-and-hand-back fallback in FR-010, which is what the user
  perceives as "back to normal" either way.
- **Windows Terminal is the Windows target.** Legacy console windows have no tab strip, so there is
  nothing there to identify; FR-022 exists to guarantee they are unharmed, not to serve them.
- **Verification on the target terminals is manual**, as it is for every interface change — Windows
  Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux.
- **`choom — <name>` is the wording**, with an em dash, matching the issue. The separator carries no
  meaning beyond legibility, and FR-014 covers the case where a console cannot encode it.

---

## Out of Scope

- **Reflecting anything other than the workspace in the title** — the active collection, the selected
  month, the open record, the filter term, task counts, or unsaved state. Settled in refinement: the
  title's job is to identify a tab, and a value that churns as the user navigates is noise in a tab
  strip. It can be added later on top of this without redoing any of it.
- **Updating the title at any point after startup**, for any reason, including a workspace being renamed
  underneath a running session.
- **A CLI equivalent.** See "Interface parity" above — an explicit carve-out, not an omission.
- **Any way to turn the behaviour off**: no flag, no workspace setting, no environment variable.
- **A user-defined title format or template.**
- **A display name for a workspace**, stored in its config or anywhere else.
- **Anything about the icon, badge, colour, or other tab decoration** a terminal may support.
- **Detecting or configuring terminal multiplexers**, including tmux's own title-forwarding setting.
- **Restoring the title after choom is killed outright**, which no in-process code can do.
- **Showing the workspace inside the interface** — the bottom-bar workspace indicator raised in issue
  #32 is the same question answered from a different side, and stays a separate piece of work.

---

## Dependencies

- Depends on the existing workspace resolution that already runs before the interface opens — the
  interface cannot start without a workspace, so a workspace root is always available when the title is
  composed.
- Depends on the existing refusal to open the interface when stdout is not a terminal. That check
  already prevents the interactive path from running in a pipe; FR-015 restates the guard at the point
  of emission so the guarantee survives if that check ever moves.
- Depends on the application's existing startup and shutdown lifecycle, including the discard
  confirmation added for issue #64, which FR-011 and FR-012 hook into rather than modify.
- Adds no third-party dependency. The escape sequence is plain output and the Windows console-mode call
  is a standard-library facility.
- Related to issue #32, which puts the workspace path in the bottom bar. Distinct surface, distinct
  work; neither blocks the other.
