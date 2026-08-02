# Feature Specification: Delete a Task From the Line It Lives On

**Feature Branch**: `017-editor-task-delete`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "issue #79. You are 017"

**Source**: GitHub issue #79 "[Feature]: ctrl+d to delete task inside doc editor", which asks that
pressing a key while the cursor sits on a task line in the document editor remove that task from
both the document and the user's task list, after a confirmation.

**Scope settled in refinement**: the binding is **`ctrl+t`**, not `ctrl+d`. `ctrl+d` is claimed
twice over — by `TextArea`'s own delete-character-forward, which is ordinary text editing on every
line of every editor, and by the already-shipped record-delete on a highlighted row in the list view
(`ctrl+d delete` is in the list footer today). Rebinding it inside the editor would silently break
plain character deletion, including on lines that have nothing to do with tasks. `ctrl+t` was
verified unbound at every layer that could claim it — the app, the screen, the list screen, the
editor pane, and `TextArea`'s own defaults — and reads as "task". This choice is settled and is not
reopened by this spec.

---

## Overview

choom already puts tasks into documents. `/task buy the coffee` in the editor writes a task to the
task list and leaves behind a **task line** — an ordinary markdown checklist item whose link points
at that task. `/ai list my tasks from this meeting` does the same thing in bulk, capturing every
task line the assistant returns. Both are working as designed, and both produce the same problem:
the fastest way to create a task is now much faster than the fastest way to get rid of one.

Today, removing a task the user did not want takes two separate gestures in two separate places.
Delete the line in the editor, then leave the editor, switch to the Tasks collection, find the task,
and delete it there. Skip the second half and the task lives on in the task list with nothing
pointing at it. Skip the first half and the document keeps a checklist item whose link resolves to
nothing.

This feature makes it one gesture. Put the cursor on the task line, press `ctrl+t`, confirm, and the
line leaves the document and the task leaves the task list.

Because that single keystroke writes to two files at once, three properties define it:

1. **It removes exactly one line, and only the line the cursor is on.** Not the blank line above it,
   not the indented note beneath it, not a second copy of the same task elsewhere in the document,
   and not one byte of anything else. A key that deletes user text is only trustworthy if the amount
   it deletes is exactly what the user pointed at.
2. **It refuses rather than guesses.** When the document and the task list have drifted apart, or
   when the task list has a line choom cannot parse, the safe move is to change nothing and say why.
   A deletion built on a misreading is the one failure this feature cannot recover from.
3. **It asks once, and only when there is something to lose.** The confirmation appears when a task
   line is under the cursor. On any other line the keypress does nothing at all — no dialog, no
   write. A dialog that appears for a no-op is how a confirmation stops being read.

### Terminology

- **Task line** (the issue's word) and **mirror** (the codebase's word) are the same thing: a
  checklist item in a document whose link destination names a task id, e.g.
  `- [ ] [Buy the coffee](../../tasks.md#task_a1b2c3)`. It is simultaneously text the user wanted in
  their note and a control surface onto that task's completion state.
- **Task record**: the task's own line, and any indented body beneath it, in `tasks.md`.
- **Document**: whatever the editor currently has open — a meeting note, a general note, or a task's
  own body. All three can contain task lines.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Throw away a task the assistant invented (Priority: P1)

Someone runs `/ai list my tasks from this meeting` in a meeting note. Five task lines come back and
all five are already in the task list. Four are right. The fifth is something the assistant inferred
that nobody actually agreed to. They put the cursor on that line, press `ctrl+t`, read the
confirmation naming the task, and press Enter. The line disappears from the note, the task
disappears from the task list, and the other four are untouched.

**Why this priority**: This is the problem the issue reports, in the exact shape it reports it. With
this alone the feature is worth having.

**Independent Test**: Capture several tasks into a document, delete one of them with `ctrl+t`, and
confirm the document keeps every other line byte-for-byte while the task list keeps every other
task.

**Acceptance Scenarios**:

1. **Given** a document open in the editor containing a task line whose task exists in the task
   list, **When** the cursor is on that line and `ctrl+t` is pressed, **Then** a confirmation naming
   the task appears.
2. **Given** that confirmation, **When** it is confirmed, **Then** the task line is removed from the
   document, the task record is removed from the task list, and both changes are on disk.
3. **Given** that confirmation, **When** it is cancelled, **Then** nothing is written to either file
   and the cursor returns to where it was.
