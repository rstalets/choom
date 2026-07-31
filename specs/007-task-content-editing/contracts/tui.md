# Contract: TUI surface

The TUI stays one screen with the states list → preview → edit, and every transition stays one
keystroke (Principle V).

## Preview pane

Highlighting a task renders, in the pane that today renders documents:

```markdown
# call the vendor

*2026-07-30 · followup · #procurement*

Need the Q3 comparison before the renewal meeting.

- 07-28 called, left voicemail
```

- The heading is the task's text; the italic line carries creation date, type, and tags, matching how
  documents preview. A completed task's metadata line says so.
- A task with no body shows the heading and metadata line only — never the previously highlighted
  task's content.
- Absent fields are omitted rather than rendered empty.
- A body taller than the pane scrolls; nothing is truncated.
- Rendering reads from the task list already in memory. No file is read on cursor movement, which is
  what keeps a 500-task list responsive (SC-005).

## Bindings

No key is added. `e` already exists on the list screen and is already shown in the footer; it becomes
active on task rows, where it is currently a no-op.

| Key | On a task row | Change |
|-----|---------------|--------|
| `e` | Open the editor on the task's body | Was a no-op |
| `space` | Toggle done — body preserved | Unchanged |
| `j` / `k` / arrows | Move, updating the preview | Preview is new for tasks |

`e` on the empty-state row does nothing.

## Editor

The existing editor screen, opened on the task's body instead of a file. Its bindings, discard
dialog, and status line are unchanged.

- The buffer holds the body alone — never the checkbox line, its metadata comment, or another task's
  content. A task with no body opens empty.
- `ctrl+o` saves; `ctrl+x` saves and closes; `escape` discards, confirming only when the buffer is
  dirty.
- Saving an unchanged buffer does not write to disk (SC-003).
- Returning to the list restores the same task highlighted, with the saved body in the pane.
- No frontmatter warning is shown — a task body has no frontmatter, and the `updated:` stamp that
  applies to notes and meetings does not apply here.

## Failure

A save that cannot complete reports what went wrong in the status bar and leaves the editor open
with the user's text intact (FR-023):

| Condition | Message names |
|-----------|---------------|
| The task no longer exists in the file | that the task is gone, and that the text is still in the buffer |
| The id is ambiguous | the conflicting line numbers |
| `tasks.md` cannot be written | the path and the underlying error |
