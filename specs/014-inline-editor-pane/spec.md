# Feature Specification: Editor Replaces the Preview Pane

**Feature Branch**: `014-inline-editor-pane`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Issue #57. you are 014"

**Source**: GitHub issue #57 "[Feature]: Editor replaces the preview pane instead of opening full-screen"
(milestone v0.0.3), split out of issue #32 where it was item 6. Pressing `e` on a highlighted item today
replaces the whole screen with an editor: the list, the scope pane, and the preview the user was reading
all disappear for the duration of an edit that is usually a line or two long.

**Builds on**: `004-viewing-editing` (the `list → preview → edit` state machine, the save and discard
keys, and the discard confirmation), `005-ui-layout-refresh` (the three-pane list screen with its
preview pane, the collection bar, and the status bar), `007-task-content-editing` (editing a task's
body through the same editor), `006-ai-assistant-invocation` (the in-editor assistant request and its
in-flight status), and `010-read-on-load` (the list refreshing from disk rather than from a session
snapshot).

**Sequenced with**: `011-ui-refinements`, which changes where the cursor lands when edit mode is entered
and replaces the confirmation dialog with a single-line bar. Both surfaces are reached from the editor
this feature moves. This spec assumes those changes exist and does not restate them.

---

## Overview

The interface is meant to be one screen — a filterable list and a preview pane, with `list → preview →
edit` as states of that screen. Every state honours that today except the last: the editor leaves the
screen behind entirely.

This feature makes edit mode a state of the list screen rather than a departure from it. The editor
takes over the preview pane's footprint, the list and the scope pane stay exactly where they were, and
the user returns to the same row they left without having to find it again.

Two boundaries are settled up front, both narrowing the change:

- **Full-screen reading is untouched.** `enter` on a highlighted document still opens the full-screen
  reading view, and pressing `e` from inside that view still opens a full-screen editor. There is no
  preview pane to take over there, and the user has already chosen a full-screen reading context.
- **Nothing about editing itself changes.** The same keys save, the same key discards, the same
  confirmation fires, and the same content is written to disk. Only where the editor appears changes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Edit a note without losing your place (Priority: P1)

A user is scanning the list, reading each record's preview as they move down it. They land on a note
that needs one more line. They press `e`; the editor appears where the preview was, with the list still
beside it and the same row still highlighted. They type the line, save, and the preview comes back with
their new line in it — they never left the list and never had to find their place again.

**Why this priority**: This is the whole point of the issue and the case the tool is optimised for — a
quick edit to something already on screen. It is also the largest share of edits.

**Independent Test**: Open the list, highlight a record with a visible preview, press `e`, and confirm
the list and scope pane remain visible while the editor occupies the preview pane. Type a line, save,
and confirm the same row is still highlighted and the preview shows the typed line.

**Acceptance Scenarios**:

1. **Given** a highlighted document in the list, **When** the user presses `e`, **Then** the editor
   appears in the preview pane's footprint and the list, the scope pane, and the collection bar remain
   visible and unchanged.
2. **Given** the inline editor is open, **When** the user types, **Then** the text appears in the pane
   and no keystroke reaches the list — the highlighted row does not move, the collection does not
   change, and no filter is started.
3. **Given** the inline editor is open with unsaved changes, **When** the user saves, **Then** the
   content is written, the editor closes, the preview pane returns showing the saved content, and the
   same record is still highlighted.
4. **Given** the inline editor is open with unsaved changes, **When** the user discards and confirms,
   **Then** the file is unchanged, the editor closes, and the same record is still highlighted with its
   previous content in the preview.
5. **Given** the inline editor has just closed by saving or discarding, **When** the user presses a list
   key such as a movement key, **Then** the list responds — keyboard control is back where it was.
6. **Given** a line of content wider than the preview pane, **When** it is displayed or typed in the
   inline editor, **Then** it wraps at the pane's current edge and no content requires horizontal
   scrolling to read.

---

### User Story 2 - Update a task's details in place (Priority: P2)

