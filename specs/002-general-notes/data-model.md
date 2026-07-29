# Data Model: General Notes

**Feature**: `002-general-notes` | **Plan**: [plan.md](./plan.md)

Feature 001's data model is the baseline. This document records what changes, what is added, and
what is deliberately identical. Where a rule is unchanged from meetings, it says so rather than
restating it — FR-011 makes "identical to meetings" the requirement, and a restatement is a place
for the two to drift apart.

---

## Entity map

```
Workspace
├── meetings/            Document, collection MEETINGS      (feature 001)
├── notes/               Document, collection NOTES         ← this feature
│   └── daily/           Document, type "daily", one per day
└── tasks.md                                                (feature 003)
```

`Document` is one record type for both kinds. They carry byte-identical frontmatter — the six fields
fixed by REQUIREMENTS.md §4.6 — so the distinction between a meeting and a note is *where the file
lives*, not what it contains. Nothing in the record says which kind it is.

---

## Changed: `Document` (was `Meeting`)

```python
@dataclass(frozen=True, slots=True)
class Document:
    id: str                    # "<prefix>_YYYYMMDD_" + 8 hex
    path: Path                 # absolute
    title: str                 # never empty
    type: str                  # "" when untyped; lowercase; "daily" only for daily notes
    tags: tuple[str, ...]      # order preserved, deduplicated, lowercase
    created: str               # "YYYY-MM-DDTHH:MM:SS", local naive
    updated: str               # same format

Meeting = Document            # alias, feature 001 compatibility
Note = Document               # alias, reads better at note call sites
```

