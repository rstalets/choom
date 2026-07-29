# Feature Specification: Viewing and Editing

**Feature Branch**: `004-viewing-editing`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "requirements.md feature 3.5"

**Source**: `REQUIREMENTS.md` §3.5, plus the parts of §4.4 (re-parse only the changed file), §4.5
(edit-state presentation and key-binding hazards), §4.6 (frontmatter timestamps), and §4.7 that this
feature needs to be shippable. §3.5 is a terminal-interface feature end to end, and this spec adds no
command-line surface — see Assumptions for why that does not breach the two-front-doors rule.

**Builds on**: Features `001-meeting-notes` and `002-general-notes`, which delivered the workspace,
the frontmatter schema, the list-and-preview screen, the collection menu, and the command-line
conventions. Both deliberately deferred the edit half of §3.5 and forbade the preview footer from
advertising an edit action until this feature landed. This feature removes that restriction and
completes the list → preview → edit state machine.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fix what you are reading, without leaving (Priority: P1)

The user is reading yesterday's standup and spots a line that is wrong, or wants to add the decision
that got made after the call ended. One keystroke turns the page they are reading into a page they
can type into. One more keystroke puts it on disk. They never chose a file, never launched an
editor, and never left the tool.

**Why this priority**: The preview half of §3.5 already ships. Without the edit half, endpaper can
create a document and show it, but the user has to leave for another program to change a single
character — which breaks the premise that the tool disappears into the twenty seconds around a
meeting. This story alone makes captured notes maintainable and is a complete slice on its own.

**Independent Test**: Open any existing meeting or note from the list, press the edit key, type,
save, and confirm the file on disk matches the buffer exactly and the preview shows the new content.

**Acceptance Scenarios**:

1. **Given** a document open in preview, **When** the user presses `e`, **Then** an editing area
   appears containing the document's raw markdown including its frontmatter, with the cursor ready
   for input and no content elided or reformatted.
2. **Given** the edit state with typed changes, **When** the user presses `ctrl+o`, **Then** the file
   on disk becomes byte-identical to the buffer apart from the `updated` frontmatter stamp, and the
   user remains in the edit state with the cursor position preserved.
3. **Given** the same state, **When** the user presses `ctrl+s` instead, **Then** the result is
   identical to pressing `ctrl+o` in every respect.
4. **Given** the edit state with typed changes, **When** the user presses `ctrl+x`, **Then** the file
   is saved and the user lands in the preview state showing the new content rendered.
5. **Given** a document saved from the edit state, **When** the user returns to the list, **Then**
   the row for that document reflects any title, type, or tag change made in the buffer, and no other
   row changed.
6. **Given** a document whose frontmatter carries `created` and `updated`, **When** it is saved,
   **Then** `updated` reflects the time of the save and `created` is unchanged.
7. **Given** a document opened in preview, **When** the user presses `esc` without entering the edit
   state, **Then** they return to the list and the file's bytes and modification time are unchanged.

---

### User Story 2 - Back out without losing a keystroke (Priority: P2)

The user starts editing, changes their mind, and presses `esc`. If there is work to lose, endpaper
asks. If there is nothing to lose, it does not — because a dialog that fires when nothing is at stake
is a dialog users learn to dismiss without reading, which disarms it for the one time it matters.

**Why this priority**: It is what makes the edit state safe to enter casually, and casual entry is
the entire point of a one-keystroke transition. It depends only on Story 1.

**Independent Test**: Enter the edit state four ways — with changes, without changes, after a save,
and after cancelling a discard — press `esc` in each, and confirm the prompt appears exactly when
unsaved changes exist and that the file on disk is untouched whenever the user discards.

**Acceptance Scenarios**:

1. **Given** the edit state with unsaved changes, **When** the user presses `esc`, **Then** a modal
   confirmation appears offering Discard and Cancel, and nothing is written.
2. **Given** that confirmation, **When** the user chooses Cancel, **Then** they return to the edit
   state with every character of the buffer and the cursor position intact.
3. **Given** that confirmation, **When** the user chooses Discard, **Then** they return to the
   preview state and the file on disk is byte-identical to what it was before the edit state was
   entered.
4. **Given** the edit state with no changes made, **When** the user presses `esc`, **Then** they
   return to preview immediately with no dialog.
