# Contract: `core` API

**Feature**: `017-editor-task-delete` | **Module**: `src/choom/core/mirrors.py`

Two new public functions. Both are callable with a `Workspace` and a string, with no terminal, no TTY,
and no event loop (Principle I). Neither imports anything from `choom.cli` or `choom.tui`.

---

## 1. `plan_mirror_deletion`

```python
def plan_mirror_deletion(
    workspace: Workspace,
    text: str,
    line: int,
    *,
    source: Path,
    body_task_id: str | None = None,
) -> MirrorDeletion | None:
```

Decide what deleting the task line at `line` would do, without doing any of it.

**Parameters**

| Name | Meaning |
|---|---|
| `text` | The document text as the editor holds it — LF-only, frontmatter included |
| `line` | **1-based**, matching `Mirror.line`, `Task.line`, and `Link.line`. The adapter adds 1 to a 0-based widget row |
| `source` | The document's path, needed to resolve link destinations. Never opened by this function |
| `body_task_id` | The task whose body `text` is, or `None` when `text` is a document (FR-024) |

**Returns** `None` when `line` carries no task line — FR-008's no-op. That is the answer for prose, a
heading, a blank line, frontmatter, a plain checklist item with no link, a checklist item whose only link
is not a task link, and any line inside a fenced code block or inline code span (the exclusion comes free
from `find_links`, which `find_mirrors` already delegates to).

Otherwise returns a `MirrorDeletion` whose `outcome` is one of the five in
[data-model.md §2](../data-model.md), decided in this order:

1. `body_task_id` is not `None` and equals the line's task id → **`self_referential`**
2. Exactly one task record carries the id → **`deletable`**
3. More than one task record carries the id → **`ambiguous_id`**
4. No task record carries the id, and `parse_tasks` reported `task_unterminated_comment` or
   `task_malformed_comment` → **`unreadable_tasks`**
5. No task record carries the id, and it reported neither → **`line_only`**

Order matters at 3 vs 4: an ambiguous id is a definite finding and gets the more specific message even in
a file that also has an unreadable line elsewhere.

**Guarantees**

- **Writes nothing.** Not `tasks.md`, not the document, not per-user state. Reads `workspace.tasks_file`
  through `parse_tasks`, never `load_tasks` — the latter backfills ids and writes, which a step running
  before the user has confirmed must not do (research R6).
- `text` and `span` satisfy `plan.text == text[: span[0]] + text[span[1] :]` on every non-refusing
  outcome.
- Exactly one line's worth of characters is spanned. Blank lines above and below, indented continuation
  beneath, and every other byte of `text` are outside the span by construction.
- Never raises. A missing `tasks.md` is `line_only` (no record exists, nothing unparseable). An
  unreadable `tasks.md` is `unreadable_tasks` with the OS error in `message`.

**Raises**: nothing.

---

## 2. `commit_mirror_deletion`

```python
def commit_mirror_deletion(workspace: Workspace, plan: MirrorDeletion) -> MirrorDeletion:
```

Carry out the `tasks.md` half of a plan the user has confirmed. **Never touches the document** — the
caller owns the buffer and applies `plan.span` itself.

- `outcome == "deletable"` → calls `tasks.delete_task(workspace, plan.task_id)`, which removes the
  checkbox line and its whole indented body span and leaves every other line byte-identical, preserving
  the file's line-ending convention and trailing-newline state. Returns `plan` unchanged on success.
- `outcome == "line_only"` → returns `plan` unchanged, having opened nothing. There is no record to
  remove.
- Any refusing outcome → raises `UsageError`. Reaching here with one is a caller bug, not a user error;
  the adapter is required to stop at the plan step.

**Raises**

| Exception | When |
|---|---|
| `NotFoundError` | The record disappeared between plan and commit (another process) |
| `UsageError` | The id became ambiguous between plan and commit, or a refusing outcome was passed |
| `WorkspaceError` | `tasks.md` could not be written |

All three leave `tasks.md` byte-identical — `delete_task` re-reads, re-parses, and locates by id before
writing, so a stale plan cannot splice into a moved line.

---

## 3. `find_mirrors` — behaviour change

`Mirror` gains `link_start` and `link_end` (data-model §1). `find_mirrors` populates them from the `Link`
it already selects. No change to which lines are recognised, which link on a line wins, or the order
mirrors are returned in.

---

## 4. What is not added

- **No CLI command, flag, `--json` key, or exit code.** `choom task delete <id> --force` already exists
  and is unchanged, including its documented behaviour of leaving task lines in documents pointing at
  nothing (pinned by `tests/integration/test_delete_mirrors.py`). See spec.md §"Interface parity".
- **No new module.** Both functions live in `core/mirrors.py`, whose stated domain is this edge.
- **No change to `delete_task`, `delete_by_id`, `save_buffer`, `set_task_body`, or `reconcile_on_save`.**
  All four are called as they stand.
