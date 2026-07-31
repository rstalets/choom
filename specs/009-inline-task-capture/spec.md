# Feature Specification: Inline Task Capture

**Feature Branch**: `009-inline-task-capture`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Issue 21"

**Source**: GitHub issue #21 "[Feature]: Tasks created inline from inside a note or meeting", which asks
for followups to be captured without leaving the editor, for the resulting task to remember the
conversation that produced it, for the note to keep a working checkbox pointing at that task, and for
completing the task from either end to keep the two in agreement.

---

## Overview

Today a task can only be created from the command bar or the command line. In practice most followups
are born mid-sentence: someone is taking notes, a commitment is made, and capturing it means leaving
the editor, losing your place in the document, and typing the same words twice — once as a note line,
once as a task. The friction is high enough that either the task never gets captured or the note loses
the thought.

There is also no trail. A task carries no indication of the conversation that produced it, so "call
Terry" a week later has lost its reason.

This feature closes both gaps with one gesture. Typing `/task.followup call Terry about the renewal
#procurement` on its own line in the editor creates the task and leaves a working checkbox in the note
that points at it. Four properties define the result:

1. **One grammar, learned once.** The editor accepts the same `/task` verb, the same `.type` suffix,
   and the same `#tag` tokens the command bar already accepts, and the task it produces is
   indistinguishable from one typed anywhere else. What differs is only what happens afterwards: the
   command bar navigates to the tasks collection, and the editor does not move at all.
2. **The note keeps the commitment it witnessed.** The typed command is replaced by a checklist item
   linking to the new task, so the note reads as a complete record on its own and renders correctly in
   any markdown viewer.
3. **The task remembers where it came from,** as an ordinary link to the source document — not a
   provenance field invented for this feature. Everything that already reads links applies for free.
4. **There is one source of truth and two control surfaces.** The tasks file holds the state; the
   checkbox in the note is a control onto that record, not a second copy of it. Ticking either one
   updates the other, and the two converge whenever the document is next read or written — with no
   background work, no repair pass, and nothing watching the filesystem.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture a followup without leaving the editor (Priority: P1)

Mid-meeting, someone commits to something. The note-taker, already in the editor, starts a new line and
types `/task.followup call Terry about the renewal #procurement` and presses enter. The task is created.
The line they typed becomes a checklist item linking to it. The cursor sits at the end of that line and
they keep typing. Nothing on screen moved.

**Why this priority**: This is the feature. Everything else here refines what the capture leaves behind
or what happens to it later; without this, none of it exists. On its own it already removes the reason
followups go uncaptured.

**Independent Test**: Open a document, type the command on its own line, press enter, and confirm a task
appears in the tasks list with the right description, type, and tags, that the editor did not move, and
that the document now shows a checklist item pointing at the task.

**Acceptance Scenarios**:

1. **Given** the editor is open on a document, **When** a line whose entire content is
   `/task.followup call Terry about the renewal #procurement` is submitted, **Then** a task is created
   with description "call Terry about the renewal", type "followup", and tag "procurement".
2. **Given** the same submission, **When** it succeeds, **Then** the document is saved in its
   pre-command state before the task is written, so nothing typed before the command can be lost.
3. **Given** the same submission, **When** it succeeds, **Then** the typed line is replaced by a
   checklist item linking to the new task, the cursor lands at the end of that line, and the editor keeps
   focus.
4. **Given** the same submission, **When** it succeeds, **Then** no screen or collection change occurs —
   unlike the command bar, which navigates to the tasks collection.
5. **Given** `/task buy milk` with no type suffix, **When** submitted, **Then** the task is created with
   no type, exactly as the command bar's `/task` does.
6. **Given** a task created this way and one created from the command bar with the same words, **When**
   both lines are compared in the tasks file, **Then** they differ only in id, timestamp, and the link
   recording the source document — the format, tag extraction, and validation are identical.
7. **Given** the inserted checklist item, **When** the user undoes, rewords, or indents it under a
   bullet, **Then** the task itself is unaffected — it is an ordinary unsaved edit to the document.
8. **Given** a line that is not entirely the command, such as `Did you know you can type /task here?`,
   **When** submitted, **Then** it is ordinary document text and no task is created.