5. **Given** the edit state where changes were made and then saved with `ctrl+o`, **When** the user
   presses `esc`, **Then** no dialog appears, because the save cleared the unsaved-changes state.
6. **Given** a buffer that the user edited and then manually returned to its original text, **When**
   the user presses `esc`, **Then** no dialog appears, because the buffer matches the file.

---

### User Story 3 - A buffer that reads like prose (Priority: P3)

The user is looking at their own words, not at source code. Long paragraphs wrap into the pane
instead of running off the right edge, the gutter tells them where they are, and every key that does
anything is written along the bottom of the screen. Nothing is hidden and nothing has to be guessed.

**Why this priority**: These are the properties that make the edit state usable for more than a
one-character correction. They are separable from the save-and-discard machinery and can be verified
on their own, but they are worth less without it.

**Independent Test**: Open a document with frontmatter, a paragraph far longer than the pane is wide,
and a hundred lines of body, then check the first gutter number, the numbering of wrapped rows, the
absence of horizontal scrolling, and the footer contents.

**Acceptance Scenarios**:

1. **Given** a document open in the edit state, **When** the user looks at the left gutter, **Then**
   line 1 is the opening `---` of the frontmatter and numbering continues unbroken through the body.
2. **Given** a paragraph wider than the editing pane, **When** it is displayed, **Then** it wraps onto
   further rows, the pane never scrolls horizontally, and the wrapped rows carry no gutter number.
3. **Given** the edit state, **When** the user reads the footer, **Then** every binding active in that
   state is listed, with `ctrl+o` shown as the save key.
4. **Given** the preview state, **When** the user reads the footer, **Then** the edit key and the key
   that returns to the list are both listed, and no edit-state-only binding is shown.
5. **Given** any of the three states, **When** the user presses a key the footer does not advertise,
   **Then** nothing outside that state's documented behaviour happens.

---

### Edge Cases

- **The file is read-only, or the disk is full.** The save fails, the user is told plainly, and they
  are left in the edit state with the buffer intact so their work can still be copied out. The file
  on disk is never left truncated or half-written.
- **The file was deleted or moved outside endpaper while it was open.** Saving reports what happened
  rather than silently recreating the file at a stale path, and the buffer is preserved.
- **The file was changed on disk by another program while it was open.** The save overwrites it.
  Detecting and resolving simultaneous edits is out of scope for v0.0.1 (`REQUIREMENTS.md` §5).
- **The user edits the frontmatter itself.** The buffer is the truth: whatever fields it contains are
  what gets written, with only `updated` stamped by endpaper.
- **The user deletes or breaks the frontmatter.** The bytes are written as typed, the `updated` stamp
  is skipped rather than guessed at, a warning is surfaced, and the file is not repaired or reverted.
  On the next scan the document is skipped with a warning, exactly as a hand-broken file already is,
  and is never rewritten or deleted.
- **The user saves an empty buffer.** The file becomes empty. Emptying a buffer in an interactive
  editor takes deliberate keystrokes and is undone by discarding rather than saving, so no extra
  confirmation is warranted here.
- **A file with Windows line endings, or with no trailing newline.** Both conventions survive a save
  unchanged.
- **A document that the active filter or collection no longer matches after the edit** — a tag
  removed, a title rewritten. Returning to the list re-applies the filter; if the document no longer
  matches, the selection moves to the nearest remaining row rather than leaving nothing selected.
- **A very large document.** It opens, scrolls, and saves without the interface becoming unresponsive.
- **Text that is not plain ASCII** — accents, emoji, CJK, right-to-left script. It is displayed,
  edited, and written back intact, with the gutter still numbering real lines correctly.
- **The terminal window is resized, or is very small, while editing.** The layout adapts, and the
  buffer, cursor position, and unsaved-changes state all survive.
- **A terminal with legacy flow control**, where `ctrl+s` freezes output instead of reaching the
  application. The canonical save key still works, because the footer advertises `ctrl+o`.
- **A document last written by something other than endpaper** — hand-edited in another editor, or
  rewritten in place by an AI assistant. It opens, edits, and saves like any other, and its stale
  `updated` value is left as found until the next save through endpaper stamps it.

## Requirements *(mandatory)*

### Functional Requirements

**The three states**

