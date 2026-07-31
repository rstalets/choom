# Contract: `endpaper.core` public API

**Feature**: `005-ui-layout-refresh`

Every signature below is callable without a terminal, a TTY, or an event loop (Principle I). All new
functions carry type hints and a docstring stating what they return and what they raise
(Principle VI).

---

## New — `endpaper.core.documents`

### `list_months`

```python
def list_months(workspace: Workspace, collection: Collection) -> MonthListing:
    """Return the months this collection holds documents in, most-recent-first.

    Discovery is a directory listing: month folders are read from the path layout
    (`<scan_dir>/**/YYYY/MM`), never from document frontmatter, so no file is opened.
    The current month is always included, even when its folder does not exist yet.
    Directory names that are not a four-digit year or a two-digit month are ignored.

    Raises nothing. A missing or unreadable scan directory yields no months rather
    than an error.
    """
```

**Guarantees**:

- Opens zero files. A test may assert this by counting `Path.read_text` calls.
- `result.months[0]` is the most recent month; the current month sorts into place naturally.
- `notes/2026/07` and `notes/daily/2026/07` collapse to one `YearMonth(2026, 7)`.
- `result.has_unfiled` is `True` when a `*.md` exists under a scan dir outside any `YYYY/MM` folder.

### `scan_month`

```python
def scan_month(
    workspace: Workspace,
    collection: Collection,
    month: YearMonth,
) -> tuple[list[Document], list[ScanWarning]]:
    """Parse every document in one month of one collection.

    Reads `*.md` from `<scan_dir>/**/<year>/<month>/` only. Ordering and warning
    behaviour match `scan_documents`: newest `created` first, ties broken by path,
    and a document whose frontmatter cannot be read becomes a `ScanWarning` rather
    than raising.

    Raises nothing. A month with no folder returns two empty lists.
    """
```

**Guarantees**:

- Reads no file outside the requested month — the assertion behind FR-012.
- Identical parse semantics to `scan_documents`: same `_parse_document`, same warning reasons, so a
  malformed file behaves the same whether reached by a full scan or a month scan (Principle IV).
- Sort order is byte-for-byte what `scan_documents` produces for the same subset, so rows do not
  reorder when a filter widens from one month to all months.

### `scan_unfiled`

```python
def scan_unfiled(
    workspace: Workspace,
    collection: Collection,
) -> tuple[list[Document], list[ScanWarning]]:
    """Parse documents that sit outside the YYYY/MM layout.

    Covers files a user placed by hand, which `scan_month` cannot reach. Same
    ordering and warning behaviour as `scan_month`. Returns empty lists when the
    collection has no stray files.

    Raises nothing.
    """
```

---

## New — collection wrappers

Thin, for symmetry with the existing `scan_meetings` / `scan_notes` pairs. No logic.

```python
# endpaper.core.meetings
def list_meeting_months(workspace: Workspace) -> MonthListing: ...
def scan_meeting_month(workspace: Workspace, month: YearMonth) -> tuple[list[Document], list[ScanWarning]]: ...

# endpaper.core.notes
def list_note_months(workspace: Workspace) -> MonthListing: ...
def scan_note_month(workspace: Workspace, month: YearMonth) -> tuple[list[Document], list[ScanWarning]]: ...
```

---

## Changed — `endpaper.core.tasks.filter_tasks`

Signature unchanged; `TaskFilter` gains `only_done: bool = False`.

```python
def filter_tasks(tasks: Iterable[Task], f: TaskFilter) -> list[Task]:
    """Conjunctive filter. Sorts oldest-first, undated last, stable within a date.

    `only_done=True` selects completed tasks only and overrides `include_done`.
    """
```

**Compatibility**: every existing call site keeps its behaviour, because `only_done` defaults to
`False` and the two pre-existing branches are untouched.

---

## Unchanged — and required to stay unchanged

`scan_documents`, `scan_meetings`, `scan_notes` keep their full-workspace semantics. The CLI still
uses them; only the TUI moves to the month-scoped pair. Removing them would break
`endpaper meeting list` / `note list`, whose contract is that they list everything.

`create_document`, `create_meeting`, `create_note`, `open_daily_note`, `load_for_edit`, `save`,
`load_tasks`, `add_task`, `set_task_state`, `match_document`, `match_task`, `filter_documents`:
untouched.

---

## Backwards-compatibility statement

| Change | Kind | Breaking? |
|---|---|---|
| `YearMonth`, `MonthListing` | New types | No |
| `list_months`, `scan_month`, `scan_unfiled` + wrappers | New functions | No |
| `TaskFilter.only_done` | New field, defaulted | No |
| `filter_tasks` honouring `only_done` | New branch | No |

Changelog entries required for `TaskFilter.only_done` and the new public functions (Principle VI).
