# Contract: `endpaper.core.tasks` public API

Extends [001's core-api contract](../../001-meeting-notes/contracts/core-api.md), which stays in
force: nothing in `core` imports `argparse`, `textual`, `rich`, or `sys.stdout`; `core` returns data
and raises `EndpaperError` subclasses; formatting and exit codes belong to the adapters.

**The split that matters here**: everything above the line is pure — no `Path`, no `open()`, no
clock. Everything below it touches the filesystem and does nothing else interesting.

---

## Types

Added to `core/models.py`:

```python
@dataclass(frozen=True, slots=True)
class Task:
    id: str | None
    text: str
    done: bool
    type: str
    tags: tuple[str, ...]
    created: date | None
    line: int

@dataclass(frozen=True, slots=True)
class ParsedTasks:
    tasks: tuple[Task, ...]
    warnings: tuple[ScanWarning, ...]
    lines: tuple[str, ...]
    needs_id: tuple[int, ...]

@dataclass(frozen=True, slots=True)
class TaskFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    include_done: bool = False
```

`Workspace` gains:

```python
@property
def tasks_file(self) -> Path: ...      # self.root / "tasks.md"
```

`ScanWarningReason` gains `"task_unterminated_comment"`, `"task_malformed_comment"`,
`"task_invalid_value"`.

---

## Pure layer

```python
def parse_tasks(text: str) -> ParsedTasks:
    """Classify every line of a tasks.md document.

    Never raises. Malformed lines become warnings, not exceptions.

    Guarantees:
      - "".join(result.lines) == text, byte for byte, for any input.
      - Line order is file order; `line` on each Task is its 1-based index.
      - A line that is not a task is carried in `lines` and appears nowhere else.
    """

def render_task_line(
    text: str,
    *,
    done: bool = False,
    id: str,
    type: str = "",
    tags: Sequence[str] = (),
    created: date | None = None,
) -> str:
    """Render one task line, without a terminator.

    Fields appear in the order id, type, tags, created; empty ones are omitted.
    Raises UsageError if `text` is empty after stripping.
    """

def new_task_id(taken: Container[str]) -> str:
    """Return an unused 't_' + 4-hex identifier. Retries against `taken`."""
```

`parse_tasks` is where every acceptance criterion about hand-editing is testable as a string
comparison. `filter_tasks` and `match_task` mirror `filter_meetings` / `match_meeting`:

```python
def filter_tasks(tasks: Iterable[Task], f: TaskFilter) -> list[Task]:
    """Conjunctive filter. Sorts oldest-first, undated last, stable within a date."""

def match_task(task: Task, query: str) -> bool:
    """Case-insensitive substring over text, type, and tags. For the TUI's live filter."""
```

---

## Filesystem layer

```python
def load_tasks(workspace: Workspace) -> tuple[list[Task], list[ScanWarning]]:
    """Read tasks.md, backfill missing identifiers in place, return records.

    A missing tasks.md is an empty list, not an error.

    Backfill is best-effort: if the file cannot be written, the affected tasks are
    returned with id=None plus a warning, and the read still succeeds (FR-038).

    Never raises for malformed content. Raises WorkspaceError only if the file
    exists and cannot be read.
    """

def add_task(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Task:
    """Append one task to tasks.md and return it.

    Parses inline #tags out of `description` and merges them after `tags`, exactly as
    create_meeting does. Creates tasks.md if absent. Every pre-existing byte is
    preserved; if the file did not end with a newline, the terminator is added.

    Raises UsageError if the description is empty after tag removal, or if a type or
    tag is not a valid token. Raises WorkspaceError if the write fails.
    """

def set_task_state(workspace: Workspace, task_id: str, *, done: bool) -> Task:
    """Set one task's checkbox and return the task as it now stands.

    Re-reads and re-parses before writing; locates by id, never by a cached line
    number. Changes exactly one character on that line.

    No-op (no write) if the task already has the requested state.

    Raises NotFoundError   if no line carries `task_id`.
    Raises UsageError      if more than one does; the message names the line numbers.
    Raises WorkspaceError  if the write fails.
    """
```

### Exceptions

Reuses the existing hierarchy without extension:

| Raised | When | Exit |
|---|---|---|
| `NotFoundError` | `task_id` matches no line | 1 |
| `UsageError` | empty description, invalid type/tag token, duplicate id | 2 |
| `WorkspaceError` | no workspace; `tasks.md` unreadable or unwritable | 3 |

Malformed task lines raise nothing at all — they are `ScanWarning`s in the returned list.

---

## Re-exports

`core/__init__.py` adds `Task`, `TaskFilter`, `ParsedTasks`, `parse_tasks`, `render_task_line`,
`new_task_id`, `filter_tasks`, `match_task`, `load_tasks`, `add_task`, `set_task_state` to `__all__`.

---

## Invariants a test must hold

1. `"".join(parse_tasks(text).lines) == text` for every fixture, including CRLF, mixed endings, no
   final newline, and an empty file.
2. `load_tasks` on a file with no bare lines performs **no write** — verified by mtime and content.
3. `set_task_state` changes exactly one byte for an ASCII line, and never changes the file's length
   in lines.
4. Toggling from the CLI and toggling the same task through the TUI produce identical files.
5. No function in `core.tasks` writes to stdout or stderr.