4. **Given** a document with five task lines, **When** one is deleted, **Then** the other four lines
   and the other four task records are unchanged, including their completion states.

---

### User Story 2 - Undo a mistyped `/task` without leaving the editor (Priority: P1)

Someone types `/task folow up with Dana`, presses Enter, and sees the typo land as a checklist item.
Rather than editing the line and then hunting the task down in the Tasks collection to fix it there
too, they press `ctrl+t` on the line, confirm, and retype the command correctly.

**Why this priority**: Same mechanism as Story 1, but it is the case that makes the feature feel like
part of capture rather than a cleanup tool. It needs no additional behaviour.

**Independent Test**: Capture a task with `/task`, delete it with `ctrl+t` in the same editing
session, and confirm the document is back to the text that preceded the capture and the task list
has no record of it.

**Acceptance Scenarios**:

1. **Given** a task captured with `/task` earlier in this same editing session, **When** it is
   deleted with `ctrl+t`, **Then** it is removed from both places exactly as a task captured in an
   earlier session would be — nothing depends on when the task was created.

---

### User Story 3 - The key does nothing on a line that is not a task (Priority: P1)

Someone is typing a paragraph in the middle of a note and presses `ctrl+t`, either by accident or to
see what it does. Nothing happens: no dialog to dismiss, no text removed, no file written. A short
note in the status bar says there is no task on this line.

**Why this priority**: This is the safety half of the feature and it ships with it, not after it. A
destructive binding that is live on every line of the editor is only acceptable if its behaviour off
a task line is provably nothing.

**Independent Test**: Press `ctrl+t` on prose, on a heading, on a blank line, on a plain checklist
item with no link, and on a checklist item inside a fenced code block; confirm no dialog is raised
and neither file is written in any case.

**Acceptance Scenarios**:

1. **Given** the cursor on a line of ordinary prose, **When** `ctrl+t` is pressed, **Then** no
   confirmation appears and no file is written.
2. **Given** the cursor on `- [ ] buy milk` — a checklist item with no task link — **When** `ctrl+t`
   is pressed, **Then** no confirmation appears and no file is written.
3. **Given** the cursor on a task line that sits inside a fenced code block, **When** `ctrl+t` is
   pressed, **Then** no confirmation appears and no file is written, because a line inside a fence is
   text about tasks, not a task.

---

### User Story 4 - Clean up a task line whose task is already gone (Priority: P2)

Someone deleted a task from the Tasks collection last week. The meeting note it came from still
carries the checklist item, and opening the note reports the link as dead. They put the cursor on it
and press `ctrl+t`. The confirmation says the task is no longer in the task list and that only the
line will be removed. They confirm, and the line goes.

**Why this priority**: This is the drift case that already exists in shipped workspaces, and the
feature is the natural place to resolve it. It is P2 because Stories 1–3 are a complete feature
without it.

**Independent Test**: Delete a task through the task list, reopen the document that mirrors it, and
confirm `ctrl+t` on the stale line removes the line, leaves the task list byte-identical, and says
which of the two it did.

**Acceptance Scenarios**:

1. **Given** a task line whose id matches no task in a cleanly-parsed task list, **When** `ctrl+t` is
   confirmed, **Then** the line is removed from the document and the task list is not written to at
   all.
2. **Given** that same situation, **When** the confirmation is shown, **Then** its wording states
   that the task is already absent and that only the document line will be removed.

---

### User Story 5 - A task list choom cannot fully parse stops the deletion (Priority: P2)

Someone hand-edited `tasks.md` and left a metadata comment broken — an unterminated `<!--`, or a
comment with an unrecognised token in it. That line is skipped when the task list is read, so the
task it describes is invisible to choom. Later, in a document, they press `ctrl+t` on a task line
whose id choom cannot find. choom does not remove anything. It says the task list has a line it
could not read, names the line number, and tells them to fix it first.

**Why this priority**: This is the difference between "the task is gone" and "the task is
unreadable", and choom cannot tell them apart by id alone. Getting it wrong deletes the user's
document line while quietly leaving the task behind.

**Independent Test**: Break one metadata comment in `tasks.md`, then press `ctrl+t` on a task line
whose id does not resolve; confirm neither file is written and the message names the unreadable line.

**Acceptance Scenarios**:

