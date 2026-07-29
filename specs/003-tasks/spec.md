# Feature Specification: Tasks

**Feature Branch**: `003-tasks`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "requirements.md feature 3.3"

**Source**: `REQUIREMENTS.md` §3.3, plus the tagging rule stated at the head of §3, and the subset
of §4.2, §4.5, §4.6, and §4.7 that applies to tasks. Builds on the workspace, tagging, and
command-line conventions delivered by feature `001-meeting-notes`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture a task the moment it is agreed (Priority: P1)

Someone says "can you send the vendor comparison" halfway through a call. The user types one short
line — what to do, and optionally what kind of thing it is and what it relates to — and it is
recorded. They never choose a file, a folder, or a format, and they are never taken away from what
they were doing.

**Why this priority**: Nothing else in this feature exists without a way to record a task. This
story alone delivers durable capture from both front doors, and the resulting file is readable and
useful in any markdown viewer even if no other part of the feature is ever built.

**Independent Test**: From a fresh workspace, add tasks from the terminal interface and from the
command line, then open `tasks.md` in a plain text editor and confirm one checkbox line per task,
with the description, type, and tags intact.

**Acceptance Scenarios**:

1. **Given** an initialized workspace, **When** the user runs
   `endpaper task add "send the vendor comparison" --type followup --tag procurement`, **Then**
   `tasks.md` gains exactly one unchecked checkbox line carrying that text, a generated identifier,
   the type `followup`, the tag `procurement`, and today's date, and the command prints the
   identifier and exits 0.
2. **Given** the terminal interface is open, **When** the user issues
   `/task.followup send the vendor comparison #procurement`, **Then** the resulting line in
   `tasks.md` matches the one produced in scenario 1 in every field except the generated identifier
   and date-stamped values.
3. **Given** a `tasks.md` that already contains tasks and hand-written prose around them, **When**
   a task is added, **Then** the new line is appended and every pre-existing byte of the file is
   unchanged.
4. **Given** a workspace whose `tasks.md` has been deleted by the user, **When** a task is added,
   **Then** the file is recreated containing that one task and the command exits 0.

---

### User Story 2 - See what is open and check things off (Priority: P2)

At the end of the day the user wants the short list of what is still outstanding, and wants to tick
off the two things they finished. From the interface it is one keystroke per task; from the command
line it is one command per task, so an assistant can do it too.

**Why this priority**: Capture without review is a write-only log. This is what makes the captured
tasks worth capturing. It depends only on Story 1.

**Independent Test**: With a `tasks.md` containing a mix of open and completed tasks, list from both
front doors, toggle a task from each, and confirm the file on disk changed in exactly the expected
character positions.

**Acceptance Scenarios**:

1. **Given** a `tasks.md` containing three open and two completed tasks, **When** the user runs
   `endpaper task list`, **Then** only the three open tasks are shown, oldest first.
2. **Given** the same file, **When** the user runs `endpaper task list --all`, **Then** all five are
   shown and the completed ones are distinguishable from the open ones.
3. **Given** the terminal interface showing the task list, **When** the user moves the selection with
   the arrow keys or `j`/`k` and presses `space`, **Then** the selected task's checkbox flips in
   `tasks.md`, its metadata comment is preserved unchanged, and the list reflects the new state.
4. **Given** the terminal interface showing the task list, **When** the user presses `a`, **Then**
   completed tasks appear alongside open ones, rendered struck through, and pressing `a` again
   returns to open tasks only.
5. **Given** a task whose identifier is `t_a1b2`, **When** the user runs `endpaper task done t_a1b2`,
   **Then** the file changes exactly as it would have if the user had pressed `space` on that task in
   the interface, and `endpaper task undone t_a1b2` reverses it exactly.
6. **Given** an identifier that matches no task, **When** `endpaper task done` is run with it,
   **Then** the command exits with the not-found code, writes a message to standard error, and
   changes no file.

---

### User Story 3 - Hand-edit `tasks.md` and lose nothing (Priority: P3)