---

### User Story 2 - Promote something already written (Priority: P2)

Half a page later, the note-taker realizes a line they already wrote is a followup: they had typed
"chase the security review with Priya". They put the cursor at the start of that line, type
`/task.followup ` in front of it, and press enter. The existing words become the task, and the line is
rewritten as the checklist item.

**Why this priority**: This is the common case of noticing after the fact, and it is what makes the
feature usable in a real meeting where the recognition arrives late. It rides entirely on Story 1's
mechanism, so it costs almost nothing on top.

**Independent Test**: Write a plain line of prose, prefix it with the command, submit, and confirm the
task's description is the pre-existing text and the line has become the checklist item.

**Acceptance Scenarios**:

1. **Given** a line reading `chase the security review with Priya`, **When** the user prefixes it with
   `/task.followup ` and submits, **Then** a followup task is created whose description is
   "chase the security review with Priya" and the line becomes the checklist item for it.
2. **Given** a promoted line containing `#tags`, **When** submitted, **Then** the tags are extracted from
   the text exactly as they would be from a freshly typed description, and do not remain in the task's
   description.
3. **Given** a line whose entire content is `/task` with nothing after it, **When** submitted, **Then**
   no task is created, the line is left exactly as typed, and a message states that a description is
   required.
4. **Given** a line whose entire content is `/task.followup` with nothing after it, **When** submitted,
   **Then** the same applies — the type suffix is not a description.

---

### User Story 3 - The task remembers the conversation (Priority: P3)

A week later "call Terry about the renewal" has lost its reason. Opening the task shows the meeting it
came out of, and one keystroke opens that meeting. From the other direction, asking what came out of
that meeting lists the followups it produced.

**Why this priority**: Provenance is half the value of capturing in place, and it is what turns the tasks
file from a list into a record. It depends on the link primitive, so it follows the capture itself.

**Independent Test**: Capture a task from inside a meeting, then confirm the task names that meeting, that
opening the link reaches it, and that asking for the meeting's inbound links lists the task.

**Acceptance Scenarios**:

1. **Given** a task captured from inside a meeting, **When** its line in the tasks file is inspected,
   **Then** it carries a link to that meeting's id in its metadata comment's `links` field — no field
   specific to this feature.
2. **Given** that task, **When** it is previewed, **Then** the originating document is named and the
   open key opens it.
3. **Given** that meeting, **When** its inbound links are requested from either interface, **Then** the
   captured task is listed.
4. **Given** a task captured from a document that is later deleted, **When** the task is read, **Then**
   the unresolvable link produces a warning naming it, is never silently removed, and is never fatal.
5. **Given** a task captured from a document that is later moved to a different directory, **When** the
   task's link is resolved, **Then** it still resolves, because the id and not the path is the identity.

---

### User Story 4 - Tick it off in the tasks list, the note agrees (Priority: P4)

The followup gets done. In the tasks list, the user presses the toggle key. The tasks file is updated as
it is today — and the checkbox sitting in the meeting note is updated too, so a person reading that note
later sees a completed commitment rather than an open one.

**Why this priority**: Without this the note's checkbox is decoration that quietly goes stale, which is
worse than not having it. It is separable from Story 5 because it only writes in one direction.

**Independent Test**: Capture a task from a document, complete it from the tasks list, and confirm both
the tasks file and the document's checkbox show it complete, without the document's `updated` timestamp
changing.

**Acceptance Scenarios**:

1. **Given** a task with a checklist item in one document, **When** it is completed from the tasks list,
   **Then** the tasks file is updated exactly as it is today and the document's checklist item is ticked.
2. **Given** a task whose checklist item appears in several documents, **When** it is completed, **Then**
   every one of them is updated.
3. **Given** a document whose checklist item has been moved to a different line or reworded since it was
   inserted, **When** the task is completed, **Then** the right item is still found, because it is located
   by the task's id and never by line number or by matching the task's text.
4. **Given** a document that cannot be written — missing, read-only, or a dead path — **When** the task is
   completed, **Then** the tasks file is still updated, a warning names the document, and the toggle is
   not blocked or reversed.
