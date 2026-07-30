# Phase 1 Data Model: UI Layout Refresh

**Feature**: `005-ui-layout-refresh` | **Date**: 2026-07-30

This feature adds no persisted data. Nothing here changes a file on disk, a frontmatter field, or
the task line format. One new value object and one new field on an existing filter are the whole
persistent-shape delta; everything else is session state held by the TUI.

---

## New core types

### `YearMonth`

A calendar month, used to name a left-pane entry and to scope a read.

```python
@dataclass(frozen=True, slots=True)
class YearMonth:
    year: int
    month: int
```

| Field | Type | Rules |
|---|---|---|
| `year` | `int` | Four digits, `1000`–`9999`. Discovered from a directory name matching `[0-9]{4}`. |
| `month` | `int` | `1`–`12`. Discovered from a directory name matching `0[1-9]` or `1[0-2]`. |

**Behaviour**:

- Ordering is natural: `(year, month)`. The left pane renders most-recent-first, so callers sort
  descending.
- Renders as `YYYY-MM` (for example `2026-07`), matching the directory layout and the issue's mockup.
- Directory names that do not match the patterns above are ignored, not errors — a user folder called
  `notes/archive/` must not break month discovery (Principle IV).

**Why a type rather than a `(int, int)` tuple**: it is the key of the session cache and the identity
of a left-pane row; a named type keeps `scan_month(ws, NOTES, ym)` from being called with the
arguments swapped, which a tuple invites.

### `MonthListing`

What `list_months` returns: the months that exist, plus whether stray documents exist outside them.

```python
@dataclass(frozen=True, slots=True)
class MonthListing:
    months: tuple[YearMonth, ...]      # most-recent-first
    has_unfiled: bool                  # stray *.md outside any YYYY/MM folder
```

**Rules**:

- `months` always contains the current month, even when its folder does not exist on disk (FR-014),
  so the collection can be opened and written into on a fresh workspace.
- `months` is deduplicated across scan subtrees — `notes/2026/07` and `notes/daily/2026/07` are one
  entry, because they are one month to the user.
- `has_unfiled` is `True` when at least one `*.md` sits under a scan dir but outside any `YYYY/MM`
  folder (research R6). Discovering it opens no files.

---

## Changed core types

### `TaskFilter` — one new field

```python
@dataclass(frozen=True, slots=True)
class TaskFilter:
    type: str | None = None
    tags: tuple[str, ...] = ()
    include_done: bool = False
    only_done: bool = False      # NEW
```

**Selection matrix** (the only behaviour change in `filter_tasks`):

| `only_done` | `include_done` | Result |
|---|---|---|
| `False` | `False` | Open tasks only — today's default, unchanged |
| `False` | `True` | All tasks — unchanged |
| `True` | any | Completed tasks only — **new**; `only_done` wins |

Added as a field with a `False` default rather than replacing `include_done` with a tri-state, so
every existing caller, CLI invocation, and test keeps its meaning (research R8). Public API change →
changelog.

---

## Unchanged core types

`Workspace`, `Document`, `Collection`, `DailyNote`, `ScanWarning`, `ScanWarningReason`,
`DocumentFilter`, `EditableFile`, `SaveResult`, `InitResult`, `Task`, `ParsedTasks` are all
untouched. In particular:

- `Document` gains no month field. The month is derivable from the path and from `created`; storing
  it would be a third copy that can disagree with the other two.
- `Collection` gains no month configuration. `create_dir` and `scan_dirs` already imply the layout,
  and month discovery globs beneath them.

---

## Session state (TUI only — never persisted)

Held on `EndpaperApp`. All of it dies with the process; none of it is written to the workspace,
which is what keeps it outside Principle III (see plan.md Complexity Tracking).

