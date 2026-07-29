# Data Model: 003-tasks

**Feature**: [spec.md](./spec.md) | **Decisions**: [research.md](./research.md)

Tasks add no new storage location and no new file format beyond a line shape. `tasks.md` at the
workspace root is the whole model. This document fixes the grammar of a task line, how a line is
classified when it is damaged, and what the in-memory records look like.

---

## Entity: Workspace (extended)

One property is added to the existing frozen dataclass:

```python
@property
def tasks_file(self) -> Path:      # self.root / "tasks.md"
```

`init_workspace` already creates the file empty; nothing about workspace discovery changes.

---

## Entity: Task

The in-memory record. Frozen, slotted, no methods — the same shape of thing as `Document`, but not
one of them: a task has no path, no frontmatter, and no file of its own.

```python
@dataclass(frozen=True, slots=True)
class Task:
    id: str | None          # None only when backfill could not be written (FR-038)
    text: str               # the user's words, tags removed, metadata comment removed
    done: bool
    type: str               # "" when untyped
    tags: tuple[str, ...]   # () when none
    created: date | None    # None for a hand-written line, or an unparseable value
    line: int               # 1-based line number in tasks.md; display and diagnostics only
```

### Field rules

| Field | Rule |
|---|---|
| `id` | `t_` + 4 lowercase hex on write. On read, any `[A-Za-z0-9_-]+` is accepted, so a hand-written `id:groceries` works. Unique within the file; duplicates are a refusal, not a repair (FR-030). |
| `text` | Everything between the checkbox and the metadata comment, with trailing whitespace stripped. Never normalized, never re-cased, never re-wrapped. May contain any character including `<!--`. |
| `done` | `[x]` or `[X]` → `True`; `[ ]` → `False`. Nothing else is a checkbox. |
| `type` | Validated by the existing `_TOKEN_PATTERN` (`[A-Za-z0-9][A-Za-z0-9_-]{0,39}`), lowercased on write, as for meetings. |
| `tags` | Same token rule, comma-separated in the comment, order preserved, duplicates removed. |
| `created` | ISO `YYYY-MM-DD`. Written by `add_task`, never rewritten afterwards, never invented for a hand-written line ([R8](./research.md#r8-a-hand-written-task-has-no-creation-date-and-endpaper-does-not-invent-one)). |
| `line` | Assigned at parse time. **No writer consumes it** — writers locate by `id` ([R7](./research.md#r7-locate-by-identifier-at-write-time-never-by-cached-line-number)). |

There is no `updated` field and no `completed` field. The checkbox is the state; adding a timestamp
would extend the documented line format for information no requirement asks for.

---

## The task line

### Grammar

```
task_line   := indent marker ws "[" state "]" ws text [ ws comment ] eol
indent      := [ \t]*
marker      := "-" | "*" | "+"
state       := " " | "x" | "X"
comment     := "<!--" ws field { ws field } ws "-->"
field       := ("id:" idval) | ("type:" token) | ("tags:" token {"," token}) | ("created:" isodate)
idval       := [A-Za-z0-9_-]+
token       := [A-Za-z0-9][A-Za-z0-9_-]{0,39}
```

Written form — fields always in this order, absent fields omitted entirely rather than written empty
(FR-013):

```markdown
- [ ] send the vendor comparison <!-- id:t_a1b2 type:followup tags:procurement,q3 created:2026-07-28 -->
- [x] book the room <!-- id:t_9f0e created:2026-07-27 -->
- [ ] buy milk <!-- id:t_5c31 -->
```

### Classification of a line

Applied in order. Only the **last** `<!-- ... -->` on the line is considered as metadata.

| Condition | Class | Result |
|---|---|---|
| Does not match `task_line` | **not a task** | Preserved verbatim, never interpreted, never rewritten |
| No `<!--` on the line | **bare** | Listed; id backfilled in place |
| `<!--` present, no `-->` | **malformed** | Skipped, warned (`task_unterminated_comment`), left byte-identical |
| Comment closed, contains no recognized key | **bare** | The comment is the user's prose; listed; backfill appends a new comment after it |
| Comment closed, has a recognized key and an unparseable or unknown token | **malformed** | Skipped, warned (`task_malformed_comment`), left byte-identical |
| Comment closed and well-formed, `created` not an ISO date | **task** | Listed with `created=None`, warned (`task_invalid_value`) |
| Comment closed and well-formed | **task** | Listed |

The last two rows are the deliberate asymmetry explained in
[R2](./research.md#r2-the-metadata-comment-and-what-malformed-means): structural damage hides the
extent of the metadata and so skips the line, while value damage costs one field and keeps the
user's words visible.

### Warnings

`ScanWarningReason` gains three members, and `ScanWarning.path` is `tasks.md` for all of them:

```
"task_unterminated_comment" | "task_malformed_comment" | "task_invalid_value"
```

Warnings are data, never exceptions (Principle IV). Adapters print them to stderr; nothing about a
warning changes an exit code.

---

## Entity: ParsedTasks (the pure parse result)

```python
@dataclass(frozen=True, slots=True)
class ParsedTasks:
    tasks: tuple[Task, ...]
    warnings: tuple[ScanWarning, ...]
    lines: tuple[str, ...]          # every line, terminators included, in file order
    needs_id: tuple[int, ...]       # 0-based indices into `lines` that are bare tasks
```

`lines` is what makes byte-preservation testable: `"".join(parsed.lines)` must equal the input text
exactly, for every input, including mixed line endings and a missing final newline. That is a single
property test over the whole classification table.

`needs_id` is how a pure function reports repair work without doing it — `load_tasks` is the only
thing that acts on it ([R5](./research.md#r5-who-writes-the-backfilled-identifiers-and-when)).

---

## Entity: TaskFilter

```python
@dataclass(frozen=True, slots=True)
class TaskFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    include_done: bool = False
```

Filters combine conjunctively. `include_done=False` (the default) drops completed tasks; `--all` and
the TUI's `a` set it True. Tag and type matching is exact and case-insensitive, matching
`filter_meetings`.

---

## Entity: Task list record (the wire projection)

`task list --json` emits exactly seven keys per object, in this order, and never omits one:

| Key | Type | Notes |
|---|---|---|
| `id` | string \| null | null only when backfill could not be written |
| `text` | string | the user's words |
| `done` | boolean | |
| `type` | string | `""` when untyped, never null |
| `tags` | array of string | `[]` when none, never null |
| `created` | string \| null | `YYYY-MM-DD`, or null when unknown |
| `line` | number | 1-based |

`type` and `tags` follow the meeting schema's convention — empty rather than null — because they are
always meaningful. `id` and `created` are genuinely unknown in the cases above, so they are null.

---

## Sorting

1. Tasks with a `created` date, ascending (oldest first).
2. Tasks without one, after those, in file order.
3. Ties within the same date keep file order.

Oldest-first is the opposite of the meeting list and intentional: an open task list is a queue to
work through, a meeting list is a history to browse. Implemented as a stable sort over the file
order, which is why parse order is preserved end to end.

---

## State transitions

A task has exactly two states and one transition in each direction:

```
open  --(space | task done)-->  done
done  --(space | task undone)-->  open
```

- Both directions are one keystroke or one command, both call `set_task_state`, and both produce
  byte-identical files (FR-026).
- Setting the state a task already has is a no-op: exit 0, file untouched, no write attempted
  (FR-028).
- The transition changes exactly one character on the line — the checkbox — and nothing else
  (FR-027). Indentation, bullet marker, spacing, text, comment, and trailing whitespace all survive.
- There is no delete transition. Removing a task is deleting a line in a markdown file, which the
  user does in their editor; v0.0.1 provides no command for it and REQUIREMENTS.md does not ask for
  one.

---

## Writing

Every write follows [R6](./research.md#r6-writing-without-losing-anything):

1. Read with `newline=""`, so terminators survive.
2. `splitlines(keepends=True)`.
3. Replace or append exactly one line.
4. Write a temp file in the same directory; `os.replace` over the original.

| Operation | Touches | Final newline |
|---|---|---|
| `add_task` | Appends one line | Adds the terminator the previously-final line lacked, and terminates the new line |
| `set_task_state` | One character on one line | Preserved exactly, including its absence |
| Backfill | Appends a comment to one or more bare lines | Preserved exactly, including its absence |

A failed write raises `WorkspaceError` (exit 3) and leaves the original file untouched.

---

## Known limitations

- **A `- [ ]` inside a fenced code block is parsed as a task.** The parser is line-oriented and does
  not track fence state. In a file whose purpose is tasks this is pathological, and tracking fences
  would mean carrying block context through a parser whose simplicity is the reason it is
  trustworthy. Revisit only if it happens to a real user.
- **Two tasks may carry the same id if a user copy-pastes a line.** Detected, never silently
  repaired: any command targeting that id refuses and names the line numbers (FR-030). Repairing
  would mean choosing which line keeps the id, and that is the user's call.
- **No file locking.** Simultaneous edits from two synced copies are out of scope per
  REQUIREMENTS.md §5; OneDrive's conflict-copy behaviour is the answer. Re-reading immediately
  before every write keeps the window to milliseconds.
