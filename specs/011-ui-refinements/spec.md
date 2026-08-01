# Feature Specification: UI Refinements

**Feature Branch**: `011-ui-refinements`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Issue 32"

**Source**: GitHub issue #32 "[Feature]: UI Improvements (More)" (milestone v0.0.3), which collects five
independent rough edges: the cursor lands at the top of the editor instead of where the user is about to
type; the running workspace is invisible from inside the tool; the list rows are an unlabelled string of
values that shift sideways when a field is empty; records cannot be deleted without opening a file
manager; and confirmation dialogs make the user aim at a button instead of pressing a key.

**Builds on**: Features `004-viewing-editing` (the preview → edit state machine and the discard
confirmation), `005-ui-layout-refresh` (the collection bar, the scope pane, the three-pane list screen,
and the status bar with its version indicator), and `003-tasks`/`009-inline-task-capture` (the task line
format, task bodies, and the mirror checkboxes a task can have in a document). It adds no new record
type and no new stored state.

**Sequenced after**: `010-read-on-load` (issue #51), which lands first and retires the session-lifetime
snapshot. This spec is written for the codebase that exists once it has landed — see Dependencies and
Relationships for what that changes here, and for the gate on planning.

---

## Overview

Four of these five items are presentation: where a cursor starts, what the top bar says, how a row is
laid out, how a dialog asks a question. The fifth — deleting a record — is the one genuine capability
gap, and it is the reason the others travel together: a delete needs a confirmation, and today's
confirmation is exactly the dialog the user is asking to replace.

Taken together they close the loop on the everyday motions:

1. **Editing starts where you type.** Entering edit mode puts the cursor on a fresh line below the
   existing content, separated by one blank line, so the common case — appending a thought to something
   already written — costs no keystrokes to reach.
2. **The tool says which workspace it is showing.** The path sits in the top bar, snapped to the
   top-right corner, so telling an assistant or a terminal where the notes live is a matter of reading it
   rather than remembering it.
3. **The list is a table, not a sentence.** Four labelled columns hold their position whether or not a
   record has a type or tags, so the eye finds the title in the same place on every row.
4. **Confirmations are a line, not a form.** One question, two labelled keys — `Esc` always stops,
   `Enter` always proceeds — centred on screen, with no highlight to move and no button to hit.
5. **Records can be deleted from either front-end.** In the terminal interface, `ctrl+d` on the
   highlighted row, confirmed with the dialog above. On the command line, a peer `delete` command per
   record type that takes an explicit flag and never prompts, so an assistant sharing the workspace can
   clean up after itself.

## User Scenarios & Testing *(mandatory)*

**Sequencing note**: the stories below are in build order, and one of the dependencies is binding rather
than a preference. Story 1 (the confirmation) MUST land before Story 2 (deleting from the list) is wired
up. Deletion is the one new confirmation point this feature adds, and FR-026 requires every confirmation
in the product to be the same one — so building the delete against the confirmation that exists today
would mean writing the confirmation twice and shipping the old style in the interval. Stories 3 and 4
follow Story 2 because they extend the same deletion behaviour. Stories 5, 6, and 7 touch none of this
and may be built in any order, before or after the rest.

### User Story 1 - Confirmations are a line with two named keys (Priority: P1)

Any time choom needs a yes or no — discarding unsaved edits, deleting a record — it shows a slim,
centred, single-question bar with two options: `Esc` to stop and `Enter` to proceed. The wording names
the outcome of each key, not an abstract "OK/Cancel". There is nothing to highlight and nothing to move.

**Why this priority**: Everything the delete stories confirm against is built here. Deletion is this
feature's only new confirmation point, and there is exactly one confirmation in the product (FR-026), so
building delete first would mean building its dialog twice and shipping the button-and-highlight style in
between. It also delivers on its own: with no delete in the tool at all, the discard confirmation the
editor already raises becomes slimmer, centred, and resolvable with one keypress.

**Independent Test**: Trigger the discard confirmation by editing a document and leaving without saving,
and confirm the dialog is a slim centred bar, that `Esc` returns to the editor with the edits intact, and
that `Enter` leaves without saving. Repeat in a narrow and a wide terminal.

**Acceptance Scenarios**:

1. **Given** unsaved changes in the editor, **When** the user tries to leave, **Then** a slim centred bar
   asks the question and offers exactly two options, each labelled with its key and the outcome that key
   produces — for example `(Esc) Continue Editing` and `(Enter) Exit Without Saving`.
2. **Given** a confirmation is on screen, **When** the user presses `Esc`, **Then** the action that raised
   it is abandoned and the user is returned to where they were with nothing changed.
3. **Given** a confirmation is on screen, **When** the user presses `Enter`, **Then** the action the user
   originally asked for goes ahead.
4. **Given** a confirmation is on screen, **When** the user presses any other key, **Then** the
   confirmation stays up and nothing happens — no key falls through to the screen underneath.
5. **Given** the confirmation was raised by activity in one pane of a multi-pane screen, **When** it
   appears, **Then** it is centred on the whole screen rather than positioned over the originating pane.
6. **Given** the terminal is resized while a confirmation is on screen, **When** the resize completes,
   **Then** the confirmation is still centred and its full text is still readable.

---

### User Story 2 - Delete a record without leaving the tool (Priority: P2)

A user has a meeting note created by mistake, a duplicate note, or a task that is no longer relevant.
They move the highlight onto it in the list, press `ctrl+d`, read a one-line confirmation naming what
will be deleted, and press `Enter`. The row disappears, the highlight lands on the next record, and the
file (or the task's lines) is gone from the workspace. Pressing `Esc` at the confirmation leaves
everything exactly as it was.

**Why this priority**: It is the only item in this feature that is a missing capability rather than a
rough edge, and it is the highest-value behaviour here — today the only way to remove a record is to
leave the tool, find the file, and delete it by hand, and for a task, to hand-edit `tasks.md` and hope
the surrounding lines survive. It sits second only because the confirmation it raises is the one built in
Story 1; everything after it is presentation.

**Independent Test**: Create a meeting, a note, and a task in a scratch workspace. Delete each from the
list with `ctrl+d` → `Enter` and confirm the record is gone from the list, gone from disk (or gone from
`tasks.md`), and that the records around it are untouched. Repeat with `Esc` and confirm nothing
changes.

**Acceptance Scenarios**:

1. **Given** the Meetings collection with a meeting highlighted, **When** the user presses `ctrl+d` and
   confirms, **Then** the meeting's markdown file is removed from the workspace, the row disappears from
   the list, and the preview pane shows the record the highlight moved to.
2. **Given** the Notes collection with a note highlighted, **When** the user presses `ctrl+d` and
   confirms, **Then** the note's markdown file is removed and the list no longer offers it.
3. **Given** the Tasks collection with a task highlighted that has a multi-line body, **When** the user
   presses `ctrl+d` and confirms, **Then** the task's line and its whole body are removed from the tasks
   file, and every other task in that file — including the tasks immediately before and after it — is
   unchanged, in the same order, with its own body intact.
4. **Given** a confirmation is on screen for a highlighted record, **When** the user presses `Esc`,
   **Then** the record still exists, the list is unchanged, and the highlight is where it was.
5. **Given** the last record in the list is highlighted, **When** the user deletes it, **Then** the
   highlight moves to the record above it rather than to an empty selection.
6. **Given** the only record in the current view is highlighted, **When** the user deletes it, **Then**
   the list shows the same empty-state message it would show for an empty view.
7. **Given** the highlight is on a row and the underlying file was already deleted outside the tool,
   **When** the user confirms a delete, **Then** the tool reports that the record no longer exists in the
   status bar and refreshes the list, rather than failing silently or crashing.

---

### User Story 3 - Delete a record from the command line (Priority: P3)

An assistant working in the same workspace created a note in the wrong place, or the user wants to script
a cleanup. Each record type has a `delete` command that takes the record's id and an explicit flag, does
the deletion without asking anything, prints nothing to stdout on success, and exits 0.

**Why this priority**: Principle II makes this a peer of Story 2, not an extra: any behaviour available in
one front-end must be available in the other. It follows the interactive path only because that is the
one a human reaches for first, and because the command line has no equivalent of "the row I am looking
at" — it needs the id, which the interactive path does not. It has no dependency on Story 1: the command
line never confirms, it takes a flag.

**Independent Test**: Create each record type, capture its id from the matching `list --json` output,
delete it by id with the flag, and confirm exit code 0 and that the record is gone. Run the same command
without the flag and confirm it exits with a usage error and deletes nothing.

**Acceptance Scenarios**:

1. **Given** a meeting exists, **When** `choom meeting delete <id> --force` runs, **Then** the file is
   removed, nothing is written to stdout, and the exit code is 0.
2. **Given** a note exists, **When** `choom note delete <id> --force` runs, **Then** the file is removed
   and the exit code is 0.
3. **Given** a task exists, **When** `choom task delete <id> --force` runs, **Then** the task's line and
   body are removed from the tasks file and the exit code is 0.
4. **Given** any record exists, **When** the delete command runs without the explicit flag, **Then**
   nothing is deleted, the command exits with the usage-error code, the reason is on stderr, and the
   command has not waited for input at any point.
5. **Given** no record carries the given id, **When** the delete command runs with the flag, **Then**
   nothing is deleted, the command exits with the not-found code, and stderr names the id that did not
   resolve.
6. **Given** the delete command is run with stdin closed and stdout redirected to a file, **When** it
   completes, **Then** it never blocks and the file contains no prompt text or terminal escape sequences.

---

### User Story 4 - A deleted task's mirrors stay in the user's words (Priority: P4)

A task was captured from inside a note, so the note carries a checkbox pointing at it. The user deletes
the task. The note keeps the line the user typed, exactly as typed; the link is now dead, and choom
reports it as dead the next time it looks — the same outcome a mirror already has when its task cannot be
found.

**Why this priority**: It is a correctness constraint on Stories 2 and 3 rather than a separate gesture,
so it cannot ship before them. It is called out as its own story because it is the one place where
deleting can damage a file that the user did not ask to touch, and Principle IV makes that the
non-negotiable part of the feature.

**Independent Test**: Capture a task from inside a note so the note holds a mirror checkbox, delete the
task, then open the note and confirm the mirror line is byte-for-byte what it was and that the tool
reports the link as dead rather than repairing or removing it.

**Acceptance Scenarios**:

1. **Given** a note contains a mirror checkbox for a task, **When** that task is deleted, **Then** the
   note's line is left exactly as it was — same text, same position, same surrounding lines.
2. **Given** a note contains a mirror checkbox for a deleted task, **When** the user opens that note,
   **Then** the tool surfaces a dead-link warning for that mirror and no other change is made to the
   file.
3. **Given** a note contains a mirror checkbox for a deleted task, **When** the user ticks or unticks
   that checkbox, **Then** the note saves with the user's change and the dead link is reported, rather
   than the save failing.
4. **Given** several documents mirror the same task, **When** the task is deleted, **Then** every one of
   those documents is left unmodified.

---

### User Story 5 - The list reads as four labelled columns (Priority: P5)

The user looks at any collection and sees a header row naming four columns — date, type, title, tags —
with every row's values under the matching header. A record with no type leaves an empty cell; the title
underneath stays in the title column instead of sliding left into the gap.

**Why this priority**: It is a legibility fix for the surface the user spends the most time on, and it is
what makes an empty field readable as "no type" rather than as a mystery. It ranks below the
confirmation work only because nothing is unusable today — the information is all present, just hard to
parse.

**Independent Test**: Populate a workspace with records that have every combination of type present or
absent and tags present or absent, then confirm in each collection that the four headers are visible and
that every value sits under its own header regardless of which neighbouring fields are empty.

**Acceptance Scenarios**:

1. **Given** any collection is shown, **When** the list is drawn, **Then** a header row above the rows
   names the four columns, and it stays visible while the user scrolls the list.
2. **Given** a record with a type and a record without one, **When** both are listed, **Then** their
   titles begin at the same column position and the typeless record shows an empty type cell.
3. **Given** a record whose title is wider than the title column, **When** it is listed, **Then** the
   title is truncated with a visible ellipsis and the columns after it keep their positions — the row
   never wraps to a second line.
4. **Given** the Tasks collection, **When** tasks are listed, **Then** the same four columns carry the
   task's date, type, text, and tags, and the task's done state is still distinguishable at a glance.
5. **Given** the terminal is narrow enough that four columns do not fit, **When** the list is drawn,
   **Then** the date and title columns remain and the lower-priority columns are dropped along with
   their headers, rather than any column being squeezed to unreadable width.

---

### User Story 6 - The top bar names the workspace (Priority: P6)

The user glances at the top-right corner of the screen and reads the path of the workspace they are in,
so they can tell an assistant, another terminal, or a colleague where the notes are without leaving the
tool.

**Why this priority**: A small, self-contained addition to an existing bar. Real value — the question
"which workspace is this?" has no answer inside the tool today — but the cost of not having it is a
lookup, not a broken flow.

**Independent Test**: Launch the tool against two different workspaces in turn and confirm the top bar
names each one's path at the right-hand edge, including one workspace whose path contains a space and a
non-ASCII character, and confirm the bottom bar is unchanged.

**Acceptance Scenarios**:

1. **Given** the tool is launched in a workspace, **When** the top bar is shown, **Then** it names the
   workspace's path, aligned to the right-hand edge of the bar.
2. **Given** the terminal is resized, **When** the redraw completes, **Then** the path is still flush with
   the right-hand edge — it is anchored to the corner, not placed at a fixed offset.
3. **Given** the workspace lives under the user's home directory, **When** the path is shown, **Then** it
   is shown in its shortened home form rather than spelled out in full.
4. **Given** a workspace path too long for the space left over in the top bar, **When** the path is
   shown, **Then** it is shortened so that the deepest part of the path — the part that identifies the
   workspace — stays readable, and the collection names keep their position and full text.
5. **Given** a workspace path containing spaces and non-ASCII characters, **When** it is shown, **Then**
   it renders correctly and the bar's layout is unaffected.
6. **Given** the workspace path is displayed, **When** the bottom bar is drawn, **Then** its help text and
   version indicator occupy exactly the space they did before this feature — no bottom-bar room is spent
   on the workspace.

---

### User Story 7 - The cursor starts where the next words go (Priority: P7)

The user opens an existing note or task body to add something. The cursor is already on an empty line
below everything that is there, separated from it by one blank line. They type. They never press
`ctrl+End`, never hold a movement key, and never accidentally type into the middle of yesterday's
paragraph.

**Why this priority**: The smallest change here and the one with the narrowest blast radius, but it fires
on every single edit. It ranks last because the current behaviour costs a keystroke rather than
preventing anything.

**Independent Test**: Open an existing multi-line document for editing and confirm the cursor is on an
empty line one blank line below the last content, then type a character and confirm it lands there.

**Acceptance Scenarios**:

1. **Given** a document with existing content, **When** the user enters edit mode, **Then** the cursor is
   positioned on an empty line separated from the last line of content by exactly one blank line.
2. **Given** a document whose content already ends with one or more blank lines, **When** the user enters
   edit mode, **Then** the cursor is positioned so that exactly one blank line separates it from the last
   non-empty line, rather than stacking further blank lines below the existing ones.
3. **Given** an empty document, **When** the user enters edit mode, **Then** the cursor is on the first
   line and no blank lines are inserted above it.
4. **Given** the user enters edit mode and immediately leaves without typing anything, **When** they
   leave, **Then** no confirmation is raised and the file on disk is unchanged — positioning the cursor is
   not an edit.
5. **Given** a task body is opened for editing, **When** the editor appears, **Then** the cursor is
   positioned by the same rule as for a document.

---

### Edge Cases

- **Deleting while a filter is active**: the record is deleted and the filtered list refreshes with the
  filter still applied; the highlight lands on the next record that still matches.
- **A background re-read lands while a confirmation is on screen**: the confirmation stays up, keeps its
  wording, and still refers to the record it named. Confirming deletes that record; declining leaves the
  refreshed list as it is.
- **Deleting the record whose links pane is open**: the links pane closes with the record and does not
  keep showing a deleted record's links.
- **A document that is linked to by other documents**: it deletes. Inbound links become dead and are
  reported as dead by the existing link check; deletion does not rewrite, repair, or remove anyone else's
  link text.
- **A task whose body is malformed or whose surrounding lines are hand-edited**: only the identified
  task's line and body span are removed; a parse warning elsewhere in the file does not block the delete
  and does not cause any other line to be dropped.
- **Two records carrying the same id**: the delete refuses and names the ambiguity rather than guessing
  which one to remove — the same resolution the tool already applies when an id is not unique.
- **`ctrl+d` pressed with no record highlighted** (an empty list, or the highlight on the empty-state
  message): nothing happens and no confirmation appears.
- **`ctrl+d` pressed while the command bar or filter is open**: the keystroke belongs to the bar; no
  confirmation appears.
- **A confirmation on a terminal too narrow for its question**: the question wraps or shortens, but both
  key labels stay visible — the user is never shown a question with no way to read the options.
- **The top bar is too narrow to hold the collections and the whole path**: the path is what gives way,
  shortening from the left; the collection names never truncate, since they are what the user navigates
  by. At the extreme, the path shortens to its final component and no further — it never disappears
  entirely, because a path that vanishes on a narrow terminal is worse than one that is elided.
- **A record with no tags and no type**: two empty cells, and the date and title stay in their columns.
- **Entering edit mode on a file that is not valid markdown or whose frontmatter does not parse**: the
  editor still opens on the raw text and the cursor rule still applies.

## Requirements *(mandatory)*

### Functional Requirements

**Deleting records — shared behaviour**

- **FR-001**: The system MUST support deleting a meeting, a note, or a task, and MUST offer that
  capability in both the terminal interface and on the command line.
- **FR-002**: Deleting a meeting or a note MUST remove that record's markdown file from the workspace.
- **FR-003**: Deleting a task MUST remove that task's line and its whole body span from the tasks file,
  and MUST leave every other line of that file — text, order, and indentation — unchanged.
- **FR-004**: Deletion MUST NOT create a trash area, an undo history, or a tombstone record. Once
  confirmed, the record is gone.
- **FR-005**: Deletion MUST NOT modify any document other than the one being deleted. In particular, a
  deleted task's mirror checkboxes in other documents MUST be left exactly as the user wrote them.
- **FR-006**: After a task is deleted, its mirrors MUST resolve as dead links using the existing dead
  outcome, and MUST be reported as such when the mirroring document is opened or saved.
- **FR-007**: A delete request naming an id that no record carries MUST fail without deleting anything
  and MUST name the id that did not resolve.
- **FR-008**: A delete request naming an id carried by more than one record MUST fail without deleting
  anything and MUST name the ambiguity.

**Deleting records — terminal interface**

- **FR-009**: Pressing `ctrl+d` with a record highlighted in the list MUST raise a confirmation naming
  the record that will be deleted. That confirmation MUST be the one specified in FR-021–FR-026, not a
  second dialog of its own.
- **FR-010**: Confirming MUST delete the record; declining MUST leave the record, the list, and the
  highlight exactly as they were. The confirmation MUST act on the record it named when it was raised,
  so a list re-read that happens while it is on screen cannot redirect the delete onto a different
  record.
- **FR-011**: After a successful delete, the list MUST refresh, the deleted row MUST be gone, and the
  highlight MUST move to the next record in the list, or to the previous one when the deleted record was
  last.
- **FR-012**: When the deleted record was the only one in view, the list MUST show the same empty-state
  message it shows for an empty view.
- **FR-013**: A delete that fails MUST report the reason in the status bar and leave the tool usable;
  it MUST NOT terminate the session.
- **FR-014**: `ctrl+d` MUST be visible in the footer wherever it is active, and MUST do nothing when no
  record is highlighted.

**Deleting records — command line**

- **FR-015**: Each record type MUST have a peer `delete` command that takes the record's id.
- **FR-016**: The delete command MUST require an explicit flag to proceed, MUST NOT prompt, and MUST NOT
  block on input under any circumstances.
- **FR-017**: Invoked without the explicit flag, the delete command MUST delete nothing, MUST explain on
  stderr that the flag is required, and MUST exit with the usage-error code.
- **FR-018**: On success the delete command MUST exit 0 and write nothing to stdout.
- **FR-019**: Delete failures MUST use the established exit codes: not-found for an unresolvable id,
  usage error for a malformed or incomplete invocation, workspace error when the workspace cannot be
  read or written.
- **FR-020**: The delete command MUST NOT colorize or decorate output when stdout is not a terminal.

**Confirmation dialogs**

- **FR-021**: Every confirmation MUST be a slim, single-question bar rather than a large box, and MUST be
  centred on the whole screen regardless of which pane raised it.
- **FR-022**: Every confirmation MUST offer exactly two options, each labelled with its key and with the
  outcome that key produces, in wording that does not require the user to work out which button does what
  they asked for.
- **FR-023**: `Esc` MUST always be the option that halts the user's request and changes nothing.
- **FR-024**: `Enter` MUST always be the option that proceeds with the user's request.
- **FR-025**: A confirmation MUST consume every keystroke while it is up: keys other than `Esc` and
  `Enter` do nothing and MUST NOT reach the screen underneath.
- **FR-026**: Both existing and new confirmation points — discarding unsaved edits, and deleting a
  record — MUST use this same confirmation, so no two confirmations in the tool look or behave
  differently.
- **FR-027**: Confirmations MUST continue to fire only where something would be lost; this feature adds
  exactly one new confirmation point, which is deletion.

**List columns**

- **FR-028**: The list MUST present records in four labelled columns: date, type, title, and tags.
- **FR-029**: The column headers MUST be visible above the rows and MUST remain visible while the list is
  scrolled.
- **FR-030**: Each value MUST render in its own column, and an empty value MUST leave its cell empty
  without shifting any other column's position.
- **FR-031**: A value wider than its column MUST be truncated with a visible ellipsis; a row MUST NOT
  wrap onto a second line.
- **FR-032**: When the available width cannot hold all four columns, columns MUST be dropped whole —
  with their headers — in the order tags first, then type, rather than any column being narrowed past
  legibility. The date and title columns MUST always remain.
- **FR-033**: The Tasks collection MUST use the same four columns, and a task's done state MUST stay
  distinguishable at a glance.

**Workspace path**

- **FR-034**: The top bar MUST show the path of the workspace the session is reading, anchored to the
  bar's right-hand edge and staying anchored there across terminal resizes.
- **FR-035**: A path under the user's home directory MUST be shown in its shortened home form.
- **FR-036**: A path too long for the space the top bar has left MUST be shortened by eliding from the
  left, keeping the final component intact and marking the elision visibly. The collection names MUST
  keep their position and their full text; the path is what gives way.
- **FR-037**: Paths containing spaces and non-ASCII characters MUST render correctly.
- **FR-038**: The workspace path MUST NOT consume any bottom-bar width. The bottom bar's help text and
  version indicator MUST be unchanged by this feature.

**Cursor placement on entering edit mode**

- **FR-039**: Entering edit mode MUST place the cursor on an empty line separated from the last non-empty
  line of content by exactly one blank line.
- **FR-040**: When the content already ends in blank lines, the rule MUST resolve against the last
  non-empty line rather than stacking further blank lines.
- **FR-041**: Entering edit mode on empty content MUST place the cursor on the first line with nothing
  inserted above it.
- **FR-042**: Positioning the cursor MUST NOT by itself count as an unsaved change: entering edit mode
  and leaving without typing MUST raise no confirmation and MUST leave the file on disk unchanged.
- **FR-043**: The rule MUST apply wherever edit mode is entered, including editing a task's body.

### Key Entities

- **Record**: a meeting, a note, or a task — the three things a user can list, and now the three things a
  user can delete. A meeting or note is one markdown file; a task is one line plus an optional indented
  body inside the tasks file.
- **Mirror**: a checkbox in a document that points at a task. Deleting the task makes its mirrors dead;
  the mirror's own text belongs to the user and is never rewritten by a delete.
- **Confirmation**: a question with exactly two answers — stop (`Esc`) or proceed (`Enter`) — raised only
  where confirming loses something.
- **Row**: one record's presentation in the list, as four column cells: date, type, title, tags.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can delete any record from the list in three keystrokes or fewer from the moment it
  is highlighted, without leaving the tool.
- **SC-002**: 100% of deletions leave every other record in the workspace byte-for-byte unchanged,
  verified across meetings, notes, and tasks including tasks with multi-line bodies and tasks mirrored
  into documents.
- **SC-003**: Deleting a record from the command line completes without any prompt, so a script or an
  assistant with stdin closed never hangs — verified with stdin closed and stdout redirected.
- **SC-004**: A declined confirmation results in zero changes on disk, in every case where a confirmation
  can be raised.
- **SC-005**: Every confirmation in the product resolves with a single keypress, and the same key means
  the same thing every time: `Esc` stops, `Enter` proceeds.
- **SC-006**: Every confirmation option's label names its key and the outcome that key produces; no label
  in the product is a bare "OK", "Yes", "No", or "Cancel".
- **SC-007**: In a list containing records with every combination of missing type and missing tags, a
  value never appears under the wrong header, and the title starts at the same position on every row.
- **SC-008**: A user can read the workspace path from the top-right corner of the list screen on a
  standard 80-column terminal without opening a menu or running a command, and the bottom bar shows
  exactly what it showed before this feature.
- **SC-009**: Appending a line to an existing note takes zero cursor-movement keystrokes between entering
  edit mode and typing.
- **SC-010**: Entering and leaving edit mode without typing produces no confirmation and no file write,
  100% of the time.
- **SC-011**: Both front-ends can delete each of the three record types — no capability exists in one and
  not the other.

## Assumptions

- **The task checkbox sits outside the four columns.** A task row shows its done state as a narrow
  leading marker (and the existing struck-through text), so the four labelled columns mean the same four
  fields in every collection. The alternative — folding the checkbox into the date column — would make
  the first column mean two different things depending on the collection.
- **Column drop priority is tags, then type.** When width is short, tags go first and type second; date
  and title always remain. They are the two fields every record has and the two the user scans by.
- **The explicit delete flag is `--force`.** It is the conventional spelling for "I know this is
  destructive, do not ask", and Principle II already requires destructive operations to take a flag
  rather than prompt. `--yes` was considered and rejected as reading like an answer to a prompt that this
  command never asks.
- **Delete takes an id, not a path.** Ids are what `--json` output already exposes and what links already
  resolve against, and one identifier form for all three record types keeps the three delete commands
  identical. A path form for documents was considered and left out as a second way to say the same thing.
- **The workspace path lives in the top bar, not the bottom one.** Issue #32 as filed asked for the
  bottom bar; that was revised during specification. Bottom-bar width is already spent on
  help text and the version indicator, and the help text is the thing a user reads most often. The top
  bar has room to the right of the collection names, and a corner is the easiest place on a screen to
  find something that never moves. The consequence is that the path shows on screens that have a top bar
  — the list screen today — and not on the full-screen preview and editor, which are transient states the
  user returns from. That is accepted rather than overlooked: adding a bar to those screens to carry one
  string would cost more room than it saves.
- **Cursor placement inserts nothing.** The editor positions the cursor below the content without writing
  blank lines into the buffer, so an untouched document stays untouched. Any trailing blank lines that end
  up in the file arise only from what the user actually types.
- **The list's date column shows the date already shown today** — the record's created date, in the same
  form — and this feature does not change which date is displayed or how records are sorted.
- **Deleting does not scan for inbound links first.** The confirmation names the record, not its
  dependents; discovering that a deleted document was linked to is the existing link check's job, and
  adding a workspace scan to every delete would trade a real cost for a warning the user can already get.
- **Existing bindings are unaffected.** `ctrl+d` is not currently bound in the list, and `ctrl+c` and
  `ctrl+q` remain reserved.
- **There is no session-lifetime cache by the time this is built.** `010-read-on-load` lands first, so a
  delete does not have to invalidate a snapshot, evict a record, or tell any view that something is
  gone — the next load reads the files. The list refresh FR-011 requires is for immediate feedback, not
  for correctness, and it is a re-read of what is on disk.

## Dependencies and Relationships

- **Issue #57 (editor replaces the preview pane)** was split out of this issue and is *not* part of this
  feature. It touches the `list → preview → edit` model; the two items here that interact with it —
  cursor placement on entering edit mode (Story 7) and the confirmation the editor raises (Story 1) —
  are specified in terms of *entering edit mode* and *any confirmation*, so they hold whether the editor
  is full-screen or in-pane. If both features are in flight, they touch the same screens and should be
  sequenced rather than developed in parallel.
- **Issue #38 (delete records)** was closed as a duplicate of #32; its content is folded into Stories 2–4
  and nothing from it is outstanding.
- **Issue #43 (completed tasks stored outside `tasks.md`)** touches the same file and the same
  "remove a line without losing the surrounding ones" mechanics as task deletion. If both land, the task
  removal behaviour should be shared rather than written twice.
- **Issue #47 (workspace in the terminal tab strip)** answers the same "which workspace is this?"
  question from outside the app. Distinct surface, no shared behaviour; both are worth having.
- **Issue #51 (read from disk on view load)**, specified as `010-read-on-load`, **lands before this
  feature** — this is settled, not a preference. It retires the session-lifetime snapshot: every list
  load, and every return to a list from another screen, reads the workspace files at that moment, and a
  displayed list re-reads periodically on its own. Two consequences for this spec:
  - There is no in-memory cache for a delete to invalidate. FR-011's refresh is a re-read, not cache
    surgery, and no code path needs to notify a view that a record has gone.
  - A periodic re-read can land while a confirmation is on screen. `010-read-on-load` requires a refresh
    not to dismiss an open dialog; this spec requires the confirmation to act on the record it named when
    it was raised (FR-010), so the two together mean a background refresh can never redirect a delete
    onto a different record.

  **Gate on planning**: when `010-read-on-load` is fully implemented, its work is merged into this
  branch and this spec is re-checked against the merged code *before* `/speckit-plan` runs. Anything in
  the delete-refresh path or the list-load path that the merge changes is reconciled here first, so the
  plan is written against the code that will actually exist rather than against today's snapshot
  behaviour.
- **Existing mirror resolution** already has a `dead` outcome for a mirror whose task cannot be found.
  Story 4 depends on that outcome existing and reuses it rather than introducing a new one.
- **Existing exit-code registry** (`docs/REQUIREMENTS.md` §4.1) covers everything the delete commands
  need; this feature adds no new exit code.

## Out of Scope

- **An editor that replaces the preview pane** — split out as issue #57.
- **Trash, undo, restore, or tombstones for deleted records.** The confirmation and the explicit flag are
  the safety net; anything else is new state to keep correct.
- **Repairing or removing links that point at a deleted record.** They become dead links and are reported
  as such by the existing link check.
- **Bulk or multi-select deletion.** One highlighted record, one confirmation.
- **Deleting a record from the full-screen preview or from inside the editor.** Deletion is a list
  gesture in this feature.
- **Renaming, moving, or archiving records.** Deletion only.
- **Sorting, grouping, or reordering the list, or making columns resizable or user-configurable.** The
  columns are a fixed, sensible default; configuration beyond workspace paths is out of scope by
  Principle III.
- **Changing which date a row shows or how records are ordered.**
- **A workspace switcher, or any way to change workspace from inside the tool.** The top bar reports
  the workspace; it does not manage it.
- **Any other change to the top bar.** The product name, the divider, and the collection names keep their
  content, order, and position; this feature only adds the path at the right-hand edge.
- **Any change to what the editor saves, when it saves, or how it handles conflicts.** This feature moves
  a cursor; it does not touch save semantics.