5. **Given** the document is open in the editor with unsaved changes, **When** the task is completed from
   the tasks list, **Then** the document is not written underneath the user; the change reaches it through
   the existing external-change path at their next save.
6. **Given** any of the above, **When** a checklist item is synced, **Then** the document's `updated`
   frontmatter is not stamped — ticking a box in the tasks list is not an edit to the meeting note, and
   must not reorder every list sorted by recency.
7. **Given** a task with no checklist item anywhere, **When** it is completed, **Then** the toggle behaves
   exactly as it does today and no document is read or written for it.

---

### User Story 5 - Tick it off in the note, the tasks list agrees (Priority: P5)

Reviewing the meeting note, the user types an `x` between the brackets of the checklist item — the same
thing they would do to any markdown checklist. When the document is saved, the task is marked done.

**Why this priority**: This is what makes the checkbox a control surface rather than a display. It comes
after Story 4 because the tasks file remains the arbiter, and the outbound direction is what keeps the
note honest even if this direction never ships.

**Independent Test**: Tick a checklist item in a document, save, and confirm the task is complete in the
tasks list; untick, save, and confirm it is open again.

**Acceptance Scenarios**:

1. **Given** a checklist item whose box is ticked in the editor, **When** the document is saved, **Then**
   its task is marked complete in the tasks file.
2. **Given** a ticked item that is unticked and saved, **When** the save completes, **Then** the task is
   marked open again.
3. **Given** a document saved with no checklist item changed, **When** the save completes, **Then** the
   tasks file is not written.
4. **Given** a save that updates the tasks file, **When** it completes, **Then** it does not trigger a
   write back into the document that supplied the state — reconciliation is idempotent and does not
   cascade.
5. **Given** a checklist item whose id resolves to no task, **When** the document is saved, **Then** the
   item is left exactly as written, a warning names it, and the save is not blocked.
6. **Given** a document holding two checklist items for the same task that disagree with each other,
   **When** it is saved, **Then** the tasks file is left unchanged for that task and a warning names it —
   the system does not pick a winner between two of the user's own edits.
7. **Given** a checklist item that the user did not touch in this editing session but whose task changed
   state elsewhere, **When** the document is saved, **Then** the tasks file wins and the item is corrected
   on the way out.
8. **Given** a checklist item the user did change in this session whose task also changed state elsewhere,
   **When** the document is saved, **Then** the save wins, the tasks file is updated, and a warning names
   the task so the divergence is reported rather than silently resolved.

---

### User Story 6 - Opening a document is enough to make it agree (Priority: P6)

Someone hand-edited the tasks file in another editor. A note was closed when its task was completed. A
checklist item got copy-pasted into a second note. All of them converge the next time that document is
opened — there is no repair command to remember and nothing watching the filesystem.

**Why this priority**: This is the backstop that makes the whole design correct without background work.
It is last because in the ordinary flow Stories 4 and 5 already keep the pair in agreement; this is what
handles everything outside that flow.

**Independent Test**: With the app closed, hand-edit the tasks file to complete a task, then open the
document holding its checklist item and confirm the item is now ticked.

**Acceptance Scenarios**:

1. **Given** a task completed outside the app, **When** the document holding its checklist item is opened,
   **Then** the item is reconciled to match the tasks file.
2. **Given** a checklist item copy-pasted into a second document, **When** that document is opened,
   **Then** its item reflects the task's real state — a copy is a control surface onto the same record,
   never a second record.
3. **Given** reconciliation on open changes nothing, **When** the document is opened, **Then** it is not
   written at all.
4. **Given** reconciliation on open changes something, **When** the document is written, **Then** only that
   document is touched, its `updated` frontmatter is not stamped, and no other file in the workspace is
   modified.
5. **Given** a document with no checklist items, **When** it is opened, **Then** the tasks file is not read
   on its behalf and the open is not slowed.
6. **Given** a document opened for reading rather than editing, **When** it is displayed, **Then** the same
   reconciliation applies, so what is shown is never a stale checkbox.

---

### User Story 7 - The same capture from the command line (Priority: P7)

An assistant working in the workspace has just read a meeting and needs to file a followup against it. It
runs `endpaper task add "call Terry about the renewal" --type followup --link meeting_20260728_a1b2c3d4`
and the task is captured with the same relationship the editor would have written.