| State | Shape | Purpose | Reset when |
|---|---|---|---|
| `active` | `str` — `"tasks" \| "notes" \| "meetings"` | Which collection the top bar highlights | Never; starts at `"tasks"` |
| `month_scope` | `dict[str, YearMonth]` per collection | Which month the left pane highlights | Set to the current month each time a collection is selected (FR-010, US2 scenario 5) |
| `task_category` | `str` — `"todo" \| "done"` | Which category the left pane highlights | Set to `"todo"` each time Tasks is selected (FR-018) |
| `month_cache` | `dict[(str, YearMonth), list[Document]]` | Months already read (FR-035) | Never during a session; evicted only by process exit |
| `month_warnings` | `dict[(str, YearMonth), list[ScanWarning]]` | Per-month warning counts (FR-016) | With the cache |
| `unfiled_cache` | `dict[str, list[Document]]` | Stray documents, read on first Unfiled selection | With the cache |
| `fully_loaded` | `set[str]` | Collections whose every month is cached, so a filter need not re-read | Never during a session |
| `filter_query` | `str` | Active filter term | Cleared on escape and on `/filter` with no term |
| `pre_filter_scope` | `YearMonth \| None` | The month to restore when a filter is cleared (FR-034) | Captured when a filter becomes active |

**Cache coherence**: a month already in the cache is not re-read, so a document added to that month
by another process while the tool is open will not appear until restart. This is the same staleness
the tool has today (a single scan at mount), with the same targeted escape hatch: `refresh_document`
re-parses the one file the user just edited. No new invalidation logic is introduced, deliberately.

**`refresh_document` must be re-pointed at the cache.** `EditScreen._save` calls
`app.refresh_document(path)` after every save, and today that walks `self.documents[collection]` and
`self.visible_documents`. Those are exactly the structures the month cache replaces, so the method
has to update `month_cache[(collection, month)]` — keyed by the month derived from the saved
document's path — plus `unfiled_cache` when the document is unfiled. Getting this wrong is silent:
the file on disk is correct and only the row is stale, which is precisely what FR-024 ("its row
reflecting any change made") exists to catch. Two edges depend on it — save-and-exit from the list
and from preview — and both are covered in `test_edit_from_list_tui.py`.

A saved document whose `created` date moved to a different month (a hand-edited frontmatter date)
leaves its cached month and joins another. `refresh_document` removes it from the month keyed by its
old path and, because the file itself has not moved on disk, re-files it under the month its path
still implies — the path is the authority for scoping, not the frontmatter (see R5).

---

## State transitions

```text
                 tab / shift+tab
   ┌──────────────────────────────────────────┐
   │                                          │
   ▼                                          │
Collection selected ──► month_scope := current month   (notes, meetings)
   │                    task_category := "todo"        (tasks)
   │                    focus := middle pane, row 0
   │
   ├─ left pane moves ──► month_scope := chosen month ──► middle pane refills
   │                                                       (cache hit, or read + cache)
   │
   ├─ /filter <term> ───► pre_filter_scope := month_scope
   │                      load all months (worker, once) ──► fully_loaded += collection
   │                      middle pane := matches across all months
   │                      left pane := scope suspended
   │
   ├─ filter cleared ───► month_scope := pre_filter_scope ──► middle pane refills
   │
   └─ document created ──► month_scope := created document's month
                           cache[(collection, that month)] += document
                           push EditScreen
```

---

## Validation rules carried from the spec

| Rule | Source | Where enforced |
|---|---|---|
| Month list is most-recent-first and always includes the current month | FR-014 | `list_months` (core) |
| Only the displayed month is read when no filter is active | FR-012 | `scan_month` call sites (TUI), asserted by read-count tests |
| A filter reads each month at most once per session | FR-035 | `month_cache` / `fully_loaded` (TUI) |
| Warning counts reflect the displayed month only | FR-016 | `month_warnings` keyed by month |
| Malformed frontmatter yields a warning, never an exception | Principle IV | `_parse_document`, reused unchanged |
| Unrecognised directory names are ignored, not fatal | Principle IV | `list_months` pattern match |
| Completed-only selection is available to both front-ends | Principle II | `TaskFilter.only_done` + `task list --done` |
