# Contract: `endpaper.core` public API

**Why this is a contract**: Principle I makes `core` the product and the CLI and TUI peer adapters
over it. That only holds if both call the same functions. Anything either adapter needs that is not
here is a gap in `core`, not a reason for the adapter to reach for the filesystem itself.

**Hard rule**: nothing in `core` imports `argparse`, `textual`, `rich`, or `sys.stdout`. `core`
returns data and raises exceptions; formatting and exit codes belong to the adapters. A test asserts
this by walking `core`'s imports.

---

## Types

```python
@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path
    @property
    def meetings_dir(self) -> Path: ...   # collection root; files live in YYYY/MM/ beneath it

@dataclass(frozen=True, slots=True)
class Meeting:
    id: str
    path: Path
    title: str
    type: str
    tags: tuple[str, ...]
    created: str
    updated: str

@dataclass(frozen=True, slots=True)
class ScanWarning:
    path: Path
    reason: Literal[
        "no_frontmatter", "unterminated_frontmatter", "malformed_yaml",
        "not_a_mapping", "missing_fields", "unexpected_fields", "invalid_value",
    ]
    message: str

@dataclass(frozen=True, slots=True)
class MeetingFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    since: date | None = None
```

---

## Exceptions

```python
class EndpaperError(Exception):
    """Base. Carries the exit code the CLI should use."""
    exit_code: ClassVar[int]

class NotFoundError(EndpaperError):   exit_code = 1
class UsageError(EndpaperError):      exit_code = 2
class WorkspaceError(EndpaperError):  exit_code = 3
```

Adapters map `EndpaperError.exit_code` directly to the process exit code. Nothing else in `core`
raises to the caller by design — scans return warnings as data rather than raising (Principle IV).

---

## Workspace

```python
def find_workspace(start: Path) -> Workspace:
    """Walk up from `start` looking for .endpaper/config.toml.

    Raises WorkspaceError if no workspace is found before the filesystem root,
    or if the marker declares a schema version this build does not support.
    """

def init_workspace(target: Path) -> Workspace:
    """Create the endpaper layout in `target`.

    Writes meetings/, notes/daily/, tasks.md, AGENTS.md, then .endpaper/config.toml LAST,
    so an interrupted init leaves a directory that is not yet a workspace.

    Raises WorkspaceError if `target` already contains .endpaper/, without writing anything.
    """
```

---

## Meetings

```python
def create_meeting(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Meeting:
    """Create exactly one meeting file and return its record.

    `description` may contain inline #tag tokens; they are parsed out and merged with `tags`,
    preserving order and removing duplicates.

    `now` is injectable so tests can fix the date without patching the clock globally. Production
    callers omit it.

    Never reads, modifies, or overwrites an existing file. Collisions get -2, -3, ... via
    exclusive create.

    Raises UsageError if the description is empty after tag stripping, or if `type` or any tag
    fails validation.
    """

def scan_meetings(workspace: Workspace) -> tuple[list[Meeting], list[ScanWarning]]:
    """Read every *.md in meetings/ and return the ones that parse, plus warnings for the ones
    that do not.

    Never raises. Never rewrites, repairs, moves, or deletes a file. A malformed file is skipped
    and every other meeting still returns. Sorted by created descending, ties by path ascending.
    """

def filter_meetings(meetings: Iterable[Meeting], f: MeetingFilter) -> list[Meeting]:
    """Apply --type / --tag / --since conjunctively. Pure; no I/O."""

def match_meeting(meeting: Meeting, query: str) -> bool:
    """Case-insensitive substring test over title, type, and tags. Pure.

    This is the TUI live filter's predicate, in core so the CLI could expose it later
    and so it is testable without a terminal.
    """
```

---

## Text helpers

```python
def slugify(text: str, *, max_length: int = 40) -> str:
    """NFKD, casefold, non-alphanumerics to single hyphens, strip, truncate,
    strip trailing hyphen from the cut. Returns 'untitled' if nothing survives."""

def parse_tags(description: str) -> tuple[str, str]:
    """Split a description into (title, tags-as-csv-free-tuple).

    Removes #tag tokens from anywhere in the string, collapses the whitespace they leave behind,
    and preserves the original casing of the remaining title.
    """

def new_meeting_id(when: date) -> str:
    """m_YYYYMMDD_ + 8 lowercase hex from secrets.token_hex(4)."""
```

---

## Frontmatter

Deliberately asymmetric — see [research.md](../research.md#r2-frontmatter-parsing-and-writing).

```python
def read_frontmatter(text: str) -> dict[str, str | list[str]]:
    """Tolerant read via yaml.safe_load, then coerce every scalar back to str.

    The coercion is what undoes YAML 1.1 turning `no` into False and a bare timestamp into a
    datetime. Raises FrontmatterError (internal, never escapes scan_meetings) on any structural
    problem.
    """

def render_frontmatter(meeting: Meeting) -> str:
    """Deterministic emitter. Six keys, fixed order, title and tags always double-quoted,
    timestamps unquoted, no line wrapping at any title length.

    NOT yaml.safe_dump: that sorts keys, picks its own quoting, and wraps at 80 columns, which
    would break round-tripping of long titles and the CLI/TUI identical-output requirement.
    """
```

---

## The one-create-path rule

`create_meeting` is the only function in the codebase that writes a meeting file. The CLI's
`meeting new` and the TUI's `/meeting.<type>` both call it with the same arguments and do nothing
else.

This is what makes spec US2 scenario 2 testable: the two front doors produce files identical in
every field except `id`, `created`, and `updated`. The test injects a fixed `now` and a seeded id,
calls both paths, and diffs the bytes.
