# Contract: `endpaper.core` public API (notes)

**Baseline**: [feature 001's core-api contract](../../001-meeting-notes/contracts/core-api.md). This
page records what this feature adds and what it generalises. Anything not mentioned is unchanged.

**Hard rule, unchanged**: nothing in `core` imports `argparse`, `textual`, `rich`, or `sys.stdout`.
The existing import-walk test covers the new modules with no edit.

---

## Module layout

| Module | Role |
|---|---|
| `core/documents.py` | **new** — the generic implementation. `create_document`, `scan_documents`, `filter_documents`, `match_document`, token validation. |
| `core/meetings.py` | **changed** — shrinks to the `MEETINGS` descriptor plus bound wrappers with feature 001's exact signatures. |
| `core/notes.py` | **new** — the `NOTES` descriptor, `create_note`, `scan_notes`, `open_daily_note`. |

`meetings.py` and `notes.py` hold no logic. If either grows a branch that the other does not have,
FR-011 has been broken and the branch belongs in `documents.py` behind a `Collection` field.

---

## Types

Added to `core/models.py`. See [data-model.md](../data-model.md) for field-level rules.

```python
@dataclass(frozen=True, slots=True)
class Collection:
    id_prefix: str                    # "m_" | "n_"
    create_dir: str                   # relative to workspace root
    scan_dirs: tuple[str, ...]        # relative to workspace root, scanned in order
    reserved_types: frozenset[str]

@dataclass(frozen=True, slots=True)
class DailyNote:
    path: Path                        # always present; the file exists when this returns
    document: Document | None         # None when an existing file's frontmatter does not parse
    created: bool                     # True only when this call created the file
```

Renamed, with aliases retained so feature 001 compiles untouched:

```python
Document = ...            # was Meeting; fields unchanged
Meeting = Document        # alias
Note = Document           # alias
DocumentFilter = ...      # was MeetingFilter; fields unchanged
MeetingFilter = DocumentFilter   # alias
```

`Workspace` gains `notes_dir` and `daily_dir` properties.

---

## Generic document functions

```python
def create_document(
    workspace: Workspace,
    collection: Collection,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Document:
    """Create exactly one document file in `collection.create_dir` and return its record.

    Behaviour is feature 001's create_meeting, verbatim, with the directory, the id prefix, and
    the reserved-type set taken from `collection`.

    Never reads, modifies, or overwrites an existing file: collisions get -2, -3, ... via
    exclusive create.

    Raises UsageError, before any filesystem work, if the description is empty after tag
    stripping, if `type` or any tag fails token validation, or if `type` is in
    `collection.reserved_types`.
    """

def scan_documents(
    workspace: Workspace,
    collection: Collection,
) -> tuple[list[Document], list[ScanWarning]]:
    """Read every *.md in each of `collection.scan_dirs` and return the ones that parse, plus
    warnings for the ones that do not.

    Each directory is globbed non-recursively, so a nested directory a user creates is ignored
    rather than swept in. A missing directory contributes nothing and is not a warning.

    Never raises. Never rewrites, repairs, moves, or deletes a file. Sorted by created
    descending, ties by path ascending.
    """

def filter_documents(documents: Iterable[Document], f: DocumentFilter) -> list[Document]:
    """Apply type / tags / since conjunctively. Pure; no I/O."""

def match_document(document: Document, query: str) -> bool:
    """Case-insensitive substring test over title, type, and tags. Pure."""
```

Feature 001's `create_meeting`, `scan_meetings`, `filter_meetings`, and `match_meeting` remain
exported with unchanged signatures, each a one-line binding. Removing them is a breaking change and
is not proposed.

---

## Notes

```python
NOTES: Collection   # id_prefix "n_", create_dir "notes",
                    # scan_dirs ("notes", "notes/daily"), reserved_types {"daily"}

def create_note(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Document:
    """create_document bound to NOTES.

    Raises UsageError naming `endpaper note today` when `type` is "daily" (FR-012).
    """

def scan_notes(workspace: Workspace) -> tuple[list[Document], list[ScanWarning]]:
    """scan_documents bound to NOTES. Returns typed notes and daily notes as one list."""

def open_daily_note(workspace: Workspace, *, now: datetime | None = None) -> DailyNote:
    """Return today's daily note, creating it only if no file exists at its path.

    The path is notes/daily/YYYY-MM-DD.md, built from `now` (or the current local time).
    Creates notes/daily/ if absent.

    Idempotent by construction: the file is opened with O_CREAT|O_EXCL, so an existing file is
    never opened for writing. FileExistsError is the "already exists" path, which makes the
    create-or-open decision atomic and safe against a second process and against a sync client
    materialising the file mid-call.

    An existing file is NEVER modified -- not its body, not its frontmatter, not its `updated`
    field, not its mtime. An existing file whose frontmatter does not parse is still returned
    (it is that day's note, FR-005), with document=None; it is neither repaired nor rewritten.

    Never raises for a malformed existing file. Filesystem errors (read-only directory, disk
    full) propagate as OSError, as they do for create_document.
    """
```

---

## Text helpers

```python
def new_document_id(when: date, prefix: str) -> str:
    """<prefix>YYYYMMDD_ + 8 lowercase hex from secrets.token_hex(4)."""

def new_meeting_id(when: date) -> str:
    """Unchanged. Now new_document_id(when, "m_")."""
```

---

## Frontmatter

`render_frontmatter(document: Document) -> str` — signature unchanged in effect, since `Meeting` is
now an alias of `Document`. The emitter is untouched: the same six keys, the same fixed order, the
same quoting.

This matters more than it looks. A daily note and a meeting written on the same day produce files
that differ only in their `id` prefix, `type`, `title`, and directory. There is one emitter, so
there is no way for the two kinds to drift into different quoting or key order.

---

## The one-write-path rules

Feature 001 had one. This feature has two, and the distinction is the whole feature:

| Rule | Function | Guarantee |
|---|---|---|
| Every meeting and every typed note file is written by | `create_document` | Never touches an existing file; collisions suffix |
| Every daily note file is written by | `open_daily_note` | Never touches an existing file; no suffix ever, because there is exactly one per day |

Both use `O_CREAT|O_EXCL`. Neither has a code path that opens an existing file for writing. That is
what makes SC-003's "byte-identical, 0% unrequested modification" a property of the design rather
than something a test hopes to catch — and the test asserts bytes *and* `st_mtime_ns`
([R10](../research.md#r10-test-strategy-for-the-file-did-not-change)) so that a future no-op rewrite
fails rather than passes.

**Parity test** (spec US2 scenario 2): with a fixed `now` and a seeded id, `create_note` called via
the CLI handler and via the TUI's command-bar path produce files identical in every byte except
`id`, `created`, and `updated` — the same test feature 001 runs for meetings, pointed at notes.
