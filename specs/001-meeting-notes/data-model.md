# Phase 1 Data Model: 001-meeting-notes

**Date**: 2026-07-28
**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

There is no database. Markdown files are the only persistent state (Principle III). The types below
are in-memory projections of files, plus the validation rules that govern how files are named and
written.

---

## Entity: Workspace

A directory containing the fixed endpaper layout.

| Field | Type | Source | Notes |
|---|---|---|---|
| `root` | `Path` | discovered | Absolute path to the directory holding `.endpaper/` |
| `meetings_dir` | `Path` | derived | `root / "meetings"` — the collection root; dated files live in `YYYY/MM/` beneath it |

**Created by** `endpaper init`, which writes:

```
.endpaper/config.toml     # marker + schema version
AGENTS.md                 # generated from a packaged template
meetings/                 # empty
notes/daily/              # empty, unused this feature
tasks.md                  # empty, unused this feature
```

`.endpaper/config.toml` content for this feature:

```toml
[workspace]
schema = 1
created = "2026-07-28T09:14:00"
```

**Discovery rule** (FR-010): walk from the current directory upward through its ancestors; the
first directory containing `.endpaper/config.toml` is the workspace. Stop at the filesystem root.

**Validation**:

| Rule | Violation → |
|---|---|
| `init` target must not already contain `.endpaper/` | `WorkspaceError`, exit 3, nothing written (FR-009) |
| Every read/create command must find a workspace | `WorkspaceError`, exit 3, message names how to create one (FR-011) |
| `schema` must be `1` | `WorkspaceError`, exit 3, message names the version found |

---

## Entity: Meeting

One markdown file in `meetings/`. The file is the record; the type below is what a scan produces.

```python
@dataclass(frozen=True, slots=True)
class Meeting:
    id: str            # m_YYYYMMDD_xxxxxxxx
    path: Path         # absolute
    title: str
    type: str          # "" when untyped
    tags: tuple[str, ...]
    created: str       # YYYY-MM-DDTHH:MM:SS, local naive
    updated: str       # same format
```

**Frozen and slotted** because scans produce thousands of these and nothing mutates one — an edit
re-reads the file (Principle III: no cache to invalidate).

### Field rules

| Field | Rule | Source |
|---|---|---|
| `id` | `m_` + `YYYYMMDD` + `_` + 8 lowercase hex, from `secrets.token_hex(4)`. Stable for the life of the file. | FR-019, R5 |
| `title` | Description with `#tag` tokens removed and internal whitespace collapsed to single spaces. Original casing and non-ASCII preserved. Must be non-empty after stripping. | FR-020 |
| `type` | Lowercase. Matches `^[a-z0-9][a-z0-9_-]{0,39}$`, or empty for untyped. | FR-014, edge cases |
| `tags` | Ordered, de-duplicated, lowercase. Each matches `^[a-z0-9][a-z0-9_-]{0,39}$`. | FR-023 |
| `created` | Local naive time at creation. Never changes after. | FR-018 |
| `updated` | Equals `created` at creation. This feature never changes it (no edit path). | FR-018 |

### Path derivation

```
meetings/YYYY/MM/YYYY-MM-DD[-<type>]-<slug>[-N].md
```