Fields, types, and validation are unchanged. The only change is the name and the two aliases
([R2](./research.md#r2-naming-and-backward-compatibility-of-the-core-api)).

**`id` prefix by collection**: `m_` for meetings, `n_` for notes. The prefix makes an id
self-describing in a log line or a JSON dump, and guarantees no collision between the two
collections' in-memory lists. Uniqueness within a collection still comes from
`secrets.token_hex(4)`, with no lookup (feature 001's R-decision, unchanged).

---

## New: `Collection`

The four values that differ between the two document kinds, and nothing else.

```python
@dataclass(frozen=True, slots=True)
class Collection:
    id_prefix: str                    # "m_" | "n_"
    create_dir: str                   # relative to workspace root
    scan_dirs: tuple[str, ...]        # relative to workspace root, scanned in order
    reserved_types: frozenset[str]    # rejected by create_document with a usage error

MEETINGS = Collection("m_", "meetings", ("meetings",), frozenset())
NOTES     = Collection("n_", "notes",   ("notes", "notes/daily"), frozenset({"daily"}))
```

| Field | Why it varies |
|---|---|
| `id_prefix` | `m_` vs `n_`, per REQUIREMENTS.md §4.6's example format |
| `create_dir` | New documents always land in the collection's top directory; daily notes bypass this entirely and use their own writer |
| `scan_dirs` | Notes live in two places. `glob("*.md")` does not recurse, so listing `notes/` alone would miss the daily notes and listing recursively would sweep up any directory a user creates. Naming both explicitly satisfies FR-017 and FR-023 at once. |
| `reserved_types` | Only notes reserve a type. See [R8](./research.md#r8-the-reserved-daily-type). |

**Not a base class, not a registry.** It carries no behaviour and is never subclassed; the functions
take it as an argument. Adding a third kind later means adding a constant, not a class hierarchy.

---

## New: `DailyNote`

The result of `open_daily_note`. Distinct from `Document` because it must describe a file that
exists but may not parse.

```python
@dataclass(frozen=True, slots=True)
class DailyNote:
    path: Path                 # always present — the file exists when this returns
    document: Document | None  # None when an existing file's frontmatter does not parse
    created: bool              # True only when this call created the file
```

| Case | `path` | `document` | `created` |
|---|---|---|---|
| No file for today; we created it | the new file | the new record | `True` |
| File exists, frontmatter parses | the existing file | its record | `False` |
| File exists, frontmatter missing/broken | the existing file | `None` | `False` |

`document is None` is not an error and never raises. It means: the file is real, we know where it
is, and we know nothing else about it. Full reasoning in
[R4](./research.md#r4-what-open_daily_note-returns-when-the-existing-file-is-unparseable).

**Consumers**:

- CLI `note today` prints `path` in every case (FR-007) and never reads `document`.
- TUI previews the file at `path`, and inserts into the in-memory list only when
  `created and document is not None`.

---

## Changed: `Workspace`

```python
@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path

    @property
    def meetings_dir(self) -> Path: return self.root / "meetings"
    @property
    def notes_dir(self)    -> Path: return self.root / "notes"          # new
    @property
    def daily_dir(self)    -> Path: return self.root / "notes" / "daily" # new
```

`init_workspace` already creates `notes/daily/` (feature 001), so no workspace migration exists and
none is needed. A workspace created under 001 works with every command in this feature — SC-010
asserts exactly this.

---

## Changed: `DocumentFilter` (was `MeetingFilter`)

```python
@dataclass(frozen=True, slots=True)
class DocumentFilter:
    type: str | None = None    # exact, case-insensitive; "daily" selects daily notes
    tags: tuple[str, ...] = () # all must be present (conjunctive)
    since: date | None = None  # inclusive, compared against created[:10]

MeetingFilter = DocumentFilter  # alias
```

Semantics unchanged. `--type daily` needs no special case: daily notes carry `type: daily` in
frontmatter, so the existing exact match selects them (FR-019).

---

## File formats

### Typed note — `notes/YYYY-MM-DD-<type>-<slug>.md`

Identical in every respect to a meeting file except the directory and the id prefix.

```markdown
---
id: n_20260728_a1b2c3d4
type: "research"
title: "vendor landscape"
tags: ["procurement"]
created: 2026-07-28T09:14:00
updated: 2026-07-28T09:14:00
---

```

Untyped notes omit the type segment from the filename (`notes/2026-07-28-vendor-landscape.md`) and
carry `type: ""`. Slug rules, the 40-character truncation, the `untitled` fallback, and the `-2`/`-3`
collision suffixes are all unchanged from meetings (FR-011).

### Daily note — `notes/daily/YYYY-MM-DD.md`

```markdown
---
id: n_20260728_e5f6a7b8
type: "daily"
title: "2026-07-28"
tags: []
created: 2026-07-28T09:14:00
updated: 2026-07-28T09:14:00
---

```

| Field | Value | Why |
|---|---|---|
| `title` | the ISO date | The list needs something to show and filter on, and the frontmatter schema is fixed at six fields, so there is nowhere else to put it. |
| `type` | `"daily"` | FR-003, and what makes `--type daily` work with no special case. |
| `tags` | `[]` | The daily-note command takes no arguments, so there is nothing to tag with. |
| body | empty | No heading, no template. Anything else is content the user did not ask for (spec Assumptions). |

**The filename carries no slug and no type segment.** It is the one filename in the product derived
from a date alone, which is what makes it addressable — `open_daily_note` resolves it by
construction rather than by search (FR-005).

---

## Validation rules

Rules marked *unchanged* are enforced by code shared with meetings and are not re-implemented.

| Rule | Applies to | Behaviour on violation |
|---|---|---|
| Type matches `^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$` | note create | `UsageError`, exit 2 (*unchanged*) — this is what keeps a crafted type from escaping `notes/` (FR-013) |
| Type not in `reserved_types` | note create | `UsageError` naming `endpaper note today`, exit 2, **before any filesystem work** (FR-012) |
| Tags match the same pattern | note create | `UsageError`, exit 2 (*unchanged*) |
| Description non-empty after tag stripping | note create | `UsageError`, exit 2 (*unchanged*) |
| Frontmatter has exactly the six keys | note scan | Skipped with a `ScanWarning`; file never rewritten (*unchanged*, FR-021) |
| Target file does not already exist | note create | Suffix `-2`, `-3`, … via `O_EXCL` (*unchanged*, FR-011) |
| Daily note for today does not already exist | daily create | **Not a violation** — the existing file is returned, `created=False`, nothing written (FR-004) |

---

## Scan behaviour

`scan_documents(workspace, NOTES)` walks `notes/` then `notes/daily/`, each with a non-recursive
`glob("*.md")`.

This satisfies three requirements as a consequence of the glob rather than as special cases:

- **FR-023, non-markdown ignored** — `*.md` does not match them.
- **FR-023, other subdirectories ignored** — `glob` does not recurse, and only `daily` is listed.
- **FR-017, both kinds in one collection** — the two directories' results are concatenated before
  sorting, so daily and typed notes interleave by date.

Sort order is unchanged: `created` descending, ties broken by path ascending, so the order is total
and stable across runs.

**A file in `notes/daily/` whose name is not an ISO date** is listed normally if its frontmatter
parses. It is never returned by `open_daily_note`, which builds today's filename rather than
searching for it. The two operations disagreeing here is intended: listing describes what is on
disk, and the daily note is defined by its path.

---

## Identity and cross-collection separation

FR-018 requires notes and meetings to stay separate. Three independent mechanisms enforce it, and
none of them relies on a field inside the record:

1. **Directories do not overlap.** `meetings/` and `notes/` are siblings; neither scan can reach the
   other.
2. **Id prefixes differ.** An `m_` id in a note list would be visible immediately.
3. **The adapters never merge the lists.** The CLI has separate subcommands; the TUI holds a dict
   keyed by collection and renders one at a time
   ([R6](./research.md#r6-holding-two-collections-in-a-one-screen-tui)).

A file physically placed in `notes/` whose frontmatter says `type: daily` lists as a daily note and
is not reachable by `open_daily_note`. This is an accepted, documented edge case rather than a bug:
listing reports what is on disk, and endpaper itself cannot create such a file because `daily` is
reserved.
