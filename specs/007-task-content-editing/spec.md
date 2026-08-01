# Feature Specification: Task Content Editing

**Feature Branch**: `007-task-content-editing`

**Created**: 2026-07-30

**Status**: Draft

**Input**: GitHub issue #26 — "[Feature]: Task Content Editing". Tasks are currently a single line with no room for context. Like notes and meetings, a task should carry a content body shown in the preview pane when highlighted, and `e` on a highlighted task should open the editor to update it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read a task's details while scanning the list (Priority: P1)

A user moves the cursor down the To-Do list. For each task they land on, the right-hand preview pane shows that task's details — what "call the vendor" actually requires, and the running log of what has been done so far. Tasks with no details show an empty preview rather than a stale one from the previous task.

**Why this priority**: This is the payoff the issue asks for. It is also the only story that works on a vault that already exists — a user who has hand-written indented notes under a task line today gets value immediately, with no editing feature at all. Every other story is a way of getting content into the pane this story displays.

**Independent Test**: Hand-edit `tasks.md` to add indented text under one task line, open the task list, move the cursor onto that task, and confirm the text renders in the preview pane and disappears when the cursor moves to a task without details.

**Acceptance Scenarios**:

1. **Given** a task whose line is followed by indented detail text, **When** the user highlights that task, **Then** the preview pane renders that text as markdown.
2. **Given** a task with no detail text, **When** the user highlights it immediately after a task that had details, **Then** the preview pane is empty and shows no content belonging to the previous task.
3. **Given** a completed task with details, **When** the user highlights it in the Done category, **Then** its details render the same way they do for an open task.
4. **Given** a task whose details are longer than the preview pane, **When** the user highlights it, **Then** the pane shows the beginning of the content and the remainder is reachable by scrolling.

---

### User Story 2 - Add and update a task's details (Priority: P2)

A user highlights a task and presses `e`. The editor opens on that task's details — empty for a task that has none, pre-filled for one that does. They type what the task requires, or append a dated line to the history ("07-30 called, left voicemail"), and save. The list returns with the same task still highlighted and the new content in the preview pane.

**Why this priority**: This is what turns the preview pane from a viewer of hand-written content into a working capture surface. It depends on P1 to show its result, so it ships second.

**Independent Test**: Highlight a task, press `e`, type a line of text, save, and confirm the text is present in `tasks.md` under that task and rendered in the preview pane.

**Acceptance Scenarios**:

1. **Given** a highlighted task with no details, **When** the user presses `e`, **Then** an editor opens with an empty buffer scoped to that task.
2. **Given** a highlighted task with details, **When** the user presses `e`, **Then** the editor opens pre-filled with exactly those details and nothing else — not the task's own line, and not any other task's content.
3. **Given** an open editor with unsaved changes, **When** the user saves, **Then** the details are written to `tasks.md`, the list is restored with the same task highlighted, and the preview pane shows the new content.
4. **Given** an open editor with unsaved changes, **When** the user discards, **Then** `tasks.md` is unchanged and the previous details are still shown.
5. **Given** a task whose details were just edited, **When** the file is inspected, **Then** the task's own line is byte-identical to before — same checkbox state, same text, same identifier comment.
6. **Given** a task with details, **When** the user opens the editor, deletes all content, and saves, **Then** the task returns to a single line with no leftover blank or indented lines.
7. **Given** a task with details, **When** the user toggles it done or open, **Then** the details are preserved unchanged.

---

### User Story 3 - An assistant reads task details through the CLI (Priority: P3)

An AI assistant working through the CLI needs the same context a human sees in the preview pane: it lists tasks, sees which ones carry details, and reads the details for a specific task before acting or writing an update back into the file.

**Why this priority**: Required for interface parity, and it is the smaller half of the work — the CLI reads and reports; it never opens an editor. It ships last because the human-facing loop is the point of the issue.

**Independent Test**: Add details to a task, then confirm the CLI can print those details for that task by identifier and that the machine-readable task listing reports the details.

**Acceptance Scenarios**:

1. **Given** a task with details, **When** the assistant asks the CLI to show that task by identifier, **Then** the details are printed to standard output and the command exits successfully.
2. **Given** a task with no details, **When** the assistant asks the CLI to show it, **Then** the command succeeds and prints the task with no detail content, rather than reporting an error.
3. **Given** an identifier that matches no task, **When** the assistant asks the CLI to show it, **Then** the command reports the failure on the error stream and exits with the not-found code.
4. **Given** a mix of tasks with and without details, **When** the assistant requests the machine-readable listing, **Then** each task's entry carries its details, and entries that existed before this feature keep every field they had.

