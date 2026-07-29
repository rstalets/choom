# Feature Specification: Viewing and Editing

**Feature Branch**: `004-viewing-editing`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "requirements.md feature 3.5"

**Source**: `REQUIREMENTS.md` §3.5, plus the parts of §4.2 (`read`, `write`, `append`), §4.4 (re-parse
only the changed file), §4.5 (edit-state presentation and key-binding hazards), §4.6 (frontmatter
timestamps), and §4.7 that this feature needs to be shippable.

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

### User Story 4 - An assistant reads and rewrites the same files, with no terminal (Priority: P4)

An AI assistant working in the user's workspace pulls a note's raw markdown, rewrites it, and writes
it back — the same read-refine-write loop it already runs against a codebase. It never gets an
editor, never gets a prompt, and never has to guess whether the write landed.

**Why this priority**: The constitution requires that any behaviour in one front door exist in the
other. Interactive text entry is inherently interactive and has no command-line form, but reading and
replacing a document's content is exactly the peer, and no other feature delivers it. It is
independently valuable to an assistant even if the terminal interface's edit state is never used.

**Independent Test**: With no terminal attached and all output redirected, read a document, pipe
modified content back through the write command, and compare the resulting file against the file the
terminal interface produces from the same buffer.

**Acceptance Scenarios**:

1. **Given** an existing meeting, **When** `endpaper read <id>` runs with output piped, **Then**
   standard output is the file's exact bytes with nothing added, removed, or re-encoded, and the
   command exits 0.
2. **Given** the same document, **When** `endpaper write <id>` is given replacement content on
   standard input, **Then** the file becomes that content with `updated` stamped and `created`
   untouched — the same file the terminal interface produces when the same text is saved from its
   edit state.
3. **Given** the same document, **When** `endpaper append <id>` is given content on standard input,
   **Then** that content is added at the end of the file, every preceding byte is unchanged, and
   `updated` is stamped.
4. **Given** an identifier or path that matches no document, **When** any of the three commands runs,
   **Then** it exits with the not-found code, writes the reason to standard error, and changes no
   file.
5. **Given** any of the three commands, **When** it runs, **Then** it never opens an editor, never
   prompts, never waits for a keypress, never pages, and emits no colour or cursor control characters
   when its output is not a terminal.
6. **Given** `endpaper read <id> --json`, **When** it runs, **Then** standard output parses as a
   single object carrying the document's identifier, path, and full content under documented keys.

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
- **The user saves an empty buffer.** The file becomes empty. From the command line the same outcome
  requires an explicit flag, because empty standard input is far more often an upstream failure than
  an intent.
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
- **A path outside the workspace given to a command-line read or write.** Refused with the workspace
  error code; endpaper does not read or write arbitrary files on the machine.
- **An argument that is both a valid identifier and an existing relative path.** Refused as a usage
  error naming both candidates, rather than silently preferring one.

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

**Command-line peer**

- **FR-036**: `endpaper read <id|path>` MUST write the target file's exact bytes to standard output,
  unmodified, and exit 0.
- **FR-037**: `endpaper read` MUST support `--json`, emitting a single object with the documented keys
  `id`, `path`, and `content`.
- **FR-038**: `endpaper write <id|path>` MUST replace the target file's content with what it reads
  from standard input.
- **FR-039**: `endpaper append <id|path>` MUST add what it reads from standard input to the end of the
  target file, leaving every preceding byte unchanged.
- **FR-040**: `endpaper write` and the interface's save MUST produce the same file from the same
  content, through the same underlying operation, including the `updated` stamp and the FR-018 and
  FR-019 behaviours.
- **FR-041**: `endpaper write` MUST refuse empty standard input as a usage error unless an explicit
  flag is given, and MUST NOT modify the file when it refuses.
- **FR-042**: All three commands MUST accept either a document identifier or a workspace-relative
  path, MUST refuse a path resolving outside the workspace with the workspace error code, and MUST
  refuse an argument that matches both an identifier and a path as a usage error naming both.
- **FR-043**: All three commands MUST target an existing file; creating a document remains the job of
  the create commands, and an unmatched target MUST exit with the not-found code.
- **FR-044**: No command in this feature may open an editor, prompt for input, wait for a keypress, or
  page its output.
- **FR-045**: No command in this feature may emit colour or cursor control characters when its output
  is not a terminal.