- **FR-001**: The interface MUST have exactly three states — list, preview, and edit — and every
  transition between adjacent states MUST be a single keystroke.
- **FR-002**: `enter` on a list row MUST open that document in the preview state, showing rendered
  markdown rather than raw source.
- **FR-003**: `e` in the preview state MUST enter the edit state on the same document.
- **FR-004**: `esc` in the preview state MUST return to the list without writing anything.
- **FR-005**: `esc` in the edit state MUST return to the preview state, subject to the unsaved-changes
  check in FR-016.
- **FR-006**: The edit state MUST be reachable only from the preview state, so that reading remains
  the default and editing remains the exception.
- **FR-007**: On returning to preview after a save, the preview MUST show the saved content, not the
  content that was displayed before editing.
- **FR-008**: These transitions MUST behave identically for every document opened from the meetings
  collection and from the notes collection, including daily notes.

**The edit buffer**

- **FR-009**: The edit state MUST present the document's raw markdown, including its frontmatter, in
  a plain text editing area, with no field hidden, reordered, or reformatted on entry.
- **FR-010**: Line numbers MUST be shown in a gutter on the left of the editing area, numbering the
  whole buffer, so that line 1 is the opening `---` of the frontmatter.
- **FR-011**: Lines longer than the pane MUST wrap onto further display rows rather than scrolling
  horizontally, and wrapped continuation rows MUST NOT carry a gutter number.
- **FR-012**: Pressing `tab` in the editing area MUST NOT insert a literal tab character into the
  buffer.
- **FR-013**: The buffer MUST preserve any character the user types, including non-ASCII text, and
  MUST NOT normalise, transliterate, or strip it on entry, display, or save.

**Saving**

- **FR-014**: `ctrl+o` MUST save the buffer to disk and leave the user in the edit state with the
  cursor position and scroll position preserved. `ctrl+x` MUST save and return to the preview state.
- **FR-015**: `ctrl+s` MUST be bound as an additional alias for save, and `ctrl+o` MUST be the binding
  shown in the footer, because `ctrl+s` cannot be guaranteed to reach the application.
- **FR-016**: A save MUST write the buffer's content exactly, changing only the `updated` frontmatter
  field.
- **FR-017**: A save MUST set `updated` to the time of the save and MUST NOT alter `created`.
- **FR-018**: When the saved buffer has no parseable frontmatter, the content MUST still be written
  as typed, the `updated` stamp MUST be skipped rather than inferred, and a warning MUST be surfaced.
- **FR-019**: A save MUST preserve the file's existing line-ending convention and the presence or
  absence of a final newline.
- **FR-020**: A save that cannot complete MUST leave the file exactly as it was — never truncated,
  never partially written — MUST report the failure, and MUST leave the user in the edit state with
  the buffer intact.
- **FR-021**: A successful save MUST re-read and re-parse only the file that changed, and MUST NOT
  rescan the workspace.
- **FR-022**: After a save, the list MUST reflect any change to the document's title, type, or tags
  without a manual refresh, and MUST leave every other row unchanged.
- **FR-023**: A save MUST NOT modify, move, or rename any file other than the one being edited, and
  MUST NOT move a document to match a partition its edited date now implies.

**Discarding**

- **FR-024**: `esc` in the edit state MUST prompt only when the buffer differs from the file on disk.
- **FR-025**: When the buffer matches the file, `esc` MUST return to preview immediately and silently.
  This MUST hold after a save, and MUST hold when the user has manually undone their own changes.
- **FR-026**: When the buffer differs, `esc` MUST present a modal confirmation offering Discard and
  Cancel.
- **FR-027**: Cancel MUST return to the edit state with the buffer content and cursor position intact.
- **FR-028**: Discard MUST return to the preview state and MUST leave the file on disk byte-identical
  to its state when the edit state was entered.
- **FR-029**: No transition out of the edit state may write to disk except the explicit save keys.

**Footer and bindings**

- **FR-030**: The footer MUST display every binding active in the current state at all times, in all
  three states. No key that does something may be hidden.
- **FR-031**: The footer MUST NOT advertise a binding that does nothing in the current state.
- **FR-032**: The preview state MUST advertise the edit key, replacing the restriction that features
  001 and 002 placed on it while the edit state was undelivered.
