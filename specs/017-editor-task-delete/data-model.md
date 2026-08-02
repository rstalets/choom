# Phase 1 Data Model: Delete a Task From the Line It Lives On

**Feature**: `017-editor-task-delete` | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-02

Nothing here is persisted. choom's only state is markdown files (Principle III); every type below
lives for the duration of one keystroke and is discarded.

---

## 1. `Mirror` — modified

`src/choom/core/models.py`. Two fields added; nothing removed or renamed.

| Field | Type | Status | Meaning |
|---|---|---|---|
| `task_id` | `str` | unchanged | The task this line is a control surface onto |
| `done` | `bool` | unchanged | The checkbox state as the line reads |
| `line` | `int` | unchanged | **1-based** line number in the document text |
| `state_offset` | `int` | unchanged | Character offset of the single state character |
| `text` | `str` | unchanged | The link's text — the task's description as the line displays it |
| `link_start` | `int` | **new** | Character offset where the mirror's link begins |
| `link_end` | `int` | **new** | Character offset one past where it ends |

`link_start`/`link_end` are copied from the `Link` that `find_mirrors` already selects as the mirror
(the lowest-`start` task link on the line, per FR-007). They are offsets into the same text
`state_offset` indexes, so all three are directly comparable.

**Why on `Mirror` rather than recomputed**: FR-005 and FR-007 forbid a second definition of which link
on a line is *the* task. `find_mirrors` makes that choice once and currently discards the evidence;
carrying it means the extra-text test in R7 reads the answer instead of re-deriving it.

**Invariant**: `link_start <= link_end`, and both fall within the line whose 1-based index is `line`.

**Construction**: still exactly one site — `find_mirrors` in `src/choom/core/mirrors.py`. The docstring's
"produced by scanning, never constructed by a caller" continues to hold, which is why two required
fields can be added without touching any other call site.

---

## 2. `MirrorDeletionOutcome` — new

`src/choom/core/models.py`, a `Literal` alongside the existing `MirrorOutcome`.

```
"deletable" | "line_only" | "unreadable_tasks" | "ambiguous_id" | "self_referential"
```

| Value | Meaning | Confirms? | Writes `tasks.md`? | Removes the line? |
|---|---|---|---|---|
| `deletable` | The task line resolves to exactly one task record | yes | yes | yes |
| `line_only` | No such task record, and the task list parsed cleanly (FR-012) | yes | no | yes |
| `unreadable_tasks` | No such task record, but the task list has lines choom could not parse (FR-021) | no | no | no |
| `ambiguous_id` | The id is on more than one task record (FR-023) | no | no | no |
| `self_referential` | The buffer is this task's own body (FR-024) | no | no | no |

The three refusing outcomes are terminal: the TUI reports `message` and stops. There is no partial
path through them.

**Why an enum rather than an exception per case**: the refusals are ordinary, expected states of a
user's hand-edited workspace, not errors in the caller. Making them return values means the adapter
handles all five in one place and cannot forget one — and it keeps core out of the business of
deciding which failures are exceptional, which is what produced the outcome enum `MirrorResolution`
already uses for reconciliation.

---

## 3. `MirrorDeletion` — new

`src/choom/core/models.py`, frozen, slotted, matching the module's existing style.

| Field | Type | Meaning |
|---|---|---|
| `outcome` | `MirrorDeletionOutcome` | Which of the five cases above |
| `task_id` | `str` | The id named by the task line |
| `description` | `str` | The link text — what the confirmation quotes |
| `text` | `str` | The document text with the line removed. `""` on a refusing outcome |
| `span` | `tuple[int, int]` | Character offsets of the removal in the *original* text. `(0, 0)` on a refusing outcome |
| `extra_text` | `bool` | The line carries content beyond the checkbox prefix and the mirror's own link (FR-011) |
| `message` | `str` | Why it was refused, naming the cause and the next step. `""` otherwise |

**Central invariant** — the one a test asserts, and the reason the adapter cannot drift from core:

```
plan.text == original[: plan.span[0]] + original[plan.span[1] :]
```

Both fields describe the same single removal. `text` is what a non-widget caller uses; `span` is what
the TUI converts to widget coordinates so the edit is undoable (research R2, R4).

**Span definition** — the whole line including its terminator:

| Situation | Span |
|---|---|
| Task line is followed by another line | first character of the line → first character of the next line |
| Task line is last, with a trailing newline | first character of the line → end of text |
| Task line is last, with no trailing newline | end of the *previous* line's content → end of text (absorbs the preceding terminator, so no blank line is left behind) |
| Task line is the only line | `(0, len(text))` |

The buffer is always LF-only (research R5), so a terminator is exactly one character and the file's real
convention is restored by the save path.

**Lifetime**: created by `plan_mirror_deletion` before the dialog is raised, held by the TUI across the
modal, consumed on confirm. Never persisted, never serialised, never crosses a process boundary. It is
also the mechanism for FR-013 — what is applied on confirm was decided from the buffer as it stood when
the question was asked.

---

## 4. `EditTarget` — modified

`src/choom/tui/edit_screen.py`. One field added, defaulted, so both existing construction sites and any
future one stay valid.

| Field | Type | Status | Meaning |
|---|---|---|---|
| `text`, `display_path`, `save`, `ai_line_offset`, `stamps_frontmatter`, `captures_tasks` | — | unchanged | — |
| `body_task_id` | `str \| None = None` | **new** | The id of the task whose body this buffer is, or `None` when the buffer is a document |

Set by `open_task_editor` (which already has the id in hand); left at the default by `open_editor`.

**Why it is needed**: FR-024 must refuse when the target line is a task line for the very task whose body
is being edited. `captures_tasks=False` says "this is a task body" but not *which* task, and the id is
otherwise reachable only inside `open_task_editor`'s `_save` closure (research R9).

This is adapter state describing what the adapter has open, so it belongs on `EditTarget` rather than in
`core`. It is passed *into* core as an argument; core stores nothing.

---

## 5. What is deliberately not modelled

- **No undo record.** The editor's own history holds the text edit; the task record's removal is not
  undoable and is not tracked (research R2).
- **No trash, archive, or tombstone.** Deletion is removal, here as everywhere else in choom today
  (FR-034). Issue #43 may change what removal means; it will change it in `delete_task`, which this
  feature calls rather than reimplements.
- **No persisted plan.** `MirrorDeletion` never outlives the keystroke.
- **No new frontmatter field, no new metadata token, no new comment key.** The task line's shape and the
  task record's shape are both unchanged by this feature.
