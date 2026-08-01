# Contract: Task Lines in an Assistant Reply

**Feature**: 012-assistant-task-syntax | **Date**: 2026-08-01

Three surfaces: what the prompt promises an assistant, what the classifier guarantees about a line, and
what the capture walk does with the result. The fourth section records the TUI behaviour that hangs off
them.

---

## 1. The prompt clause

`compose_prompt(user_prompt, document, line, *, task_capture: bool)`.

When `task_capture` is `True`, the composed prompt carries a task syntax clause. When it is `False`, the
clause is absent and the prompt is byte-identical to today's.

**Guarantees**:

- The clause is one constant, appended verbatim. It is therefore identical for every profile in
  `PROFILES` — no per-assistant wording exists, and none may be added (FR-006).
- It sits after the "Do not edit any file" instruction and reconciles the two: writing a task line is not
  editing a file, because choom performs the write (research R4).
- It states, at minimum: both forms (`/task <description>`, `/task.<type> <description>`); that `#tags`
  inside the description are lifted out and attached to the task; that the line must be its entire
  content, unindented, and outside any code fence; that choom replaces the line with a link to the task it
  creates; and that emitting one is optional (FR-001 – FR-005).

**Callers**: `task_capture=True` for a document (`open_editor`); `False` for a task body
(`open_task_editor`), which has no document identity to link a capture from (FR-007).

---

## 2. `parse_reply_lines(text) -> tuple[ReplyLine, ...]`

`core/editor_commands.py`. Pure: no workspace, no filesystem, no clock. Raises nothing.

**Input**: the assistant's reply text, already reduced to its final answer by the profile's
`parse_reply` (#69) and normalised for line endings by the existing reply path.

**Output**: one `ReplyLine` per input line, in order.

**A line is eligible** (`task` is non-`None`) when all of these hold:

| # | Rule | Rejects |
|---|------|---------|
| 1 | Not inside a fenced code block | ` ```\n/task call Terry\n``` ` |
| 2 | No leading whitespace | `  /task call Terry`, a task line nested under a bullet |
| 3 | `parse_line` returns a command | `/tas call Terry`, `Did you know you can type /task here?` |
| 4 | That command is named `task` | `/ai ...`, `/link ...`, any future verb |

**Fence tracking**:

- An opening fence is three or more backticks or three or more tildes, after at most three leading spaces,
  with or without an info string.
- A closing fence uses the same character, is at least as long as the opener, and carries no info string.
- A fence that is never closed puts every remaining line inside it. Nothing after an unclosed fence is
  captured — the safe direction (spec edge case).
- Indented (four-space) code blocks need no handling: rule 2 already excludes their contents.

**Non-guarantees**: eligibility is not usability. `/task` with no description is eligible and parses to an
empty `argument`; rejecting it is `capture_task`'s job, so that the reply path and the editor give the
same message for the same mistake (FR-015).

---

## 3. `capture_reply_tasks(workspace, text, *, source, source_id) -> ReplyCapture`

`core/mirrors.py`. Writes `tasks.md` through `capture_task` and nothing else.

**Behaviour**:

1. Classify with `parse_reply_lines`.
2. For each eligible line, top to bottom, call
   `capture_task(workspace, argument, type=suffix, source=source, source_id=source_id)`.
3. On success, substitute the returned mirror line for that line's text.
4. On `UsageError` or `WorkspaceError`, leave the line exactly as the assistant wrote it and record a
   `ScanWarning(path=workspace.tasks_file, reason="reply_capture_failed", message=str(exc))`.
5. Return `ReplyCapture(text, tasks, warnings)`.

**Guarantees**:

- **No line is lost.** The output has the same line count and ordering as the input, under every outcome
  including total failure (FR-017).
- **Order is the reply's order.** Tasks reach `tasks.md` in the order the assistant listed them.
- **Partial failure is normal.** One failing line stops nothing; the lines after it are still captured
  (FR-016).
- **No eligible lines means no work.** The input string is returned unchanged, no read or write happens,
  and both tuples are empty (FR-011).
- **Only the two documented exceptions are caught.** Anything else propagates — a bug stays loud (R10).
- **Every task is indistinguishable from a typed one.** All shaping happens inside `capture_task`, which
  this function does not reimplement any part of (FR-021).

---

## 4. TUI behaviour (`tui/edit_screen.py`)

**Where the walk runs**: inside `_finish_request`, after the superseded check and only when `reply.ok`.
A cancelled, failed, or superseded request creates no task and restores the `/ai` line exactly as today
(FR-019, research R5).

**The insert**: one `editor.replace()` of the `⋯` placeholder span with `ReplyCapture.text` — the same
single call the reply path makes today, so undo remains one step and does not remove the created tasks
(FR-024, research R6).

**Mirror baseline**: `_mirror_baseline[task.id] = False` for every task in `ReplyCapture.tasks`, so a
freshly inserted mirror is not read at the next save as a state change the user made (FR-023).

**Status line**, composed from the result (research R8):

| Outcome | Message | `⚠` |
|---------|---------|-----|
| No eligible lines | none — the plain `EDIT_HELP` footer, exactly as today | — |
| All captured, ≥1 | `1 task captured` / `3 tasks captured` | no |
| Some captured, some failed | `2 tasks captured; 1 could not be: <first reason>` | yes |
| All failed | `<first reason>` | yes |

This requires `_render_status(note, *, warn: bool = True)`; a successful capture is news, not a warning,
and prefixing it with `⚠` would teach the user to ignore the marker (Principle V).

**Unchanged**: no screen push, no collection change, no scroll change; the editor keeps focus (FR-020).
