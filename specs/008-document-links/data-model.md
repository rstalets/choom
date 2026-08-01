# Data Model: Document Links

**Feature**: `008-document-links` | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

Everything here is in-memory. This feature introduces **no new persisted structure** — no index file,
no cache, no new frontmatter key, and no back-reference written into any target (FR-021, FR-028). The
only bytes that change on disk are link destinations inside document bodies and one new optional
field in the `tasks.md` metadata comment.

All types follow the house style in `core/models.py`: `@dataclass(frozen=True, slots=True)`.

---

## On-disk representation

There are exactly two places a link exists on disk.

### 1. In a document body — a CommonMark inline link

```markdown
See [Q3 planning](../../../meetings/2026/07/2026-07-28-q3-planning.md#meeting_20260728_a1b2c3d4).
```

| Part | Role | Authored by |
|---|---|---|
| `[Q3 planning]` | Link text | The user. Never modified by endpaper. |
| `../../../meetings/...md` | Path — the route | **endpaper.** Derived, perishable, repaired when stale. |
| `#meeting_20260728_a1b2c3d4` | Fragment — the identity | Either. Authoritative and permanent. |

Both parts are optional on input, and that is the point:

| Written by hand | Valid? | What happens on next save |
|---|---|---|
| `[label](#meeting_20260728_a1b2c3d4)` | Yes — resolves by id | Gains the correct relative path |
| `[label](../meetings/2026/07/a.md)` | Yes — resolves by path | Gains the target's `#id` fragment |
| `[label](wrong/path.md#meeting_2026…)` | Yes — resolves by id | Path corrected |
| `[label](#meeting_deleted)` | Resolves to nothing — **dead** | Left byte-identical, warning emitted |

### 2. On a task line — the `links` field

```
- [ ] call Terry about the renewal <!-- id:task_a1b2 type:followup links:meeting_20260728_a1b2c3d4 created:2026-07-30 -->
```

Ids only, comma-separated, no paths (FR-018) — a task line is already one line of metadata, and the
prefix says which collection to look in. Field order is `id`, `type`, `tags`, `links`, `created`;
empty fields are omitted (FR-017), so a task with no links renders exactly as it does today.

---

## Entities

### `Link`

One directed reference, as found in a source file. Carries the source offsets so a repair can splice
a new destination into the original text and change nothing else (FR-026).

| Field | Type | Notes |
|---|---|---|
| `source` | `Path` | File the link was found in |
| `line` | `int` | 1-indexed, for reporting |
| `text` | `str` | Link text, verbatim; never modified |
| `path` | `str \| None` | Destination path as written; `None` for a fragment-only link |
| `target_id` | `str \| None` | Fragment without the `#`; `None` for a path-only link |
| `start` | `int` | Character offset of `[` in the source text |
| `end` | `int` | Character offset just past `)` |
| `in_tasks_field` | `bool` | True when it came from a task line's `links:` field rather than a body link |

A link from a `links:` field has `path=None`, `start`/`end` spanning the id token, and
`in_tasks_field=True`. It is never path-repaired, because it never carries a path.

**Invariant**: at least one of `path` and `target_id` is not `None`. A `[text]()` with an empty
destination is not a link and is not collected.

### `LinkStatus`

```python
LinkStatus = Literal["resolved", "stale", "dead"]
```

| Value | Meaning | Repairable |
|---|---|---|
| `resolved` | Id resolves and the path already points at that file | Nothing to do |
| `stale` | Id resolves, but the path is wrong, absent, or the fragment is absent | **Yes** — mechanical |
| `dead` | Id resolves to nothing (or, for a path-only link, the path resolves to nothing) | **No** — needs a decision |

The `stale`/`dead` split is the whole point of `links check`: one is mechanically fixable and the
other needs a human to choose between relinking, removing, and recreating the target (FR-033).

### `LinkDirection`

```python
LinkDirection = Literal["out", "in", "both"]
```

`both` is the default for `endpaper links <id>` (FR-032).

### `LinkReport`

What `check` and `heal` emit for one link. Field names are the fixed JSON keys from FR-039 — see
[contracts/cli.md](contracts/cli.md).

| Field | Type | Notes |
|---|---|---|
| `file` | `Path` | Source file, workspace-relative when serialised |
| `line` | `int` | 1-indexed |
| `text` | `str` | Link text |
| `target_id` | `str \| None` | The id, resolvable or not |
| `old_path` | `str \| None` | Path as written; `None` when the link had no path |
| `new_path` | `str \| None` | Correct path; `None` for a dead link, which never gets one |
| `status` | `LinkStatus` | |

### `LinkTarget`