The user opens `tasks.md` in whatever editor is in front of them and types `- [ ] buy milk` at the
bottom, or reorders lines, or deletes half of a metadata comment by accident. endpaper picks up
what it can, repairs what it safely can, and never destroys what it cannot understand.

**Why this priority**: A plain markdown file that punishes hand-editing is not a plain markdown file.
This property is what lets the format be the product rather than an implementation detail, and it is
independently valuable even to a user who never runs a single task command.

**Independent Test**: Construct a `tasks.md` by hand containing well-formed tasks, a bare checkbox
with no metadata, a checkbox with a truncated metadata comment, headings, paragraphs, and an
indented sub-list, then list and toggle tasks and diff the file before and after.

**Acceptance Scenarios**:

1. **Given** a hand-written line `- [ ] buy milk` with no metadata comment, **When** the tasks are
   next scanned, **Then** that line is listed as an open task and gains a generated identifier in
   place, with the task text, the surrounding lines, and the rest of the file unchanged.
2. **Given** a line with a truncated metadata comment such as `- [ ] thing <!-- id:`, **When** the
   tasks are scanned, **Then** no error is raised, that line is left byte-identical on disk, a
   warning is recorded, and every other task in the file still lists.
3. **Given** a `tasks.md` containing headings, paragraphs, and non-task list items, **When** any task
   operation runs, **Then** those lines are preserved verbatim and in place.
4. **Given** a `tasks.md` using Windows line endings and no trailing newline, **When** a task is
   toggled, **Then** the line endings and the absence of a trailing newline are preserved.
5. **Given** any sequence of add, complete, and uncomplete operations, **When** the file is compared
   before and after, **Then** no line has been dropped, reordered, or truncated.

---

### User Story 4 - An AI assistant manages the list unattended (Priority: P4)

An assistant working in the user's workspace adds the tasks it agreed to, reads back what is open,
and marks things done as it finishes them — with no terminal, no prompts, and no guesswork about
whether a command succeeded.

**Why this priority**: It is the reason the command line exists at all, and it is a small increment
once Stories 1 and 2 are in place: a stable machine-readable projection of what the interface
already shows.

**Independent Test**: Run every task command with output redirected to a file, with no terminal
attached, and confirm the output parses as JSON where requested, contains no decoration, and that
exit codes distinguish success, not-found, usage error, and workspace error.

**Acceptance Scenarios**:

1. **Given** a workspace with tasks, **When** `endpaper task list --json` is run with output piped,
   **Then** standard output parses as a JSON array whose objects carry a documented, stable set of
   keys, and contains no colour or cursor control characters.
2. **Given** any task command, **When** it is run, **Then** it never opens an editor, never prompts,
   never waits for a keypress, and never pages its output.
3. **Given** a command run outside any workspace, **When** it executes, **Then** it exits with the
   workspace error code and explains how to create a workspace.
4. **Given** the workspace guidance file generated at init, **When** an assistant reads it, **Then**
   it states the task line format and that `--tag` is the command-line form for tags.

---

### Edge Cases

- A task description that is empty or only whitespace once tags are removed: rejected as a usage
  error, and `tasks.md` is not touched.
- A description containing the metadata comment's own delimiters, or a literal `<!--`: stored so
  that the line still parses back to the same task text on the next scan.
- A description spanning what the user intended as multiple lines: newlines are collapsed to spaces,
  because one task is one line.
- An unquoted `#tag` on the command line: the shell strips it before endpaper sees it and the tag is
  silently absent — help text and the workspace guidance file must document `--tag` prominently.
- Two lines carrying the same identifier, typically from a copy-paste: both are listed, and any
  command that targets that identifier refuses to act, exits with a usage error, and names the
  affected lines rather than guessing which was meant.
- A completed task marked with an uppercase `- [X]`: recognised as completed; toggling writes the
  lower-case form without altering any other character on the line.
- An indented checkbox nested under another list item: treated as a task, with its indentation
  preserved on rewrite.
- A checkbox using an alternative bullet marker (`*` or `+`): treated as a task, with the marker
  preserved.
- `tasks.md` absent when listing: the list is empty and the command exits 0, rather than erroring.
- `tasks.md` present but not writable: listing still works and reports the tasks it can identify;
  identifier backfill is skipped with a warning; completing a task fails with the workspace error
  code and changes nothing.