1. **Given** a task list containing at least one line choom could not parse, **When** `ctrl+t` is
   pressed on a task line whose id does not resolve, **Then** nothing is written to either file and
   the message names the unreadable line and what to do about it.
2. **Given** that same broken task list, **When** `ctrl+t` is pressed on a task line whose id *does*
   resolve to a readable task, **Then** the deletion proceeds normally — one broken line never
   prevents the rest of the file from working (Principle IV).

---

### Edge Cases

**What gets removed from the document**

- **Blank lines around the task line.** Exactly the task line and its own line terminator are
  removed. A blank line above it and a blank line below it both stay, even when that leaves two
  consecutive blank lines where there used to be one item. choom does not tidy. A blank line the
  user typed is a character the user typed.
- **Indented continuation beneath the task line.** A sub-list, a nested note, or any indented text
  under the task line is left in place. It may now be orphaned formatting, and that is the correct
  outcome: the cursor was on one line, so one line is removed. This is deliberately *unlike* the
  task list, where a task's indented body is part of the record and goes with it.
- **The task line's own indentation.** A task line nested inside another list is removed along with
  its leading whitespace. No surrounding line's indentation changes.
- **Trailing or leading prose on the task line.** A line such as
  `- [ ] [Ship it](../../tasks.md#task_x) — before Friday, ask Dana` is one line and is removed
  whole, including the trailing prose and any additional links on it. Because that text is not part
  of the task's description, the confirmation must say so explicitly before it goes.
- **The task line is the last line of the file with no trailing newline.** The file's
  trailing-newline state is preserved as it was; removing the last line does not add or remove a
  final newline elsewhere.
- **The task line is the document's only body line.** The body becomes empty. Frontmatter is
  untouched and the file is never deleted.
- **Line endings.** A CRLF document stays CRLF and an LF document stays LF. No line other than the
  removed one changes by a single byte.

**When the two sides disagree**

- **Task line in the document, no matching task record** (deleted elsewhere), and the task list
  parses cleanly: confirm, remove the document line, write nothing to the task list. Story 4.
- **Task line in the document, no matching task record, and the task list has unparseable lines**:
  refuse, write nothing, name the unreadable line. Story 5.
- **The same id appears on two task records** (a hand-edit collision): refuse, write nothing, and
  report the conflicting line numbers so the user can fix the duplicate — the same refusal the task
  list's own delete already makes.
- **A task record with no task line anywhere**: not reachable by this gesture, which is driven by
  the cursor. It is deleted from the Tasks collection, as today.
- **The same task mirrored twice in one document**: the task record is deleted and only the line
  under the cursor is removed. The other line becomes a dead task line, is reported in the status
  bar at the time, and is reported again when the document is next opened. Removing a line the user
  did not point at is not an option.
- **The same task mirrored in a different document**: that document is not opened, read, or written.
  Its line becomes a dead task line and is reported when it is next opened, exactly as it is today
  when a task is deleted from the task list.

**When the keypress does nothing**

- Cursor on prose, a heading, a blank line, frontmatter, a plain checklist item with no link, or a
  checklist item whose only link is not a task link.
- Cursor on a task line inside a fenced code block or an inline code span — those are excluded
  before this feature ever sees them, by the same masking the link scanner already applies.
- An assistant request is in flight (the buffer is read-only for its duration).
- The link picker is open awaiting a choice.

**Other**

- **A multi-line selection is active.** The cursor's line is what counts; the selection is ignored
  and never extends the deletion beyond one line.
- **Editing a task's own body, and the cursor is on a task line for a *different* task.** The
  deletion works: the other task's record is removed and the line leaves this task's body.
- **Editing a task's own body, and the cursor is on a task line for *that same* task.** Refuse,
  write nothing, and say why — deleting the record whose body is currently being edited would leave
  the editor holding text with nowhere to save it.
- **The task is already completed** (`- [x]`). It is deleted the same way, with no extra prompt and
  no special case.
- **The document save fails** after the task record was removed. The task is gone, the buffer shows
  the line removed and is marked unsaved, and the failure is named in the status bar. Every word the
  user wrote is still on disk; nothing is truncated.
- **The task list write fails.** Nothing is removed from the document, the buffer is untouched, and
  the failure is named.
- **The editor's undo is pressed after a deletion.** It restores the line in the buffer only. The
  task record is not restored — the undo history belongs to the text widget and has never spanned
  files. Saving afterwards produces a dead task line, reported like any other.

