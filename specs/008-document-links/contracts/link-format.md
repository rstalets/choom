# Contract: the on-disk link format

**Feature**: `008-document-links`

This is the contract with the *file*, not with a caller. It is what a person hand-editing a note,
an assistant writing markdown, and a plain markdown viewer can all rely on. Everything else in this
feature is downstream of it.

Two rules govern the whole format:

1. **The `#id` fragment is the identity.** It is what endpaper resolves against, it is context-free,
   and it never changes.
2. **The path is the route.** It is derived, perishable, computed by endpaper, and repaired when it
   goes stale. It exists so the link is clickable in a plain viewer and openable by an assistant that
   only reads files.

---

## Grammar

A link is an ordinary CommonMark **inline link**:

```
[ text ]( destination )

destination := path? fragment?      -- at least one must be present
fragment    := "#" id
```

Recognised:

```markdown
[Q3 planning](../../../meetings/2026/07/2026-07-28-q3-planning.md#meeting_20260728_a1b2c3d4)
[Q3 planning](#meeting_20260728_a1b2c3d4)
[Q3 planning](../../../meetings/2026/07/2026-07-28-q3-planning.md)
[Q3 planning](<../../../notes/2026/07/Q3 (draft).md#note_20260728_a1b2c3d4>)
```

**Not** recognised as a record link — these are ordinary content and endpaper never touches them:

| Form | Why |
|---|---|
| `![alt](pic.png)` | An image, not a reference to a record |
| `[text](https://…)`, `[text](mailto:…)` | Has a URL scheme; external |
| `[text][ref]` | Reference-style. endpaper never writes one; deliberately out of scope (R1) |
| `` `[text](#id)` `` | Inside an inline code span |
| A link inside a ``` or `~~~` fence | Inside a fenced code block |
| `[text]()` | Empty destination; not a link |

The last three matter more than they look. A note explaining link syntax contains example links, and
rewriting them would be exactly the "never lose the user's words" failure Principle IV exists to
prevent.

---

## Escaping

Write the destination bare. Wrap it in angle brackets when it contains a space, `(`, `)`, `<`, or
`>`:

```markdown
[a](notes/2026/07/plain.md#note_1)
[a](<notes/2026/07/Q3 (draft).md#note_1>)
```

Percent-encoding is never emitted. The raw file is what an assistant reads, and `%20` makes it worse
(R4).

Generated paths never need this — endpaper slugifies filenames to `[a-z0-9-]`. It exists for files a
user placed by hand, which the workspace explicitly permits.

---

## Path derivation

The path is always computed, never authored (FR-007). It is the relative path from the **directory
containing the source file** to the **target file**, with forward slashes on every platform.

| Source | Target | Destination written |
|---|---|---|
| `meetings/2026/07/a.md` | `notes/2026/07/b.md` | `../../../notes/2026/07/b.md` |
| `notes/daily/2026/07/d.md` | `meetings/2026/07/a.md` | `../../../../meetings/2026/07/a.md` |
| `tasks.md` | `meetings/2026/07/a.md` | `meetings/2026/07/a.md` |
| `meetings/2026/07/a.md` | `tasks.md` | `../../../tasks.md` |
| `notes/stray.md` | `notes/daily/2026/07/d.md` | `daily/2026/07/d.md` |
| `meetings/2026/07/a.md` | `meetings/2026/07/b.md` | `b.md` |

The prefix ranges from nothing to `../../../../`. **Depth is not a constant** — which is why nobody
should be asked to write one by hand, and why a fragment-only link is valid input.

Forward slashes are mandatory, not cosmetic: a Windows-authored link containing `\` is not a valid
relative URL and will not resolve for a colleague on macOS sharing the same folder.

---

## Resolution

Always id first, path second (FR-006):

1. If the destination has a `#id`, resolve that id against the workspace. If it names a record, that
   is the target — **regardless of what the path says**.
2. Otherwise, resolve the path relative to the source file's directory. If it names a file in the
   workspace, that is the target.
3. Otherwise the link is **dead**.

| Id | Path | Outcome |
|---|---|---|
| resolves | correct | `resolved` |
| resolves | wrong, or absent | `stale` — repaired on next write |
| absent | resolves | `stale` — gains the target's `#id` on next write |
| does not resolve | anything | `dead` — never rewritten, never removed |

**Duplicate ids** (two files carrying the same id, e.g. a copied file) resolve deterministically to
the first in workspace path-sort order, with a `link_ambiguous` warning naming every path. Resolution
never raises — one duplicated id elsewhere must not make an unrelated file unreadable (R11).

An id is compared **whole**. Nothing splits it on `_` or reads it by offset, which is what lets
`m_20260728_a1b2c3d4` (an id written before the prefix change) and `meeting_20260728_a1b2c3d4`
coexist with no compatibility branch (FR-013, FR-014).

---

## Repair

Repair is a **byte-level splice**, not a re-render. Only the destination between `(` and `)` is
replaced; the link text, the surrounding sentence, and the file's line endings are untouched
(FR-026). Markdown is never round-tripped through a parser.

Two triggers, with different rules:

| Trigger | Scope | Writes when nothing is stale? |
|---|---|---|
| Saving a file (`save_buffer`) | That one file only (FR-024) | The file is written because the user saved; `updated` moves as it always has |
| `endpaper links heal` | Whole workspace, or named paths | **No.** A file with nothing stale is not opened for writing and its `updated` does not move |

That distinction is load-bearing. A repair pass that rewrote every file would make a colleague's sync
client show a wave of modifications nobody made — which is why repair-on-scan was rejected outright.

A dead link is skipped by both. It is never rewritten, never removed, and never fatal; it produces a
warning naming the source file and line (FR-025).

---

## The task line

```
- [ ] call Terry about the renewal <!-- id:task_a1b2 type:followup links:meeting_20260728_a1b2c3d4 created:2026-07-30 -->
```

- `links` holds comma-separated **ids only, never paths** (FR-018). A task line is one line of
  metadata, and the prefix already says which collection to look in.
- Field order is `id`, `type`, `tags`, `links`, `created`. Empty fields are omitted, so a task with
  no links renders byte-identically to today (FR-016, FR-017).
- A malformed value warns and skips that one line; every other task in the file still parses
  (FR-020).
- An id that names nothing is preserved verbatim and reported dead — never silently dropped
  (FR-019).

`tasks.md` stays valid CommonMark and renders as a checklist in any viewer; the metadata is in an
HTML comment, which every renderer hides.

---

## Ids

| Collection | Prefix | Example |
|---|---|---|
| `meetings/` | `meeting_` | `meeting_20260728_a1b2c3d4` |
| `notes/`, `notes/daily/` | `note_` | `note_20260728_a1b2c3d4` |
| `tasks.md` | `task_` | `task_a1b2` |

The prefix is the collection's own name, so a new collection needs no registry of abbreviations and
no arbitration when two collections share a first letter — `meeting_` and `memo_` need no decision
(FR-012).

Ids written before this change keep working untouched (FR-013). Nothing is migrated and no file is
rewritten to adopt the new scheme.