- **FR-033**: The terminal's reserved interrupt and quit keys MUST NOT be bound to any action in this
  feature, and MUST retain their existing behaviour in all three states.
- **FR-034**: No binding in this feature may require a modifier other than `ctrl`, and no interface
  text or documentation may promise a binding that a terminal emulator would intercept before the
  application sees it.
- **FR-035**: The fallback for a terminal whose flow control swallows `ctrl+s` MUST be documented for
  the user.

**Command-line surface**

- **FR-036**: This feature MUST add no command-line surface. Interactive text entry is inherently
  interactive and has no command-line form, and the file-content commands in `REQUIREMENTS.md` §4.2
  are independent of the edit state — see Assumptions.
- **FR-037**: The edit state MUST NOT become a prerequisite for any command-line capability, so that
  the §4.2 commands can be specified and delivered separately, before or after this feature, without
  either depending on the other.

**Never lose the user's words**

- **FR-038**: No operation in this feature may drop, reorder, or truncate a line the user did not
  change.
- **FR-039**: A document whose frontmatter the user has broken MUST be left exactly as written, MUST
  be skipped with a warning on the next scan rather than raising, and MUST NOT prevent any other
  document from listing.
- **FR-040**: Warnings MUST go to the interface's existing warning surface — never into a document,
  and never silently swallowed.
- **FR-041**: A document modified outside endpaper — by hand, by another program, or by an AI
  assistant editing the file directly — MUST open, preview, edit, and save exactly as one endpaper
  itself last wrote. Nothing in this feature may require that a document have been last written by
  endpaper.

**Platform**

- **FR-042**: Windows, macOS, and Linux MUST be supported, with Windows treated as a primary target,
  and the bindings MUST be verified on the target terminals before release.
- **FR-043**: Workspace paths containing spaces and non-ASCII characters MUST work for every
  operation in this feature.
- **FR-044**: No operation in this feature may require network access.

### Key Entities

- **Document**: A meeting or a note — the thing being viewed and edited. Already defined by features
  001 and 002; this feature adds no field to it and changes only its `updated` timestamp.
- **Interface state**: Which of list, preview, or edit the user is currently in. Determines what the
  footer advertises and what each key does.
- **Edit buffer**: The in-memory text the user is typing into, holding the document's raw markdown
  including frontmatter. It exists only while the edit state is active and is authoritative over the
  file only when the user saves.
- **Unsaved-changes state**: Whether the buffer currently differs from the file on disk. Set by
  typing, cleared by a save, and the sole trigger for the discard confirmation.
- **Save operation**: The single shared action that writes a buffer's content to a document, stamps
  `updated`, preserves `created` and the file's line-ending convention, and re-parses that one file.
  Invoked by the interface's save keys. It is defined as a core operation taking content and a
  target, rather than as interface behaviour, so that a later command-line writer can reuse it
  unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a list row, a user can correct a typo and have it on disk in three keystrokes —
  open, edit, save — with no file chooser, no editor launch, and no configuration.
- **SC-002**: A save is reflected on disk and in the preview within one second for a document of any
  size the tool targets.
- **SC-003**: Across any sequence of 1,000 edit, save, and discard operations, no character the user
  typed and saved is lost or altered, and no file other than the one being edited changes.
- **SC-004**: Every discard leaves the file byte-identical to its pre-edit state, verified by
  comparing the file before and after in 100% of discard cases.
- **SC-005**: The unsaved-changes confirmation appears in 100% of cases where unsaved work exists and
  in 0% of cases where it does not, including immediately after a save and after the user has undone
  their own changes.
- **SC-006**: `created` is unchanged and `updated` advances on 100% of saves, from both front doors.
- **SC-007**: A document edited on one platform and saved on another retains its line-ending
  convention, verified for both conventions in both directions.
- **SC-008**: Every key that does anything in a given state appears in that state's footer, verified
  by comparing the footer against the state's bindings for all three states.
- **SC-009**: A save that fails because the file cannot be written loses nothing: the buffer is still
  present and the file on disk is unchanged, in 100% of induced failure cases.
- **SC-010**: A document rewritten in place outside endpaper — by hand or by an AI assistant — opens,
  edits, and saves indistinguishably from one endpaper wrote itself, verified for a document whose
  body, frontmatter field order, and line endings were all changed externally.