- `tasks.md` is very large, or the disk fills mid-write: the file is never left truncated or
  half-written.
- A task line containing non-ASCII text, emoji, or right-to-left script: stored and displayed intact.
- The terminal window is very small, or is resized while the task list is open: the layout adapts
  without crashing.

## Requirements *(mandatory)*

### Functional Requirements

**Creating a task**

- **FR-001**: Users MUST be able to add a task from the terminal interface with
  `/task.<type> <description>` and from the command line with
  `endpaper task add <description> --type <type>`, both producing the same result through the same
  underlying operation.
- **FR-002**: The type MUST be optional and free-form. Omitting it MUST create a task with no type.
- **FR-003**: In the terminal interface, `#tag` tokens MUST be accepted inline anywhere in the
  description, repeatably, and MUST be removed from the stored task text.
- **FR-004**: On the command line, `--tag` MUST be accepted repeatably, and `#tag` tokens appearing
  inside a quoted description MUST also be parsed as tags and stripped from the task text.
- **FR-005**: Tags MUST be stored in the order supplied, with duplicates removed.
- **FR-006**: A new task MUST be appended as a single line to `tasks.md` in the current workspace,
  leaving every existing byte of that file unchanged.
- **FR-007**: When `tasks.md` does not exist, adding a task MUST create it.
- **FR-008**: On the command line, adding a task MUST print the new task's identifier to standard
  output and exit 0.
- **FR-009**: A description that is empty after tag removal MUST be rejected as a usage error, with
  no file written.
- **FR-010**: Adding a task MUST NOT modify any file other than `tasks.md`.

**Storage format**

- **FR-011**: Tasks MUST be stored as markdown checkbox lines in a single file, `tasks.md`, at the
  workspace root, one task per line.
- **FR-012**: Each task line MUST carry its metadata in a trailing HTML comment holding the fields
  `id`, `type`, `tags`, and `created`, so that the metadata is invisible when the file is rendered.
- **FR-013**: The `type` and `tags` fields MUST be omitted from the comment when empty, rather than
  written as empty values.
- **FR-014**: `tasks.md` MUST remain valid CommonMark at all times and MUST render as a checklist in
  any markdown viewer.
- **FR-015**: A task's identifier MUST be unique within `tasks.md` and MUST remain stable for the
  life of the task, including across completion, reopening, and hand-reordering of the file.
- **FR-016**: Task state MUST be carried by the checkbox itself — unchecked for open, checked for
  completed — with no separate status field.
- **FR-017**: There MUST be no index, database, or cache of tasks; `tasks.md` is the only source of
  truth.

**Listing tasks**

- **FR-018**: Users MUST be able to list tasks from the terminal interface with `/tasks` and from the
  command line with `endpaper task list`.
- **FR-019**: Open tasks MUST be shown by default, sorted by creation date, oldest first, with tasks
  sharing a date keeping their order in the file.
- **FR-020**: Completed tasks MUST be included when `--all` is given on the command line, and when
  `a` is pressed in the terminal interface, and MUST be visually distinguishable — struck through in
  the interface.
- **FR-021**: The command line MUST support `--tag` and `--type` filters, which MUST combine
  conjunctively with each other and with `--all`.
- **FR-022**: `--json` MUST emit an array of objects with exactly the keys `id`, `text`, `done`,
  `type`, `tags`, `created`, and `line`, where `line` is the task's 1-based line number in
  `tasks.md`.
- **FR-023**: The task list MUST be produced by scanning markdown, not by reading a database, so that
  the same scan can later be pointed at additional files without migrating any data.
- **FR-024**: Listing MUST exit 0 and produce an empty list when `tasks.md` is absent or contains no
  checkbox lines.

**Completing and reopening**

- **FR-025**: Pressing `space` on the selected task in the terminal interface MUST toggle its
  completion state and write the change to `tasks.md`.
- **FR-026**: `endpaper task done <id>` and `endpaper task undone <id>` MUST produce exactly the file
  change that toggling the same task in the interface produces.