**Why this priority**: The two interfaces are peers, and the command line is the assistant's only
interface. It is last only because the editor is where the human friction is.

**Independent Test**: Add a task with a link from the command line and confirm the resulting task line is
indistinguishable from one captured in the editor, and that an unknown id fails cleanly.

**Acceptance Scenarios**:

1. **Given** `endpaper task add "<description>" --link <id>` with a resolvable id, **When** it runs,
   **Then** the task is created carrying that link, and the line is identical in shape to one captured in
   the editor.
2. **Given** `--link` naming an id that resolves to nothing, **When** it runs, **Then** it exits non-zero
   with a message naming the id, and no task is created.
3. **Given** `--link` supplied more than once, **When** it runs, **Then** all the ids are recorded, in the
   order given.
4. **Given** `endpaper task done <id>` for a task with checklist items in documents, **When** it runs,
   **Then** those items are updated on the same terms as the toggle in the interactive interface,
   including the warning-and-continue behaviour for documents that cannot be written.
5. **Given** `endpaper task undone <id>`, **When** it runs, **Then** the same propagation applies in the
   opposite direction.
6. **Given** any of these commands with `--json`, **When** they run, **Then** the output reports the task's
   links and the documents whose items were updated, and nothing is written to standard output that is not
   part of that schema.
7. **Given** any of these commands, **When** they run, **Then** they neither prompt, block, nor open an
   editor.

---

### Edge Cases

**Capture**

- A command line submitted with only whitespace after the verb is treated as no description: nothing is
  created and the line is preserved.
- A type or tag token containing characters the existing validation rejects fails the capture, leaves the
  line exactly as typed, and reports which token was rejected.
- The tasks file does not exist yet: it is created, exactly as capture from anywhere else does.
- The tasks file cannot be written: nothing is created, the typed line is preserved verbatim so no words
  are lost, and the message names the file.
- The document has never been saved, or saving it fails: the capture does not proceed, because the task's
  link must point at a document that exists.
- A capture is submitted from inside a task's own body editor: the same rules apply and the resulting link
  points at the tasks file's record, or, if that is not supported, the capture is refused with a message
  rather than producing a link that cannot resolve.
- Two captures in quick succession never collide on an id; each gets a distinct one.
- A capture inside a fenced code block is ordinary text — the same rule the link primitive already holds
  for anything inside code fences and code spans.

**The checklist item left behind**

- The document sits at a depth the layout has not seen before — outside the dated directories, or a daily
  note one level deeper — and the item's path is still correct, because it is computed from the two real
  file locations rather than assembled from a fixed prefix.
- The item's path goes stale because the tasks file or the document moved: the id still resolves, and the
  path is repaired on the document's next save by the existing link repair.
- The user deletes the item from the document: the task is untouched and keeps its link. Deleting a
  checkbox is not deleting a task.
- The user duplicates the item within one document: both are control surfaces onto the same task, and both
  are reconciled.
- The user reindents the item under a bullet or moves it into a list: it is still found, because it is
  located by its id fragment.

**Reconciliation**

- The tasks file has been hand-edited into a state the parser reports as malformed: the malformed line is
  skipped and warned about, and every other task and item still reconciles.
- A document is opened, reconciled, and closed without further edits: it is written at most once, only if
  something actually changed.
- A workspace on cloud storage with files not present locally: reconciliation reads only the tasks file and
  the one document in hand, never the whole workspace, so opening a document never triggers a
  workspace-wide hydration.
- The same task is completed from the tasks list while its document is open and untouched: the item is
  brought into agreement without disturbing the user's cursor or selection.

---

## Requirements *(mandatory)*

### Functional Requirements

**Capture in the editor**

- **FR-001**: A line in the editor whose entire content is `/task` — optionally with a `.<type>` suffix,
  followed by a description — MUST, on submission, create a task and MUST NOT be left in the document as
  typed.
- **FR-002**: The verb, the `.<type>` suffix, and inline `#tag` tokens MUST follow exactly the grammar the
  command bar already accepts; this feature MUST NOT introduce a second grammar for the same operation.