The resolved other end. A link can point at a document or at a task, and the two live in different
places, so resolution returns a small union rather than a `Document`.

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | The record's id |
| `path` | `Path` | The file that holds it — a document's own file, or `tasks.md` for a task |
| `title` | `str` | Document title, or task text |
| `kind` | `Literal["meeting", "note", "task"]` | Derived from the id prefix |
| `line` | `int \| None` | Line within `tasks.md` for a task; `None` for a document |

`kind` being derivable from the prefix is the payoff from the id change (R6): the resolver knows
where to look before it opens anything, and a new collection needs no registry.

---

## Changes to existing types

### `Task` — gains `links`

```python
@dataclass(frozen=True, slots=True)
class Task:
    id: str | None
    text: str
    done: bool
    type: str
    tags: tuple[str, ...]
    links: tuple[str, ...]   # NEW — target ids, in the order written
    created: date | None
    line: int
```

Bare ids, not `Link` objects: the field holds what the line holds. Defaults to `()`, so every
existing construction site and every existing `tasks.md` is unaffected (FR-016).

### `SaveResult` — gains `warnings`

```python
@dataclass(frozen=True, slots=True)
class SaveResult:
    ok: bool
    saved_text: str
    stamped: bool
    message: str
    warnings: tuple[ScanWarning, ...] = ()   # NEW — dead links found while healing
```

Defaulted, so the four existing test call sites and the single production caller keep compiling
(R5). A dead link never makes `ok` False — it is reported, not fatal (FR-025).

### `ScanWarningReason` — gains two members

```python
"link_dead",          # a link whose id resolves to nothing
"link_ambiguous",     # two records carry the same id
```

Reusing `ScanWarning` rather than inventing a second reporting channel is the spec's stated
assumption, and it means dead links surface through the paths that already print warnings in both
adapters.

### `Collection` — no shape change, new values

`id_prefix` goes from `"m_"` / `"n_"` to `"meeting_"` / `"note_"`. The field already exists; only the
literals move (R6).

---

## Relationships

```mermaid
graph LR
  Task -- "links: ids" --> LinkTarget
  Document -- "body markdown link" --> LinkTarget
  LinkTarget -.-> Document
  LinkTarget -.-> Task
```

- A link is **directed**. Nothing records the reverse; inbound links are computed by scanning
  (FR-027).
- A link is **many-to-many and unconstrained**: any record may point at any number of records,
  including itself, and the same target twice from one file (Edge Cases).
- A link may point at **nothing**. That is a valid, non-fatal state called `dead`, not an error.
- There is **no referential integrity**, by design. Deleting a document is allowed and leaves dead
  links behind, which `links check` reports and a human resolves.

---

## Validation rules

| Rule | Source | Where enforced |
|---|---|---|
| Fragment is authoritative; id resolves before path | FR-002, FR-006 | `core/links.py` resolver |
| At least one of path / fragment must be present | Model invariant | Scanner drops empty destinations |
| Text in fenced blocks and code spans is not a link | FR-009 | Scanner mask (R1) |
| Images and URL-scheme destinations are not record links | FR-010 | Scanner: `!` lookbehind, scheme test |
| An id is matched whole; never split or offset-parsed | FR-014 | Resolver compares full strings |
| `links:` values match `^[A-Za-z0-9_-]+$` | FR-015, R7 | `_classify_body`, reusing `_IDVAL` |
| An empty `links:` value is malformed | R7, mirrors `tags` | `_classify_body` |
| A malformed value skips one line, never the file | FR-020, Principle IV | Existing warn-and-continue path |
| An unresolvable id is preserved verbatim | FR-019 | Never rewritten, never dropped |
| Destinations use `/` on every platform | R3 | Path derivation replaces `os.sep` |
| Destinations with spaces or parens use `<...>` | R4 | Path renderer |
| Duplicate ids resolve deterministically, with a warning | R11 | Resolver sorts by path, warns |

---

## State transitions

A link's status is not stored — it is recomputed every time anyone asks. These are the transitions a
link moves through as the workspace changes around it:

```
                    target exists, path correct
   [ authored ] ──────────────────────────────────▶ resolved
        │                                            │   ▲
        │ authored without a path,                   │   │
        │ or target moved                            │   │ save, or `links heal`
        ▼                                            ▼   │
      stale ─────────────────────────────────────────────┘
        │
        │ target deleted
        ▼
       dead ──── never rewritten, never removed, never fatal ────▶ (reported; a human decides)
```

- `stale → resolved` happens on save of the containing file (FR-022) or on `links heal` (FR-035).
- `dead` is terminal for tooling. `links heal` skips it, `save_buffer` skips it, and both report it.
- `dead → resolved` is possible but only by human action — recreating the target, or editing the
  link to name a different one.
- A dead link in a file **never blocks** repair of a stale link beside it (US2 AC6, US4 AC5).
