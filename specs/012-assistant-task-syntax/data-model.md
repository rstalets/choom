# Phase 1 Data Model: Linked Task Syntax for AI Assistant

**Feature**: 012-assistant-task-syntax | **Date**: 2026-08-01

This feature introduces no persisted state. Both new shapes are in-memory values that exist for the
duration of one reply, and nothing about a task, a mirror, or a document changes.

---

## New shapes

### `ReplyLine` (frozen dataclass, `core/models.py`)

One line of an assistant reply, classified.

| Field | Type | Meaning |
|-------|------|---------|
| `text` | `str` | The line exactly as the assistant wrote it, without its line terminator. Never modified by the classifier. |
| `task` | `ParsedCommand \| None` | The parsed task command when this line is eligible for capture; `None` for every other line, including ineligible `/task` mentions and other commands. |

**Invariants**:

- `parse_reply_lines(text)` returns exactly as many `ReplyLine`s as `text` has lines, in order. No line is
  dropped, merged, or reordered (FR-017).
- `task` is non-`None` only when `text` starts with `/`, has no leading whitespace, sits outside any
  fenced code block, and `parse_line(text)` returned a command named `task` (FR-012, FR-013, FR-014).
- `task.command.name == "task"` whenever `task` is not `None`. No other verb is ever carried.
- A `task` may still be unusable — `/task` with no description parses but has an empty `argument`. The
  classifier does not judge that; `capture_task` rejects it and the line survives as text (FR-015).

### `ReplyCapture` (frozen dataclass, `core/models.py`)

The outcome of walking one reply.

| Field | Type | Meaning |
|-------|------|---------|
| `text` | `str` | The reply with every successfully captured line replaced by its mirror line, and every other line byte-identical to the input. This is what the editor inserts. |
| `tasks` | `tuple[Task, ...]` | The tasks created, in the order their lines appeared in the reply. Empty when the reply had no eligible lines or none could be captured. |
| `warnings` | `tuple[ScanWarning, ...]` | One per line that was eligible but could not be captured, carrying the reason (FR-016, FR-018). |

**Invariants**:

- `text` has the same line ordering as the input, and the same number of lines except where a blank
  line lay between two captured lines, which is dropped so a loose list of task lines lands as a tight
  checklist (FR-010a). No line carrying a character is ever dropped.
- A reply with no eligible lines returns `text` unchanged — identical to its input, not merely equal in
  content (FR-011). This is what makes "behaves exactly as `/ai` does today" checkable.
- `len(tasks) + len(warnings)` equals the number of eligible lines.
- Every `Task` in `tasks` has a non-`None` `id`, because `capture_task` returns only written tasks.

### `ScanWarningReason` gains `"reply_capture_failed"`

Additive. Raised for a line that was eligible but whose `capture_task` call raised `UsageError` (empty
description after tag extraction, or a rejected type or tag token) or `WorkspaceError` (`tasks.md` could
not be written). The warning's `path` is the workspace's `tasks_file`; its `message` is the exception's
own text, which already names what went wrong and what to do instead.

---

## Existing entities

None change shape. What each is to this feature:

- **`Task`** — created by `capture_task`, exactly as a typed `/task` creates one: same id scheme, same
  `#tag` extraction, same type suffix, same validation, same link back to the source document. A task
  captured from a reply is distinguishable from a typed one only by id and timestamp (FR-021).
- **`Mirror`** — the checklist item substituted for a captured line. Produced by the existing
  `mirrors.mirror_line`, so it participates in reconciliation in both directions with no additional code
  (FR-022).
- **`ParsedCommand`** — unchanged, and still produced only by `parse_line`. The classifier calls that
  function rather than restating the grammar, which is what keeps the editor, the command bar, and the
  reply path in agreement.
- **`AssistantReply`** — unchanged. Its `text` is already each assistant's final answer with tool-call
  narration stripped (#69), and that is the string the classifier receives.
- **`EditTarget`** (TUI) — gains `captures_tasks: bool`. `True` for a document opened by `open_editor`,
  `False` for a task body opened by `open_task_editor`. Read by both `compose_prompt`'s new flag and the
  existing `/task` guard, which stops inferring the same fact from `stamps_frontmatter`.

---

## What a capture writes

Per eligible line, and only through `capture_task`:

1. One appended checkbox line in `tasks.md`, carrying the id, any tags, the type, and a link to the source
   document's id.
2. Nothing else. No frontmatter is stamped, no document is written, no second file is touched.

The substituted mirror text lands in the **editor buffer**, unsaved. The document on disk still holds the
`/ai` line the user submitted — it was saved in that state before the request went out, as it is today —
until the user saves again. A user who discards the buffer keeps the tasks, exactly as a discarded typed
capture does (FR-024).

## What a capture never touches

- **The document's frontmatter.** This feature stamps nothing.
- **Any line of the reply that was not eligible.** Fenced, indented, mid-sentence, another command, or
  plain prose — all inserted byte-identical (FR-010).
- **The reply, on failure.** A capture that fails leaves its line as the assistant wrote it and the rest of
  the walk continues (FR-016).
- **`tasks.md`, when the request was cancelled or superseded.** The walk runs only for a reply that will be
  inserted (research R5).
- **Anything at all, for a reply with no eligible lines.** No read, no write, no message (FR-011).
