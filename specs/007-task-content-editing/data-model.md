# Data Model: Task Content Editing

Phase 1 output for [plan.md](./plan.md). Types live in `endpaper.core.models`; behaviour lives in
`endpaper.core.tasks`.

## Task (changed)

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `id` | `str \| None` | — | Stable handle. Every write locates by this, never by `line`. |
| `text` | `str` | — | The checkbox line's text, comment stripped. |
| `done` | `bool` | — | |
| `type` | `str` | — | |
| `tags` | `tuple[str, ...]` | — | |
| `created` | `date \| None` | — | Never altered by a body write. |
| `line` | `int` | — | 1-based line of the checkbox line. Shifts as bodies grow; not a handle. |
| `body` | `str` | **new** | Dedented body text, `""` when the task has none. No trailing newline. |

`body` defaults to `""`, so every existing construction site keeps working and a task without a body
is indistinguishable from one before this feature.

**Validation.** None. A body is free markdown: no schema, no length limit, no required structure. It
is never parsed for tags, dates, or metadata — a `<!-- id:… -->` inside a body is text.

## TaskBodySpan (new, internal)

Returned alongside the parse, not part of any public output.

| Field | Type | Notes |
|-------|------|-------|
| `start` | `int` | 0-based index into `ParsedTasks.lines` of the first span line. |
| `end` | `int` | Exclusive; equals `start` when the task has no body. |
| `indent` | `str` | The common leading-whitespace prefix that was stripped; `"  "` when there was none to observe. |

`ParsedTasks` gains `bodies: tuple[TaskBodySpan, ...]`, positionally aligned with `tasks`. It exists
so the writer can splice without re-deriving boundaries, and it is not exposed by the CLI or the TUI.

## Core functions

```python
def parse_tasks(text: str) -> ParsedTasks: ...
```
Unchanged contract — never raises, `"".join(result.lines) == text` still holds for any input. Now
also populates `Task.body` and `ParsedTasks.bodies`.

```python
def get_task(workspace: Workspace, task_id: str) -> Task: ...
```
One task with its body. Raises `NotFoundError` when no task has that id, `UsageError` when more than
one does (naming the conflicting line numbers, as `set_task_state` does).

```python
def set_task_body(workspace: Workspace, task_id: str, body: str) -> Task: ...
```
Replaces the task's body span with `body`, re-indented by the span's observed prefix. Re-reads and
re-parses first; locates by id. Returns without writing when the body is unchanged. An empty `body`
removes the span entirely, leaving a lone task line. Every line outside the span is byte-identical.
Raises `NotFoundError` / `UsageError` on the same conditions as `get_task`, `WorkspaceError` when the
file cannot be written.

## State transitions

A body has three states and four transitions, all of them one write:

```text
        set_task_body(id, text)              set_task_body(id, "")
none ─────────────────────────────► present ─────────────────────────────► none
                                     │  ▲
              set_task_body(id, text)│  │ same text -> no write at all
                                     └──┘
```

`set_task_state` (the `space` toggle) is orthogonal: it changes one character on the checkbox line
and never reads or touches the span.

## File format

The on-disk shape and its edge cases are specified in
[contracts/task-file-format.md](./contracts/task-file-format.md).