A user is working through the task list. They highlight a task, press `e`, and append "08-01 called,
left voicemail" to its details in the pane beside the list. They save, and the task list is still there
with the same task highlighted and the updated details in the preview.

**Why this priority**: Task details are the shortest edits of all — usually one dated line — so the cost
of a full context switch is highest here relative to the work being done. It ships after P1 only because
document editing is the more common entry point.

**Independent Test**: Open the Tasks collection, highlight a task, press `e`, type a line, save, and
confirm the task list stayed visible throughout and the same task is highlighted with its new details in
the preview.

**Acceptance Scenarios**:

1. **Given** a highlighted task, **When** the user presses `e`, **Then** the editor opens on that task's
   details in the preview pane, with the task list still visible beside it.
2. **Given** the inline editor is open on a task's details, **When** the user saves, **Then** the
   details are written, the same task is still highlighted, and the preview shows the updated details.
3. **Given** the inline editor is open on a task's details, **When** the user discards, **Then** the
   task's details are unchanged and the task is still highlighted.
4. **Given** a task whose details are being edited inline, **When** the save fails, **Then** the reason
   is reported and the typed content is still in the editor rather than lost.

---

### User Story 3 - Full-screen reading keeps its full-screen editor (Priority: P3)

A user presses `enter` on a record to read it in full screen. Partway down they decide to change
something and press `e`. The editor opens full-screen, exactly as it does today, because that is the
context the user chose when they opened the record.

**Why this priority**: This is the scope boundary that keeps the change small, and it is the story most
at risk of being broken by accident while implementing P1. It carries no new behaviour — it is the
existing behaviour, held.

**Independent Test**: Press `enter` on a record, press `e` inside the full-screen view, and confirm the
editor is full-screen; save and confirm the user is returned to the full-screen reading view.

**Acceptance Scenarios**:

1. **Given** a highlighted document in the list, **When** the user presses `enter`, **Then** the
   full-screen reading view opens as it does today.
2. **Given** the full-screen reading view, **When** the user presses `e`, **Then** a full-screen editor
   opens rather than an inline one.
3. **Given** a full-screen editor entered from the reading view, **When** the user saves or discards,
   **Then** they are returned to the same place they would reach today.

---

### User Story 4 - Creating a record keeps the list in view (Priority: P4)

A user creates a new note, meeting, or daily note from the list screen. The editor opens on the new
record in the preview pane, with the list still visible beside it. They write, save, and the new record
is highlighted in the list they never left.

**Why this priority**: Creation opens the same editor from the same screen, so leaving it full-screen
would mean the editor appears in two different places depending on how the user got there — the exact
inconsistency this feature exists to remove. It is last because a creation flow is already a deliberate,
slower act than a quick edit.

**Independent Test**: Create a note from the list screen, confirm the editor opens in the preview pane
with the list visible, save, and confirm the new record is highlighted in the list.

**Acceptance Scenarios**:

1. **Given** the list screen, **When** the user creates a note, a meeting, or a daily note, **Then** the
   editor for the new record opens in the preview pane with the list still visible.
2. **Given** the editor opened for a newly created record, **When** it is open, **Then** the list shows
   that record and highlights it, so the pane and the list agree about what is being edited.
3. **Given** the editor opened for a newly created record, **When** the user saves or discards, **Then**
   the record is highlighted in the list, with the same outcome on disk as today.

---

### Edge Cases

- **The terminal is resized while the editor is open.** The editor re-wraps to the pane's new width,
  every typed character survives the resize, and the cursor stays on the same character of the same
  line. Nothing is truncated at either width.
- **The preview pane is very narrow.** On a terminal narrow enough that the pane is only a few columns
  wide, the editor still accepts input and still wraps rather than scrolling sideways. It never overlaps
  the list or the scope pane.
- **A line that cannot be wrapped at a space.** A long URL, a path, or an unbroken run of characters
  wider than the pane wraps within the pane rather than extending past it or being cut off.
