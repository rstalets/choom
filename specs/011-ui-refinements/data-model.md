# Phase 1 Data Model: UI Refinements

**Feature**: `011-ui-refinements` | **Date**: 2026-08-01 | **Plan**: [plan.md](./plan.md)

This feature stores nothing new. It removes records, and it renders existing ones differently. What
follows is what a delete touches, what it must never touch, and the two small in-memory values the
presentation work introduces.

---

## 1. Entities

### Record (existing — `Document` and `Task`)

No field changes. Deletion is defined per kind:

| Kind | Identified by | What "deleted" means |
|---|---|---|
| Meeting | `document.id` (`meeting_…`), file at `document.path` | The markdown file is removed from the workspace |
| Note | `document.id` (`note_…`), file at `document.path` | The markdown file is removed from the workspace |
| Task | `task.id` (`task_…`), a line in `workspace.tasks_file` | The checkbox line and its body span are removed from `tasks.md` |

### Deleted (new — returned by `deletion.delete_by_id`)

A small frozen dataclass describing what was removed, so callers can report it without re-reading:

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | The id that was deleted |
| `kind` | `str` | `"meeting"`, `"note"`, or `"task"` |
| `title` | `str` | The document title, or the task's text — what the TUI names in its confirmation |
| `path` | `Path` | The file removed, or `tasks.md` for a task |

It exists only as a return value. Nothing persists it.

### Mirror (existing — `core/mirrors.py`)

Untouched by this feature. A mirror whose task has been deleted resolves through the existing `dead`
outcome, with a `link_dead` warning. No field, no new outcome, no delete-time visit to mirroring
documents.

---

## 2. What a delete removes, precisely

### Meeting or note

The file at `document.path`, and nothing else. No directory is removed even if it becomes empty — an
empty month directory is not an error state, and removing it would be a second filesystem effect the user
did not ask for.

### Task

Given the parse of `tasks.md`:

```text
lines[:checkbox_idx] + lines[span.end:]
```

where `checkbox_idx` is the task's own line and `span` is its body span from `_body_span`. Preserved, by
reusing `set_task_body`'s write path:

- Every line outside the removed range is byte-identical, in the same order.
- The file's line-ending convention, taken from the first line that has one.
- The file's trailing-newline state when the removed block was at the end.
- Other tasks' ids, bodies, indentation, and metadata comments.

Not preserved, because it is the point: the task's own line and body.

---

## 3. What a delete must never touch

| Never | Why |
|---|---|
| Any document other than the one being deleted | FR-005; Principle IV |
| A mirror checkbox in a document, for a deleted task | FR-005/FR-006; the user typed that line |
| Another task's line or body in `tasks.md` | FR-003 |
| Frontmatter anywhere | Nothing in this feature writes frontmatter |
| Links pointing at the deleted record | FR out of scope; they become dead and are reported by the existing link check |

---

## 4. Transient state introduced

Two values, neither of which outlives the interaction that creates it. Neither is consulted to answer
"what is in the workspace" — that question goes to disk, per `010-read-on-load`.

| Value | Lifetime | Purpose |
|---|---|---|
| **Pending delete id** — the record id captured when `ctrl+d` raises the confirmation | From raising the dialog to its dismissal | FR-010: the confirmation acts on the record it named, so a list that changes underneath cannot redirect the delete (research R11) |
| **Column layout** — surviving columns and their widths, computed from the pane's width | One render; recomputed on resize | FR-028–FR-032; a pure function of width, held only as long as it takes to render the header and rows (research R8) |

The editor's padded buffer (research R10) is not listed here: it is the `TextArea`'s own text, not a
second copy of anything, and `original_text` moves with it so the two cannot disagree.

---

## 5. State transitions

### A delete from the list

```text
row highlighted
  → ctrl+d                      → confirmation raised, record id captured
    → Esc                       → nothing written; list, highlight, and preview unchanged
    → Enter                     → core delete runs
        → success               → list re-reads; highlight moves to the next record,
                                  or the previous one when the deleted record was last,
                                  or the empty state when it was the only one
        → NotFoundError         → status bar reports the record no longer exists; list re-reads
        → UsageError (ambiguous)→ status bar names the conflict; nothing deleted
        → WorkspaceError        → status bar reports the failure; nothing deleted; session usable
```

### A delete from the command line

```text
choom <type> delete <id> [--force]
  → no --force                  → exit 2, message on stderr, nothing deleted
  → id resolves to nothing      → exit 1, message on stderr
  → id resolves ambiguously     → exit 2, message names every path, nothing deleted
  → id resolves to another kind → exit 1, message names the expected kind
  → success                     → exit 0, stdout empty
```

Both paths run the same core function, so the outcomes above differ only in how they are reported.