## Assumptions

- **The preview state already exists.** Features 001 and 002 delivered rendered markdown preview,
  `enter` to open it, and `esc` to return to the list. This feature restates those transitions
  because §3.5 defines the state machine as a whole, but implements only the edit half and the
  footer change that unblocks it.
- **This feature adds no command-line surface, and that does not breach the two-front-doors rule.**
  The constitution requires parity *unless* a behaviour is inherently interactive or inherently
  non-interactive. Interactive text entry is the first kind and has no command-line form. The
  file-content commands in §4.2 — `read`, `write`, `append` — are the second kind: they exist for
  stdin piping, and they are not the peer of the edit state.

  An AI assistant does not need them in order to change a document. It reaches for the command line
  to **create** documents, because creation owns identifier generation, slug and collision rules,
  date partitioning, and frontmatter — none of which an assistant should reinvent. To **modify** an
  existing document it opens the markdown file and edits it directly, the same way it edits any file
  in a repository. It cannot edit interactively at all, so there is nothing about the edit state to
  mirror. §4.2's commands remain real, unclaimed requirements; they are independent surface and
  belong in their own spec rather than riding along with §3.5.
- **The buffer wins on frontmatter.** The edit state shows raw markdown including frontmatter, so the
  user can change any field. Whatever they type is what gets written; endpaper stamps `updated` and
  otherwise does not police the fields. This is consistent with the tool's premise that the files are
  the user's own to hand-edit.
- **`updated` is a local-time timestamp** with the same shape as the one already written at creation.
- **Simultaneous edits are not detected.** `REQUIREMENTS.md` §5 makes the sync tool's own
  conflict-copy behaviour the answer for two copies edited at once, so a save does not check whether
  the file changed underneath it.
- **endpaper does not police `updated` for changes made outside it.** A document edited by hand or
  rewritten by an assistant carries a stale `updated` until the next save through endpaper stamps it.
  Correcting it would mean watching the filesystem or keeping a second copy of state, and §3.5 asks
  for neither. The file's own modification time remains the record of when it last changed.
- **The save operation is specified as core behaviour, not interface behaviour**, so that the §4.2
  writer can later reuse it and produce byte-identical results without the edit state being involved.
- **Line numbers count real lines, not display rows**, so a wrapped paragraph occupies one number.
- **No undo history is specified beyond what the editing area provides natively**; the discard
  confirmation, not an undo stack, is the guarantee against losing work.
- **Python 3.11 or newer**, per `REQUIREMENTS.md` §4.1.

## Dependencies

- Feature `001-meeting-notes` for the workspace, the frontmatter schema, the list-and-preview screen,
  the footer, and the warning surface.
- Feature `002-general-notes` for notes and daily notes as a second collection, the collection menu,
  and the per-collection state that the edit state must leave undisturbed.
- The document scan and single-file re-parse already used to keep the list current.
- No new external dependency: the editing area is provided by the interface toolkit already in use,
  and no external editor, no syntax highlighter, and no search binary is introduced.

## Out of Scope

Deferred, and explicitly not delivered here:

- The file-content commands `endpaper read`, `endpaper write`, and `endpaper append`
  (`REQUIREMENTS.md` §4.2). They remain unclaimed by any feature and still need a spec, but they are
  stdin-piping surface rather than the peer of the edit state, and an assistant modifies documents by
  editing the markdown directly — so nothing here depends on them and they gain nothing from shipping
  together. See Assumptions.
- Editing `tasks.md` through the edit state. §3.5 applies to what is opened from the meetings and
  notes collections; tasks are toggled, not edited, in v0.0.1, and feature `003-tasks` deferred this
  on the same boundary.
- Creating a task from inside a note or meeting (`REQUIREMENTS.md` §5)
- Syntax highlighting in the editor (§5)
- An embedded or external editor, and any `$EDITOR` integration (§4.5)
- Conflict detection or resolution for simultaneous edits (§5)
- Deleting or renaming a document from the interface — no requirement asks for it
- Search (`endpaper find`, §4.4) and named workspaces (§3.4)
- A find-and-replace, a spell checker, or any editing affordance beyond typing, wrapping, and line
  numbers
- Everything else listed in `REQUIREMENTS.md` §5