- Date is the local date at creation. ISO-first so lexical sort equals chronological sort.
- The `YYYY/MM/` partition repeats the file's own date and is created on demand
  (spec [Amendments](./spec.md#amendments)). It is derived, never stored — nothing reads a meeting's
  date from its path.
- Type segment is omitted entirely when untyped (FR-015).
- `N` starts at `2` and only appears on collision (FR-017), and only within one partition — a
  collision suffix never crosses a directory boundary.
- Reading walks `meetings/` recursively, so a file the user has moved to the wrong month, or left
  directly under `meetings/`, still lists (FR-015a).

**Slug algorithm** (FR-016):

1. NFKD-normalize, then casefold.
2. Replace every run of non-`[a-z0-9]` with a single `-`.
3. Strip leading and trailing `-`.
4. Truncate to 40 characters, then strip any trailing `-` created by the cut.
5. If the result is empty, use `untitled`.

| Input description | Slug |
|---|---|
| `Q3 planning` | `q3-planning` |
| `Q3   planning!!` | `q3-planning` |
| `Café résumé` | `cafe-resume` |
| `!!!` | `untitled` |
| `🎉🎉` | `untitled` |
| 60-char sentence | first 40 chars, no trailing `-` |

Because the slug alphabet is `[a-z0-9-]`, characters illegal in Windows filenames (`<>:"/\|?*`) can
never appear in a generated path. The title in frontmatter keeps them.

### Collision handling

Candidate names are tried in order — no suffix, `-2`, `-3`, … — each opened with
`O_CREAT | O_EXCL`. The first that succeeds wins. A `FileExistsError` advances to the next
candidate. Two processes racing on the same name cannot both succeed (R6). Suffixes continue past
`-9` without special-casing.

### File on disk

```markdown
---
id: m_20260728_a1b2c3d4
type: standup
title: "Q3 planning"
tags: ["platform"]
created: 2026-07-28T09:14:00
updated: 2026-07-28T09:14:00
---

```

Exactly six keys, always in this order (FR-018). `title` and every tag are always double-quoted so
that a title of `no` or `3.10` round-trips as a string rather than a boolean or a float. `type` is
quoted when non-empty, and written as `""` when untyped. Timestamps are unquoted, matching the
example in REQUIREMENTS.md §4.6. The body after the closing `---` is a single blank line; everything
below belongs to the user and endpaper never generates content there.

---

## Entity: MeetingListRecord (the wire projection)

The shape emitted by `endpaper meeting list --json` and consumed by the TUI list. Exactly seven
keys, no more (FR-029). This is a published contract — see
[contracts/cli.md](./contracts/cli.md#meeting-list---json).

```json
{
  "id": "m_20260728_a1b2c3d4",
  "path": "meetings/2026-07-28-standup-q3-planning.md",
  "title": "Q3 planning",
  "type": "standup",
  "tags": ["platform"],
  "created": "2026-07-28T09:14:00",
  "updated": "2026-07-28T09:14:00"
}
```

`path` is relative to the workspace root and uses forward slashes on every platform, so that JSON
output is identical across Windows and POSIX and can be compared in tests.

---

## Reading: the tolerant scan

`scan_meetings(workspace) -> tuple[list[Meeting], list[ScanWarning]]`

For each `*.md` in `meetings/`, in one pass:

1. Read the file as UTF-8 with `errors="replace"`.
2. If it does not begin with `---\n`, warn `no_frontmatter`, skip.
3. Take lines up to the next `---`. If absent, warn `unterminated_frontmatter`, skip.
4. `yaml.safe_load` that block. On `yaml.YAMLError`, warn `malformed_yaml`, skip.
5. If the result is not a mapping, warn `not_a_mapping`, skip.
6. If its key set is not exactly the six required keys, warn `unexpected_fields` or
   `missing_fields`, skip.
7. Coerce every scalar to `str` — this is what undoes YAML 1.1 turning `no` into `False` and
   `created` into a `datetime` (R2).
8. Validate `type` and each tag against their patterns. On failure, warn `invalid_value`, skip.

**Invariants that hold no matter which branch fires** (Principle IV, FR-033):

- A skipped file is never rewritten, repaired, moved, or deleted.
- A skipped file never aborts the scan; every other meeting still lists.
- The scan never raises. `ScanWarning` is data, returned to the caller.
- Non-`.md` files in `meetings/` are ignored silently, not warned about.

`ScanWarning` carries `path`, a machine-readable `reason` from the set above, and a human sentence.
The CLI prints warnings to stderr (never stdout, FR-040); the TUI surfaces a count in the footer.

---

## Sorting and filtering

**Sort** (FR-027): `created` descending, ties broken by `path` ascending so ordering is total and
tests are deterministic.

**CLI filters** (FR-028), applied conjunctively:

| Filter | Semantics |
|---|---|
| `--type T` | exact, case-insensitive match on `type` |
| `--tag T` | `T` is in `tags`, exact, case-insensitive. Repeatable; repeats are ANDed. |
| `--since D` | `created` date ≥ `D`. `D` is `YYYY-MM-DD`. Inclusive. Invalid date → exit 2. |

**TUI live filter** (FR-030) is a different thing and deliberately looser: a case-insensitive
substring test against `title`, `type`, and each tag joined by spaces. It runs against the
in-memory list with no disk access (FR-031).

---

## State transitions

This feature creates and reads. It never mutates an existing meeting.

```
(none) --create--> Created --scan--> listed
```

`updated` exists in the schema so the edit feature (§3.5) has somewhere to write, but no code path
in this feature changes it after creation. That is asserted by a test, so the edit feature has to
change the assertion deliberately rather than by accident.