- **The list refreshes from disk while the editor is open.** The list screen stays live behind the
  editor, so a refresh may find new, changed, or removed records. The refresh must not move keyboard
  focus, must not change what the editor is editing, and must not alter a single character of the
  buffer.
- **The record being edited is removed or changed on disk mid-edit.** The user's typed content is never
  discarded on their behalf; a save that cannot be applied reports why and leaves the content in the
  editor, exactly as it does today.
- **Quitting with unsaved work.** `ctrl+q` while the inline editor holds unsaved changes behaves the
  same as it does for the full-screen editor — the same single confirmation, and no confirmation when
  nothing would be lost.
- **The discard confirmation.** It appears while the inline editor is open, and declining returns to the
  editor with the buffer intact rather than to the list.
- **An assistant request is in flight.** The in-flight status and its cancel key work in the inline
  editor as they do full-screen, and the request's result lands in the pane's buffer.
- **Nothing is highlighted.** Pressing `e` with an empty list or no highlighted row does nothing and
  reports nothing new — the same non-event it is today.
- **The links section of the preview pane.** While the editor holds the pane, the links section is not
  shown and its keys are not active; `b` is typed into the buffer rather than opening backlinks. Closing
  the editor restores the pane's normal behaviour.
- **A second edit request while the editor is open.** Keys that would open an editor are text input
  while one is already open; the tool never stacks a second editor over the first.

## Requirements *(mandatory)*

### Functional Requirements

**Where the editor appears**

- **FR-001**: Entering edit mode from the list screen MUST render the editor within the preview pane's
  footprint, leaving the collection bar, the scope pane, and the list pane visible and in place.
- **FR-002**: Every route into edit mode from the list screen MUST use the pane — editing a highlighted
  document, editing a highlighted task's details, creating a note, creating a meeting, opening the daily
  note, and following a link that resolves to an editable target.
- **FR-003**: The inline editor MUST replace the preview pane's contents for as long as it is open,
  including the links section, and MUST NOT overlay, float above, or resize the list or scope panes.
- **FR-004**: Content MUST wrap at the current edge of the preview pane, and no editing operation may
  require horizontal scrolling to see a line.
- **FR-005**: A change in the pane's width, including one caused by a terminal resize, MUST re-wrap the
  content without altering, truncating, or reordering it, and without moving the cursor off the
  character it was on.

**Who owns the keyboard**

- **FR-006**: While the inline editor is open it MUST retain keyboard control until the user leaves it
  through the established editor keys.
- **FR-007**: While the inline editor is open, keys that act on the list — movement, collection
  switching, filtering, opening, toggling, deleting, backlinks — MUST NOT act on the list. Printable
  keys MUST be inserted into the buffer.
- **FR-008**: While the inline editor is open, the command bar MUST NOT be openable.
- **FR-009**: While the inline editor is open, the status bar MUST show the editor's bindings in place
  of the list's, and MUST return to the list's bindings when the editor closes.
- **FR-010**: `ctrl+c` MUST remain unbound in the inline editor on the same terms it is elsewhere,
  except where an in-flight assistant request already claims it under `006-ai-assistant-invocation`.
- **FR-011**: When the inline editor closes, keyboard control MUST return to the list without the user
  pressing anything further.

**Entering and leaving**

- **FR-012**: Saving from the inline editor MUST write the same content to the same place as saving from
  the full-screen editor does today.
- **FR-013**: On leaving the inline editor by any route, the list MUST still highlight the record that
  was highlighted when the editor opened, and the preview pane MUST show that record's current content.
- **FR-014**: Discarding unsaved changes from the inline editor MUST raise the same confirmation any
  other discard raises; declining MUST return to the editor with the buffer unchanged, and confirming
  MUST close the editor and change nothing on disk.
- **FR-015**: A save that fails MUST report the reason where the user is looking and MUST leave the
  editor open with the typed content intact.
- **FR-016**: Where edit mode is entered for a newly created record, the list MUST show and highlight
  that record while its editor is open.

**What does not change**