- **FR-027**: A toggle MUST change only the checkbox character on the target line, preserving that
  line's indentation, bullet marker, task text, metadata comment, and trailing whitespace.
- **FR-028**: Marking a task done that is already done, or reopening one that is already open, MUST
  exit 0 and leave the file unchanged.
- **FR-029**: An identifier matching no task MUST exit with the not-found code, report to standard
  error, and change nothing.
- **FR-030**: An identifier matching more than one line MUST be refused as a usage error naming the
  affected line numbers, and MUST change nothing.
- **FR-031**: Identifier matching MUST be exact; no prefix or fuzzy matching.
- **FR-032**: A write that cannot complete MUST leave `tasks.md` as it was, never truncated or
  partially written.

**Tolerating hand-editing**

- **FR-033**: A checkbox line with no metadata comment MUST be treated as a valid task, and MUST be
  given a generated identifier written back in place on the next scan, with no other character on
  that line and no other line in the file altered.
- **FR-034**: A checkbox line with a malformed or partial metadata comment MUST be skipped rather
  than raising, MUST be recorded as a warning, and MUST be left byte-identical on disk.
- **FR-035**: One unparseable line MUST NOT prevent any other task in the file from being listed or
  toggled.
- **FR-036**: No scan, listing, or toggle may drop, reorder, truncate, or rewrite any non-task line
  in `tasks.md`.
- **FR-037**: Existing line endings and the presence or absence of a final newline MUST be preserved
  by every write.
- **FR-038**: When identifier backfill cannot be written — for example, a read-only file — listing
  MUST still succeed, reporting the affected tasks without identifiers and warning on standard
  error.
- **FR-039**: Warnings about unparseable or unwritable lines MUST go to standard error, never to
  standard output.

**Interface behaviour**

- **FR-040**: The terminal interface MUST support moving the task selection with the up and down
  arrows and with `j`/`k`.
- **FR-041**: Every key binding active in the task list MUST be visible in the footer.
- **FR-042**: The interface MUST NOT bind the terminal's reserved interrupt or quit keys to any task
  action.
- **FR-043**: A toggle made in the interface MUST be reflected in the list without a manual refresh,
  and MUST re-read only the file that changed.
- **FR-044**: Task creation from the interface MUST leave the user on the task list with the new task
  visible, not in a preview or an editor.

**Command-line discipline**

- **FR-045**: No task command may open an editor, prompt for input, wait for a keypress, or page its
  output.
- **FR-046**: No task command may write colour or cursor control characters when its output is not a
  terminal.
- **FR-047**: Data MUST be written to standard output and diagnostics to standard error, never
  interleaved.
- **FR-048**: Exit codes MUST be 0 for success, 1 for an identifier that was not found, 2 for a usage
  error, and 3 for a workspace error.
- **FR-049**: Every task command run outside a workspace MUST exit with the workspace error code and
  state how to create one.
- **FR-050**: The workspace guidance file generated at init MUST state the task line format and the
  task commands, while remaining roughly 60 lines or fewer.

**Platform**

- **FR-051**: Windows, macOS, and Linux MUST be supported, with Windows treated as a primary target.
- **FR-052**: Workspace paths containing spaces and non-ASCII characters MUST work for every task
  operation.
- **FR-053**: No task operation may require network access.

### Key Entities

- **Task**: One thing to do, represented by exactly one markdown checkbox line in `tasks.md`.
  Described by its text, an open or completed state, an optional type, zero or more tags, a creation
  date, and a stable identifier. Its position in the file is the user's to change.
- **Task file**: `tasks.md` at the workspace root. A hand-editable markdown document that may contain
  arbitrary prose and structure around its checkbox lines, and that is the sole store of task state.
- **Task metadata comment**: The trailing HTML comment on a task line carrying identifier, type,
  tags, and creation date. Invisible when rendered, optional on any given line, and never required
  for a line to count as a task.
- **Task record**: The in-memory, machine-readable projection of a task shared by the interface's
  list and the command line's JSON output, with a fixed and documented set of fields.