---

## Requirements *(mandatory)*

### Functional Requirements

**The binding**

- **FR-001**: The editor MUST bind `ctrl+t` to delete the task on the cursor's line, in both the
  inline editor pane and the full-screen editor, with identical behaviour in each.
- **FR-002**: `ctrl+t` MUST be visible in the editor's footer, per Principle V's no-hidden-keys rule.
  It is shown whenever the editor is active, not only when the cursor happens to be on a task line —
  a footer that appears and disappears as the cursor moves is a flicker, not a help line.
- **FR-003**: `ctrl+d` MUST NOT be rebound anywhere in the editor by this feature. `TextArea`'s
  delete-character-forward and the list view's shipped record-delete both keep it.
- **FR-004**: `ctrl+t` MUST be inert while an assistant request is in flight and while the link
  picker is open, matching how the editor already gates its other actions in those states.

**Recognising the target**

- **FR-005**: The cursor's line is a valid target when, and only when, it is a checklist item
  carrying a link whose destination fragment names a task id — the same definition the editor already
  uses to recognise a task line for completion-state syncing. There MUST NOT be a second, divergent
  definition of what a task line is.
- **FR-006**: A line inside a fenced code block or an inline code span MUST NOT be a valid target.
- **FR-007**: Where a line carries several task links, the first in document order is the task being
  deleted — again, the existing rule, unchanged.
- **FR-008**: When the cursor's line is not a valid target, `ctrl+t` MUST NOT raise a confirmation
  and MUST NOT write to any file. It MUST leave a brief, non-warning status note saying there is no
  task on this line, so an advertised key is never silently dead.

**The confirmation**

- **FR-009**: When the cursor's line is a valid target, `ctrl+t` MUST raise the product's existing
  single confirmation dialog — Esc changes nothing, Enter proceeds — and MUST NOT introduce a second
  dialog style.
- **FR-010**: The confirmation MUST name the task by its description as the line displays it, state
  that the task will be removed from both the document and the task list, and state that it cannot be
  undone.
- **FR-011**: When the cursor's line carries any text beyond the checkbox and the task's own link,
  the confirmation MUST additionally make clear that the rest of the line goes with it. The user must
  not discover after the fact that they deleted a sentence.
- **FR-012**: When the task id resolves to no task record and the task list parsed cleanly, the
  confirmation MUST say the task is already absent from the task list and that only the document line
  will be removed.
- **FR-013**: The task id and the target line MUST be captured at the moment the confirmation is
  raised and acted on when it returns, so nothing that happens in between can redirect the deletion
  onto a different line.
- **FR-014**: Cancelling the confirmation MUST write nothing to any file — including no save of the
  editor's unsaved changes. A cancelled gesture has no side effects at all.

**The deletion**

- **FR-015**: On confirmation, the task record MUST be removed from the task list first, by id,
  through the same core operation the CLI's `task delete` and the list view's `ctrl+d` already call.
  Only if that succeeds does the document change.
- **FR-016**: Removing the task record MUST remove its checkbox line and its indented body span, and
  MUST leave every other line of the task list byte-identical, in the same order, with the file's
  line-ending convention and trailing-newline state preserved. This is the existing guarantee of that
  operation and this feature MUST NOT weaken it.
- **FR-017**: The document MUST have exactly the target line and its terminator removed. No other
  line may be added, removed, reordered, reindented, reflowed, or altered by a single byte —
  including blank lines adjacent to the removed line, indented content beneath it, other task lines'
  completion characters, and frontmatter.
- **FR-018**: The removal MUST be performed as a splice at a recorded position, never by re-rendering
  the document and never by locating the line by text match.
- **FR-019**: The document's line-ending convention and trailing-newline state MUST be preserved.
- **FR-020**: A parse failure or an unexpected shape anywhere in this path MUST NEVER truncate a file
  or lose a line. When the operation cannot be completed safely, nothing is written.

**Drift and refusal**

- **FR-021**: When the task id resolves to no task record and the task list contains at least one
  line that could not be parsed, the deletion MUST be refused, nothing MUST be written to either
  file, and the message MUST name the unreadable line and tell the user to repair it. choom cannot
  distinguish "this task was deleted" from "this task is currently unreadable", and MUST NOT remove
  the user's document line on a guess.
- **FR-022**: An unparseable line in the task list MUST NOT prevent the deletion of a task whose id
  *does* resolve. One broken line never breaks the file.