- **FR-003**: A line that is not entirely the command MUST be ordinary document text, and MUST NOT create a
  task.
- **FR-004**: Description parsing, `#tag` extraction, type and tag validation, id generation, and task line
  rendering MUST use the same path as capture from the command bar and the command line, so a task's shape
  does not depend on where it was typed.
- **FR-005**: The document MUST be saved in its pre-command state before the task is written.
- **FR-006**: On success the editor MUST keep focus, the cursor MUST land at the end of the inserted
  checklist item, and no collection, screen, or scroll change MUST occur.
- **FR-007**: A command with no description MUST NOT create a task, MUST leave the line exactly as typed,
  and MUST report that a description is required. A `.<type>` suffix alone MUST NOT count as a description.
- **FR-008**: A line already containing text MUST be promotable by prefixing it with the command:
  everything after the command token on that line becomes the description, with tags extracted from it as
  usual.
- **FR-009**: Every failure — empty description, rejected type or tag token, unwritable tasks file,
  unsaveable document — MUST leave the typed line exactly as entered, report the failure in the status area,
  and return control to the editor without leaving the document.
- **FR-010**: The command MUST be discoverable the same way the editor's other commands are, and MUST appear
  wherever the editor's available commands are listed.

**The checklist item left in the document**

- **FR-011**: On success the typed line MUST be replaced by a checklist item that is a link to the new task,
  written in the link syntax the link primitive defines, carrying the task's id as its fragment.
- **FR-012**: The item's path MUST be computed from the two real file locations by the link primitive's path
  writer, and MUST NOT be assembled from a hardcoded prefix or assumed depth.
- **FR-013**: The item MUST render as an ordinary markdown checklist item and MUST be clickable in a plain
  markdown viewer; the document MUST remain valid CommonMark.
- **FR-014**: The item MUST be an ordinary unsaved edit to the document — undoable, editable, and movable —
  and editing it MUST NOT alter the task.
- **FR-015**: The item MUST be located, for every subsequent operation, by its task id fragment, and MUST
  NOT be located by line number or by matching the task's text.

**The link the task carries**

- **FR-016**: A task captured from inside a document MUST record that document as a link in its metadata
  comment's `links` field, using the link primitive's existing field; this feature MUST NOT define a
  provenance field of its own.
- **FR-017**: Everything that already consumes links MUST apply to that link without change — preview,
  opening the target, and inbound link queries.
- **FR-018**: A link whose target has been deleted MUST produce a warning, MUST NOT be silently removed, and
  MUST NOT be fatal.
- **FR-019**: A task captured outside any document — from the command bar or the command line without a link
  — MUST carry no link, and its line MUST be identical in shape to one produced today.

**State, and which side wins**

- **FR-020**: The tasks file MUST remain the single source of truth for a task's completion state. A
  checklist item in a document MUST be a control surface onto that record and MUST NOT be a second record of
  it.
- **FR-021**: Completing or reopening a task from the tasks list MUST update the tasks file exactly as it
  does today, then update the checklist item in every document the task links to.
- **FR-022**: On saving a document, any checklist item whose box the user changed in that editing session
  MUST be written through to the tasks file.
- **FR-023**: On saving a document, any checklist item the user did not change in that session but which
  disagrees with its task MUST be corrected to match the tasks file.
- **FR-024**: When both a task and its item changed since they last agreed, the save happening now MUST win
  and a warning MUST name the task.
- **FR-025**: When one document holds two items for the same task that disagree with each other, the tasks
  file MUST be left unchanged for that task and a warning MUST name it.
- **FR-026**: On opening a document — for reading or for editing — every checklist item in it MUST be
  reconciled to its task's state.
- **FR-027**: Reconciliation MUST be idempotent, and applying a state to the tasks file MUST NOT re-trigger a
  write back to the document that supplied it.
- **FR-028**: An item whose id resolves to no task MUST be left exactly as written, MUST produce a warning,
  and MUST NOT block the save or the open.
- **FR-029**: Syncing a checklist item MUST NOT stamp the document's `updated` frontmatter.
- **FR-030**: A document MUST be written only when reconciliation actually changes something in it.
- **FR-031**: Reconciliation MUST be scoped to the document in hand plus the tasks file, and MUST NOT read or
  write any other document in the workspace.