- **FR-017**: `enter` on a highlighted document MUST continue to open the full-screen reading view,
  unchanged.
- **FR-018**: Pressing `e` inside the full-screen reading view MUST continue to open a full-screen
  editor, and leaving it MUST return the user where it does today.
- **FR-019**: The editor's capabilities MUST be identical inline and full-screen — the same keys, the
  same assistant request behaviour, the same cursor placement rule on entry, and the same content
  written on save.
- **FR-020**: This feature MUST NOT change any command-line behaviour, any file format, or what any
  record contains.

**Living beside a list that refreshes**

- **FR-021**: A background refresh of the list while the inline editor is open MUST NOT modify the
  buffer, move the cursor, take keyboard control, or change which record the editor is editing.
- **FR-022**: If the record being edited stops appearing in the list while its editor is open, the
  editor MUST stay open and the user's content MUST remain editable and savable on the existing terms
  for a record that has changed underneath.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In every edit started from the list screen, the record list remains visible for the whole
  duration of the edit.
- **SC-002**: A user who edits a record from the list returns to that same record highlighted, in 100%
  of edits, without pressing any key beyond the one that closed the editor.
- **SC-003**: Editing a record and returning to the list costs the same two keystrokes it does today —
  one to enter, one to leave — with no added confirmation or navigation step.
- **SC-004**: No keystroke typed into the editor changes the list's highlighted row, its collection, or
  its filter.
- **SC-005**: At every terminal width the tool supports, no line in the editor is cut off horizontally
  or needs sideways scrolling to read.
- **SC-006**: Content typed into the editor survives a terminal resize with every character intact, 100%
  of the time.
- **SC-007**: Reading a record full-screen and editing it there behaves exactly as it did before this
  feature, verified by the existing behaviour continuing to hold.

## Assumptions

- The editor opened for a newly created record, or for a link that resolves to an editable target, uses
  the pane on the same terms as `e` does. The issue settles `e` explicitly; extending it to the other
  routes out of the same screen is the reading that leaves one editor presentation per screen rather
  than two.
- "The usual keyboard commands" in the issue means the editor's existing save, save-and-close, and
  discard keys. This feature adds no key and renames none.
- Cursor placement on entering edit mode, and the style of the discard confirmation, are settled by
  `011-ui-refinements` and are inherited here rather than re-specified.
- The preview pane is present at every terminal width the tool supports, so there is no width at which
  edit mode has nowhere to render and would need a full-screen fallback.
- The list's periodic refresh continues to run while the inline editor is open, since the list screen is
  no longer covered. FR-021 governs what that refresh may and may not disturb; whether the refresh is
  paused instead is an implementation decision, provided the observable rule holds.
- No workspace, file format, or command-line change is required by this feature.

## Dependencies and Relationships

- **Issue #32 (`011-ui-refinements`)**: items 1 and 5 — cursor placement on entering edit mode, and the
  confirmation style — surface from the editor this feature moves. If `011` lands first, this feature
  inherits both; if it lands second, its acceptance criteria apply to the editor wherever it renders.
- **Issue #51 (`010-read-on-load`)**: already landed. It is why the list behind the editor reads from
  disk rather than a snapshot, and therefore why FR-021 and FR-022 exist at all.
- **`004-viewing-editing`**: owns the `list → preview → edit` state machine this feature completes, and
  the discard confirmation this feature keeps.
- **`007-task-content-editing`**: task-body editing is the second entry point into the editor and gets
  the same treatment (User Story 2).
- **`006-ai-assistant-invocation`**: the in-editor assistant request and its in-flight status must keep
  working in the pane, including its narrow claim on `ctrl+c`.

## Out of Scope

- Editing from inside the full-screen reading view. It stays full-screen (User Story 3).
- Any change to the editor's key bindings, its assistant integration, or what it writes.
- A floating, overlaid, or resizable editor pane, and any user-adjustable split between list and pane.
- Editing more than one record at a time, or keeping an editor open while navigating the list.
- Any command-line change; the CLI never opens an editor.