- **FR-023**: When the task id matches more than one task record, the deletion MUST be refused,
  nothing written, and the conflicting line numbers named.
- **FR-024**: When the editor is scoped to a task's own body and the target line is a task line for
  that same task, the deletion MUST be refused, nothing written, and the reason stated.
- **FR-025**: When the same task is mirrored on another line of the same document, only the cursor's
  line is removed. The remaining line MUST be reported in the status bar as still pointing at a task
  that no longer exists.
- **FR-026**: Task lines for the same task in *other* documents MUST NOT be read or written. This
  feature opens no file the user does not have open.
- **FR-027**: Every failure MUST be reported in the status bar naming what went wrong and what to do
  about it, and MUST leave the editor's text as the user last saw it.

**Unsaved editor state**

- **FR-028**: `ctrl+t` MUST NOT refuse because the editor has unsaved changes, and MUST NOT operate
  on the buffer alone. On confirmation the document is written, so both halves of the deletion are
  durable in the same gesture. This matches `/task`, `/link`, and `/ai`, which all commit the
  document before touching the task list.
- **FR-029**: Writing the document as part of this gesture MUST go through the ordinary save path,
  including stamping `updated` in frontmatter and reconciling every other task line's completion
  state. Removing a task line is a user edit to the document, not a background sync.
- **FR-030**: Unsaved edits elsewhere in the buffer are saved along with the deletion. The
  confirmation is therefore the last point at which the whole gesture can be abandoned with no effect
  (FR-014).
- **FR-031**: When the document write fails after the task record has been removed, the task stays
  deleted, the buffer keeps the line removed and remains marked unsaved, and the failure is named.
  Nothing the user typed is lost.

**Aftermath**

- **FR-032**: After a successful deletion the editor MUST report what happened in the status bar and
  MUST place the cursor sensibly on the line that now occupies the removed line's position (or the
  end of the document when the removed line was last), with no scroll jump.
- **FR-033**: The deleted task MUST NOT appear in the Tasks collection the next time it is rendered.
- **FR-034**: A completed task MUST be deleted on exactly the same terms as an incomplete one.
  Deletion today is removal of the record, not a mark, a move, or an archive; there is no trash and
  nothing to restore from. This is a statement of today's behaviour, not a constraint on it — see
  Dependencies.

### Interface parity (constitution Principle II)

**This feature requires no CLI change, and adds no CLI command.** That is a conclusion, not an
omission, and it rests on the operation decomposing into three parts:

| Part | CLI answer today |
| --- | --- |
| Delete a task record by id | `choom task delete <id> --force`, shipped, non-blocking, `--force` instead of a prompt |
| Remove a checklist line from a markdown document | The assistant edits the markdown body directly — the workflow the constitution's own rationale for Principle II names, and the reason the CLI has no line-editing surface at all |
| Do both in one gesture, with the cursor naming which line | Inherently interactive: the cursor *is* the argument. There is no id for "the line I am looking at" |

So the capability is available in both interfaces in the form each interface is designed to offer.
What this feature adds is a keystroke that composes two operations both front-ends already have, and
the composition itself is the interactive part.

Two consequences are recorded explicitly rather than left implicit:

- **`choom task delete` keeps its current behaviour**: it removes the task record and leaves any task
  lines in documents pointing at nothing, which reconcile-on-open already reports as a dead link.
  Changing it to hunt down and edit documents would make a task deletion write to files the caller
  never named, and it is out of scope here.
- **The asymmetry that leaves is intentional.** `ctrl+t` removes the document line because the user
  pointed at that line. `choom task delete` does not, because nobody named a line. Both go through
  the same core deletion of the record.

### Layering (constitution Principle I)

The line between core and front-end for this feature:

**`choom.core` owns, callable with a string and a workspace, with no terminal, TTY, or event loop:**

- Deciding whether a given line of a given text is a task line, and which task it names. This reuses
  the existing task-line recogniser rather than adding a second definition (FR-005).
- Producing the document text with that line removed, byte-preserving — pure text in, text out, no
  filesystem.
- Removing the task record, through the existing by-id deletion.
- Deciding the outcome when the two sides disagree: task present, task genuinely absent, task list
  unparseable, id ambiguous, self-referential. Core returns which case occurred; core does not
  compose a sentence for a dialog.