- **FR-046**: Data MUST go to standard output and diagnostics to standard error, never interleaved.
- **FR-047**: Exit codes MUST be 0 for success, 1 for a target that was not found, 2 for a usage
  error, and 3 for a workspace error.
- **FR-048**: The workspace guidance file generated at init MUST state the read, write, and append
  commands, while remaining roughly 60 lines or fewer.

**Never lose the user's words**

- **FR-049**: No operation in this feature may drop, reorder, or truncate a line the user did not
  change.
- **FR-050**: A document whose frontmatter the user has broken MUST be left exactly as written, MUST
  be skipped with a warning on the next scan rather than raising, and MUST NOT prevent any other
  document from listing.
- **FR-051**: Warnings MUST go to standard error on the command line, and to the interface's existing
  warning surface in the terminal interface — never into standard output and never into a document.

**Platform**

- **FR-052**: Windows, macOS, and Linux MUST be supported, with Windows treated as a primary target,
  and the bindings MUST be verified on the target terminals before release.
- **FR-053**: Workspace paths containing spaces and non-ASCII characters MUST work for every
  operation in this feature.
- **FR-054**: No operation in this feature may require network access.

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
  Invoked by the interface's save keys and by the command-line write.

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
- **SC-009**: An assistant can complete a read → modify → write cycle with no terminal attached, no
  human keystroke, and a non-zero exit code only when the operation genuinely failed.
- **SC-010**: The file produced by saving a given text in the interface and the file produced by
  piping the same text to the write command are identical apart from their timestamps, verified by a
  test that exercises both.
- **SC-011**: A save that fails because the file cannot be written loses nothing: the buffer is still
  present and the file on disk is unchanged, in 100% of induced failure cases.

## Assumptions

- **The preview state already exists.** Features 001 and 002 delivered rendered markdown preview,
  `enter` to open it, and `esc` to return to the list. This feature restates those transitions
  because §3.5 defines the state machine as a whole, but implements only the edit half and the
  footer change that unblocks it.
- **The command-line half is in scope.** `REQUIREMENTS.md` §3.5 is written in terminal-interface
  terms only, but the constitution requires that any behaviour in one front door exist in the other,
  and no other feature claims `read`, `write`, or `append` from §4.2. Shipping the edit state without
  them would leave an assistant unable to change a document at all. Interactive text entry itself has
  no command-line form and is exempt as inherently interactive.
- **The buffer wins on frontmatter.** The edit state shows raw markdown including frontmatter, so the
  user can change any field. Whatever they type is what gets written; endpaper stamps `updated` and
  otherwise does not police the fields. This is consistent with the tool's premise that the files are
  the user's own to hand-edit.
- **`updated` is a local-time timestamp** with the same shape as the one already written at creation.
- **Simultaneous edits are not detected.** `REQUIREMENTS.md` §5 makes the sync tool's own
  conflict-copy behaviour the answer for two copies edited at once, so a save does not check whether
  the file changed underneath it.
- **`write` does not create files.** Creation belongs to the create commands, which own naming,
  partitioning, and frontmatter generation. A write to an unknown target is a not-found error, not an
  invitation to invent a file.
- **Empty input to `write` is refused by default**, requiring an explicit flag, because an empty
  standard input is far more often a failed upstream command than a deliberate truncation, and the
  command line takes an explicit flag rather than asking.
- **`read` on a document with broken frontmatter still succeeds**, because it dumps bytes and does
  not parse.
- **Line numbers count real lines, not display rows**, so a wrapped paragraph occupies one number.
- **No undo history is specified beyond what the editing area provides natively**; the discard
  confirmation, not an undo stack, is the guarantee against losing work.
- **Python 3.11 or newer**, per `REQUIREMENTS.md` §4.1.

## Dependencies

- Feature `001-meeting-notes` for the workspace, the frontmatter schema, the list-and-preview screen,
  the footer, the warning surface, and the command-line conventions (exit codes, stream discipline,
  `--json`, the guidance file generated at init).
- Feature `002-general-notes` for notes and daily notes as a second collection, the collection menu,
  and the per-collection state that the edit state must leave undisturbed.
- The document scan and single-file re-parse already used to keep the list current.
- No new external dependency: the editing area is provided by the interface toolkit already in use,
  and no external editor, no syntax highlighter, and no search binary is introduced.

## Out of Scope

Deferred, and explicitly not delivered here:

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