---

### Edge Cases

- **A checkbox line inside a task's details.** A user writes a nested checklist, or pastes an example containing `- [ ] something`, into a task's details. The line continues to be read as its own task, exactly as it is today, which ends the enclosing task's details at that point. No line is lost or rewritten; the content simply appears in the list rather than in the pane.
- **Hand-written details in an unexpected shape.** Tabs instead of spaces, inconsistent indent depth, blank lines inside the block, a fenced code block, or trailing whitespace. All of it is preserved verbatim on read and on any write that does not target that task.
- **Details under a task line with a broken metadata comment.** The malformed line is skipped with a warning as it is today; the indented lines beneath it are left untouched and are never re-attached to a different task.
- **Two tasks sharing one identifier.** Showing or editing details for an ambiguous identifier fails with a message naming the conflicting line numbers, and no write occurs — the same rule that already applies to completing a task.
- **The file changed underneath the editor.** Another program modifies `tasks.md` while the editor is open. On save, the task is located by identifier rather than by remembered position, so the details land on the right task even if lines moved; if the task is gone entirely, the user is told and their typed content is not silently dropped.
- **Details that look like metadata.** The user types a line containing `<!-- id:t_x -->` inside a body. It stays part of the details and does not create, rename, or capture a task.
- **Windows line endings and a missing final newline.** A file written with CRLF stays CRLF after a details edit, and a file without a trailing newline does not silently gain or lose one beyond what the edit requires.
- **Very long details.** A body of several hundred lines renders in the preview pane and round-trips through the editor without truncation.
- **Non-ASCII content.** Accented characters, emoji, and CJK text in a body survive read, render, edit, and write.

## Requirements *(mandatory)*

### Functional Requirements

**Storage and parsing**

- **FR-001**: A task MUST be able to carry an optional detail body, stored as indented content directly beneath its checkbox line in `tasks.md`.
- **FR-002**: The system MUST read a task's body as every line following its checkbox line up to, but not including, the next checkbox line or the next non-indented, non-blank line.
- **FR-003**: `tasks.md` MUST remain valid CommonMark with bodies present, rendering as a checklist whose items carry nested content in any markdown viewer.
- **FR-004**: Reading a file MUST NOT alter, reorder, or drop body content, including content whose indentation, whitespace, or structure is irregular.
- **FR-005**: A task with no body MUST behave exactly as tasks do today — one line, no blank line reserved, no placeholder written.
- **FR-006**: Existing `tasks.md` files MUST continue to parse with no migration step and no change to which lines are recognised as tasks.

**Viewing**

- **FR-007**: Highlighting a task in the task list MUST render that task's body as markdown in the preview pane.
- **FR-008**: Highlighting a task with no body MUST clear the preview pane rather than leave the previously highlighted task's content in place.
- **FR-009**: Body preview MUST work identically for open and completed tasks.
- **FR-010**: A body taller than the preview pane MUST be scrollable rather than truncated.

**Editing**

- **FR-011**: Pressing `e` on a highlighted task MUST open the editor on that task's body.
- **FR-012**: The editor MUST be scoped to the highlighted task's body alone — it MUST NOT expose the task's own checkbox line, its metadata comment, or any other task's content.
- **FR-013**: Saving MUST write the edited body beneath that task and leave the task's own line byte-identical, preserving its checkbox state, text, identifier, type, tags, and creation date.
- **FR-014**: Saving MUST leave every other line in `tasks.md` byte-identical.
- **FR-015**: Saving an empty body MUST remove the task's body entirely, leaving a single task line with no residual blank or indented lines.
- **FR-016**: Discarding MUST leave `tasks.md` unchanged.
- **FR-017**: The editor MUST confirm before discarding unsaved changes, and MUST NOT confirm when nothing would be lost.
- **FR-018**: Returning from the editor MUST restore the task list with the same task highlighted and the preview pane showing the saved body.
- **FR-019**: Writes MUST re-read and re-parse `tasks.md` and locate the task by identifier, never by a remembered line number.
- **FR-020**: Writes MUST be atomic — an interrupted save MUST leave the previous file intact rather than a partial one.
- **FR-021**: A write MUST preserve the file's existing line-ending convention and trailing-newline state.
- **FR-022**: Toggling a task's completion MUST preserve its body unchanged.
- **FR-023**: A save that cannot complete — unwritable file, vanished task, ambiguous identifier — MUST report what went wrong and MUST NOT discard the user's typed content.
- **FR-024**: Every binding this feature adds or changes MUST be listed in the footer and in the help pane.