**The TUI owns, and nothing more:**

- The `ctrl+t` binding, its footer entry, and the state gates on it.
- Reading the cursor's line number out of the widget.
- Raising the existing confirmation dialog and phrasing its question from the outcome core described.
- Splicing the returned text into the widget and restoring the cursor.
- Rendering the outcome in the status bar.

The test consequence, which is the point of the boundary: every rule in the Edge Cases section above
about what is and is not removed from a document is checkable against a string, with no terminal
involved.

### Key Entities

- **Task line (mirror)**: a checklist item in a document whose link names a task id. Already modelled;
  this feature adds no new field to it. It carries the id, the completion state, the line, and the
  position of its state character.
- **Deletion outcome**: what core determined and did — which case applied (deleted both, document
  line only, refused and why), the task's description for the confirmation, and the resulting
  document text. Not persisted anywhere.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Deleting a task line changes exactly two things on disk: that one line in the document
  (plus the frontmatter `updated` stamp any save makes) and that one task's record in the task list.
  A byte-level diff of both files shows nothing else, for every case in the Edge Cases section.
- **SC-002**: Across the full edge-case suite — blank lines above and below, nested indentation,
  indented continuation beneath, trailing prose, CRLF, no trailing newline, last line of file, only
  line of file — zero cases remove a line the user did not point at, and zero cases truncate a file.
- **SC-003**: `ctrl+t` on a line that is not a task line raises no dialog and writes no file, in
  100% of cases.
- **SC-004**: The complete gesture is two keystrokes: `ctrl+t`, then Enter. No mode to enter, no
  field to fill, no screen to leave and come back from.
- **SC-005**: Cancelling the confirmation leaves both files byte-identical, including when the editor
  had unsaved changes at the time.
- **SC-006**: A task deleted this way is absent from the Tasks collection the next time it renders,
  with no manual refresh.
- **SC-007**: Every refusal path (unparseable task list, duplicate id, self-referential body, failed
  write) leaves a message that names both the cause and the user's next step.

---

## Assumptions

- The cursor's line, not the selection, identifies the target. The editor is a plain text buffer and
  a multi-line selection has no meaning for a per-task operation.
- The user wants the task line gone entirely, not converted back to the prose it replaced. choom does
  not remember what a line said before `/task` rewrote it, and reconstructing it is not attempted.
- The confirmation is worth the keystroke even for a task created seconds ago. The gesture writes to
  two files and is not undoable across them, which is precisely the "something to lose" that
  Principle V reserves a dialog for.
- Saving the document as part of the gesture is acceptable and expected, because the three shipped
  in-editor commands that touch the task list already do exactly that.
- `ctrl+t` remains unbound by the terminal emulators choom targets. It carries no XOFF-style hazard
  of the kind that constrains `ctrl+s`.

---

## Out of Scope

- **Rebinding `ctrl+d`,** in the editor or anywhere else. Settled in refinement; see the header.
- **Changing `choom task delete` or the list view's `ctrl+d`** to also remove task lines from
  documents. Recorded above under Interface parity as a deliberate asymmetry.
- **Removing the same task's lines from other documents.** This feature writes only the document the
  user has open.
- **An undo, a trash, or a restore** for a deleted task. Deletion is removal, as it is everywhere
  else in choom today.
- **Bulk deletion** — a selection of task lines, or "delete every task from this document".
- **Anything from issue #43** (moving completed tasks to a separate file). See Dependencies.
- **A new dialog style, a new setting, or a new CLI surface.** None of the three is needed.

## Dependencies

- **Task lines and the task-line recogniser** (feature 009, inline task capture). This feature reuses
  that definition and must not fork it.
- **The by-id task deletion** used by `choom task delete` and the list view's `ctrl+d` (feature 011).
  Reused unchanged.
- **The single confirmation dialog** and **the editor pane** in both its inline and full-screen hosts
  (features 011 and 014). Reused unchanged.
- **Issue #43 (completed tasks stored outside `tasks.md`)** is in this same milestone and is
  deliberately neither depended on nor pre-empted. This feature states today's behaviour — deleting a
  task removes its record, whether or not it is completed (FR-034) — and defines `ctrl+t` as calling
  the same core deletion the rest of the product calls. If #43 later changes what deleting a
  completed task means, `ctrl+t` inherits that change with no edit here, because there is only one
  definition of deletion and this feature does not add a second.