- **FR-032**: A document that cannot be written MUST NOT block or reverse a completion: the tasks file MUST
  still be updated, a warning MUST name the document, and the item MUST be reconciled the next time that
  document is opened or saved.
- **FR-033**: A document open with unsaved changes MUST NOT be written underneath the user; the change MUST
  reach it through the existing external-change path at their next save.
- **FR-034**: Completing a task with no checklist items anywhere MUST behave exactly as it does today, with
  no document read or written on its behalf.

**Command line parity**

- **FR-035**: `endpaper task add` MUST accept a `--link <id>` option that records the same relationship the
  editor writes, and MUST accept it more than once.
- **FR-036**: A `--link` id that resolves to nothing MUST exit non-zero with a message naming it, and MUST
  NOT create the task.
- **FR-037**: `endpaper task done` and `endpaper task undone` MUST propagate to checklist items on the same
  terms as the interactive toggle, including the warning-and-continue behaviour for unwritable documents.
- **FR-038**: `--json` output for these commands MUST report the task's links and the documents whose items
  were updated, under a stable, documented schema.
- **FR-039**: These commands MUST remain non-interactive: no prompt, no confirmation, no pager, no editor,
  data on standard output and diagnostics on standard error.

**Documentation**

- **FR-040**: The generated workspace guidance for assistants MUST document in-editor `/task` capture, the
  `--link` option, and the fact that a checklist item linking to a task is a control surface rather than a
  copy.
- **FR-041**: The changelog MUST record the new command-line option, the `--json` schema additions, and the
  new reconciliation behaviour with their version.

### Key Entities

- **Task**: The record of a commitment, held in the tasks file. Owns its completion state. Gains, in this
  feature, a link to the document it was captured in — using the existing link field, not a new one.
- **Checklist item (the mirror)**: A markdown checklist line in a document whose link fragment names a task.
  It is content the user wanted in their note, and simultaneously a control surface onto that task's state.
  It is identified by the task id it carries, never by its position or its wording.
- **Editing session**: The span between a document being opened and being closed. It is what "since they
  last agreed" means: the state each checklist item had when the document was opened or last reconciled,
  held only for the life of that session and never written anywhere.
- **Reconciliation**: The act of bringing a document's checklist items and the tasks file into agreement.
  It happens at exactly two moments — a document opening and a document being saved — and touches only those
  two files.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A followup is captured from inside a document in one line typed and one keystroke, with no
  screen change and no loss of cursor position.
- **SC-002**: Capturing a followup requires the words to be typed once, not twice: the description in the
  task and the line left in the note come from the same typing.
- **SC-003**: A task's line in the tasks file is indistinguishable in format from one captured anywhere
  else, apart from the link recording its origin — verified by comparing captures from all three entry
  points.
- **SC-004**: Given a task and the note it came from, a reader can get from either one to the other in a
  single keystroke, in both directions.
- **SC-005**: A task and its checklist item never disagree after that document has been opened or saved,
  for every combination of where the change was made and which side was stale.
- **SC-006**: No sequence of completing, reopening, opening, and saving produces a state where the two
  disagree permanently, or where a change is applied twice.
- **SC-007**: Opening a document with no checklist items adds no measurable time to the open compared with
  today, and reads no file it does not read today.
- **SC-008**: Opening or saving a document with checklist items reads at most that document and the tasks
  file — never a third file — and adds under 50 ms on a workspace holding several years of documents.
- **SC-012**: Capturing a task from the editor completes in under 200 ms from keypress to the cursor being
  available again, on the same workspace.
- **SC-009**: A note containing checklist items renders correctly, and every one of them is clickable, in a
  plain markdown viewer with no knowledge of this tool.
- **SC-010**: Every failure path — unwritable file, deleted target, malformed line, dead link — leaves the
  user's typed words intact and reports what went wrong and which file it concerns.
- **SC-011**: Every capability here is reachable from both the interactive interface and the command line,
  except the in-editor typing gesture itself, which is inherently interactive.

---

## Assumptions

These are the informed decisions taken where the source issue left room for more than one reading. Each is
a working default, not a settled fact; `/speckit-clarify` is the place to revisit them.