**Command-line surface**

- **FR-025**: The CLI MUST provide a command that prints a single task and its body, selected by identifier.
- **FR-026**: That command MUST offer a machine-readable form alongside its human-readable form.
- **FR-027**: The machine-readable task listing MUST report each task's body, and MUST retain every field it emits today under its current name.
- **FR-028**: Requesting a task that does not exist MUST report the failure on the error stream and exit with the not-found code; an ambiguous identifier MUST exit with the usage-error code.
- **FR-029**: Every CLI command this feature adds or changes MUST NOT open an editor, prompt, or block on input, and MUST send data to standard output and errors to the error stream.
- **FR-030**: The changed task listing schema and the task line format's body extension MUST be recorded in the changelog and in the workspace's assistant guidance file.

### Key Entities

- **Task**: A checkbox line in `tasks.md` with an identifier, text, completion state, optional type, tags, and creation date. Gains an optional **body** — free markdown describing what the task requires and what has been done toward it. The body has no schema, no length limit, and no required structure.
- **`tasks.md`**: The single file holding every task. Remains the only source of truth for tasks; this feature adds no second store, no index, and no sidecar file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can read a highlighted task's details with zero keystrokes beyond moving the cursor onto it.
- **SC-002**: A user can go from a highlighted task to typing in its details in one keystroke, and back to the list with the content saved in one more.
- **SC-003**: Opening a task's details and saving without typing anything leaves `tasks.md` byte-identical.
- **SC-004**: 100% of hand-written body content — including irregular indentation, blank lines, fenced blocks, and non-ASCII text — survives a full read, render, edit, and save cycle with no line lost or reordered.
- **SC-005**: Moving the cursor through a list of 500 tasks updates the preview pane with no perceptible delay, and the list remains navigable at the same speed as before this feature.
- **SC-006**: A `tasks.md` written before this feature opens with every task listed exactly as it was, with no migration prompt and no file rewrite on first read.
- **SC-007**: An assistant can retrieve any task's details through the command line in a single non-interactive call that never prompts, never opens an editor, and returns a documented exit code.
- **SC-008**: A `tasks.md` containing task bodies renders as a correct nested checklist in a markdown viewer that knows nothing about endpaper.

## Assumptions

- **Body storage is inline.** A task's body lives indented beneath its own line in `tasks.md` rather than in a per-task sidecar file. Chosen for the single-file, hand-editable premise and because it adds no directory to the fixed set of collections; the cost is a longer `tasks.md` and an editor scoped to a slice of a file rather than a whole file.
- **Nested checkbox lines stay tasks.** A checkbox line indented under another task continues to be parsed as its own task, exactly as it is today, and ends the enclosing task's body. This preserves every existing vault's task list unchanged; the trade-off is that a checklist cannot be nested inside a body. No subtask hierarchy is introduced.
- **The CLI reads, the TUI writes.** The command line gains a way to show a task and its body and reports bodies in its machine-readable listing; it does not gain an interactive editor, per the rule that the CLI never opens one. Assistants write bodies by editing the markdown directly, as they already do for notes and meetings.
- **No timestamp stamping.** Tasks have no frontmatter, so editing a body does not stamp an `updated` field and does not alter the task's `created` date. Dated history lines inside a body are the user's own convention, not a format the tool imposes or parses.
- **Existing editor behaviour is reused.** Saving, discarding, the unsaved-changes confirmation, and markdown rendering behave as they already do for notes and meetings; this feature changes what the editor is opened on, not how it works.
- **Scope is unchanged elsewhere.** No due dates, priorities, project hierarchy, or attachment of tasks to meetings and notes. Bodies are free text and are not searched, filtered, or indexed by this feature.
- **Filtering is unaffected.** The task filter continues to match on text, type, and tags; body content is not part of the filter's haystack in this feature.