- **Tag**: A short free-form label attached to a task. Supplied inline in the interface, and by an
  explicit option on the command line.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can record a task, from an already-open interface or a shell in the workspace,
  in one action and under 10 seconds, without choosing a file, folder, or format.
- **SC-002**: Marking a task complete in the interface is reflected in `tasks.md` within one second.
- **SC-003**: Across any sequence of 1,000 add, complete, and reopen operations, no task text is lost
  or altered and no non-task line in the file is changed.
- **SC-004**: `tasks.md` renders as a checklist, with no visible metadata, in every markdown viewer
  tested — at minimum one web renderer, one editor preview, and one repository host.
- **SC-005**: A `tasks.md` in which one line in ten is malformed still lists 100% of its well-formed
  tasks, and produces no crash and no data loss.
- **SC-006**: A hand-written checkbox with no metadata is listed on the next scan and becomes
  addressable by identifier without the user taking any repair step.
- **SC-007**: A workspace of 1,000 tasks lists in under one second, and the interface's list responds
  to navigation with no perceptible delay.
- **SC-008**: An assistant can complete an add → list → mark-done cycle with no terminal attached, no
  human keystroke, and a non-zero exit code only when the operation genuinely failed.
- **SC-009**: Every capability available in one front door is available in the other, verified by a
  test that exercises add, list, complete, and reopen through both and compares the resulting files.

## Assumptions

- **Identifier format.** Task identifiers are short and prefixed with `t_` to distinguish them from
  meeting identifiers, and are generated to be unique within `tasks.md`. REQUIREMENTS.md §3.3 shows
  `t_a1b2`; the exact length is left to the plan, subject to FR-015.
- **`--all` means "include completed".** REQUIREMENTS.md uses `--all` in §3.3 for showing completed
  tasks and in §3.4 for widening to every workspace. Cross-workspace scope is not part of this
  feature, so `--all` here carries only the §3.3 meaning. Should both ever apply to `task list`, the
  cross-workspace flag needs a different name.
- **Tasks are single-workspace.** Task commands operate on the current workspace's `tasks.md` only.
- **Creation is recorded as a date, not a timestamp**, matching the line format in REQUIREMENTS.md
  §3.3, and using local time.
- **No completion timestamp is recorded.** The checkbox is the state. Adding a `completed` field
  would extend the documented line format for information no requirement asks for.
- **New tasks are appended to the end of the file**, which keeps file order aligned with creation
  order for a file endpaper wrote, without imposing order on a file the user has rearranged.
- **Sort is oldest-first**, unlike the date-descending meeting list: an open task list is a queue to
  work through, not a history to browse.
- **`endpaper task add` prints the identifier**, because the identifier is what the next command
  needs; the file path is fixed and already known.
- **Tags are matched exactly and case-insensitively** on the command line, consistent with meeting
  listing.
- **Tasks are standalone**, per REQUIREMENTS.md §3.3 — not attached to a meeting or note in v0.0.1.
- **Python 3.11 or newer**, per REQUIREMENTS.md §4.1.

## Dependencies

- Feature `001-meeting-notes` for workspace creation and resolution, the guidance file generated at
  init, the tag-parsing rules shared by all create commands, the command-line conventions (exit
  codes, stream discipline, `--json`), and the terminal interface's command bar and list navigation.
- The `tasks.md` file created empty by `endpaper init` in that feature.
- No new external dependency: task scanning is plain markdown scanning, with no external search
  binary and no database.

## Out of Scope

Deferred, and explicitly not delivered here:

- Tasks created from inside a note or meeting, and tasks linked to one (REQUIREMENTS.md §5)
- Due dates, priorities, assignees, recurrence, and subtask hierarchies — no requirement asks for
  them and each would extend the documented line format
- Scanning files other than `tasks.md` for checkboxes; the scan is built so this can be added later
  without migration, but it is not enabled in v0.0.1
- Cross-workspace task listing, and the workspace switching it depends on (§3.4)
- Editing `tasks.md` through the interface's edit state (§3.5)
- Searching tasks with `endpaper find` (§4.4)
- Conflict resolution when two synced copies of `tasks.md` are edited at once (§5)
- Everything else listed in REQUIREMENTS.md §5