- **Promotion is a prefix, not a suffix.** The issue describes "`/task` with no description on a line that
  already contains text". The existing editor grammar requires a command to be the entire line, so the
  gesture is read as: put the cursor at the start of the line and type the command in front of the text,
  which then serves as the description. This needs no new grammar and no new rule about where in a line a
  command may appear, and it keeps a trailing `/task` as ordinary prose. A dedicated end-of-line gesture was
  considered and rejected on that ground.
- **"Since they last agreed" means since this document was opened.** Nothing is persisted to record when a
  task and its item last matched, because persisting it would be a second source of truth. The comparison
  point is the item's state when the document was opened or last reconciled, held in memory for the life of
  the editing session. This makes the both-sides-changed case detectable without storing anything.
- **Open wins from the tasks file; save wins from the document.** On open the user has not yet acted on this
  document, so the tasks file is authoritative; on save they just have, so their edit is. This yields the
  behaviour the issue describes with a single rule and no stored state.
- **Reconciliation on open writes the document.** The alternative — correcting only what is displayed —
  would leave a stale checkbox in the file for any other reader, which defeats the point of leaving the item
  there at all. The write is scoped to the one document, happens only when something actually changed, and
  does not stamp `updated`.
- **Reopening propagates like completing.** The issue speaks of completion; the reverse direction is treated
  identically throughout, since a checkbox that can only be ticked and not unticked is not a control surface.
- **A capture with no type is valid,** matching the command bar's `/task <description>`.
- **Deleting a checklist item does not delete or unlink the task.** The link on the task records where it
  was captured, which remains true whether or not the note still shows the checkbox.
- **The existing `--type` and `--tag` options on `task add` are unchanged;** `--link` is additive, and an
  existing invocation behaves exactly as it does today.
- **Warnings do not fail a completion.** Propagating to an unwritable document warns on standard error and
  still exits successfully, because the operation the user asked for — completing the task — succeeded.

---

## Dependencies and Relationships

- **#27 / `008-document-links` is a hard dependency** and must land first. This feature writes links; it
  does not define them. It consumes the link format, the id-first resolver, the relative path writer, the
  self-healing of stale paths on save, the `links` field on task lines, the inbound link scan, and the
  full-collection id prefixes. Nothing about link syntax, resolution, or repair is decided here. In
  particular, the checklist item's path correctness at arbitrary depth, and its repair when a file moves,
  are that feature's behaviour and are exercised rather than reimplemented here.
- **#19 / `006-ai-assistant-invocation` supplies the editor command plumbing** that this extends: a command
  occupying an entire line, the save-before-acting rule, status-area reporting, and returning control to the
  editor without leaving the document. `/task` joins `/ai` and `/link` in that framework rather than building
  a second one.
- **#26 / `007-task-content-editing` and #17 / `005-ui-layout-refresh`** define the preview surfaces where a
  task's origin appears; this feature adds a link for them to show, not a new surface.
- **#22** is unaffected: the graph view it becomes will read these edges like any other.
- Ships against the current constitution: the markdown files remain the only state and no index or cache is
  introduced (III); the capture, reconciliation, and conflict rules live in core and are testable without a
  terminal (I); both interfaces stay peers with the command line non-interactive and machine-readable (II);
  hand-edited files, malformed lines, dead links, and unwritable documents are tolerated and never lose a
  line (IV); and the gesture, the failure messages, and which side wins are decided here rather than at the
  keyboard (V).

---

## Out of Scope

- Scanning arbitrary documents for tasks. A checklist item in a note is a control surface onto a record in
  the tasks file; it is not itself a task, and this feature does not make any file other than the tasks file
  a source of tasks.
- Task detail bodies (#26), delivered separately.
- Toggling a checkbox from the rendered preview. The preview is read-only.
- The link syntax, resolver, path writer, healing, and backlink scan (#27). This feature only writes links
  through them.
- A graph view (#22).
- Any background process, file watcher, or repair pass. Convergence happens on open and on save, and nowhere
  else.
- Capturing anything other than a task from the editor. Other in-editor commands are their own features.
- Deleting a task by deleting its checklist item, or any other destructive operation driven from a document.
