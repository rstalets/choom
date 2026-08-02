# Phase 1 Data Model: A Picker for Ambiguous `/link`

**Feature**: `015-link-picker` | **Date**: 2026-08-01 | **Plan**: [plan.md](./plan.md)

Nothing here is persisted. Both entities exist only for the duration of one `/link` invocation; the
workspace's files are the only state choom has (Principle III).

---

## `LinkCandidate` (new, `core/models.py`)

One record the search matched, carrying everything a row needs to be chosen from.

| Field | Type | Notes |
|-------|------|-------|
| `target` | `LinkTarget` | The record itself — id, path, title, kind, line. Unchanged and reused, so insertion goes through the same formatting the single-match path uses. |
| `collection` | `str` | Display name of the collection: `meeting`, `note`, or `task`. Derived from `target.kind`; carried explicitly so the renderer never re-derives it. |
| `date` | `str \| None` | ISO `YYYY-MM-DD`. `None` when the record has no recorded date (a hand-typed task). |

```python
@dataclass(frozen=True, slots=True)
class LinkCandidate:
    target: LinkTarget
    collection: str
    date: str | None
```

**Derivation**

| Source | `collection` | `date` |
|--------|--------------|--------|
| Meeting (`Document`) | `"meeting"` | `document.created` verbatim (already ISO) |
| Note (`Document`) | `"note"` | `document.created` verbatim |
| Task (`Task`) | `"task"` | `task.created.isoformat()`, or `None` when `task.created is None` |

**Validation rules**

- `title` for display is `target.title`; for a task that is the task's text. Never empty in practice,
  but a blank title renders as a blank cell rather than raising (Principle IV).
- `date` is never parsed for ordering — ISO strings sort lexicographically in date order.
- A malformed hand-edited `created:` value is carried through as the string it is rather than raising.
  It sorts where it sorts and displays as written; it never removes the record from the list.

**Ordering (the one invariant worth stating)**

Newest first; ties by title, case-insensitive; undated records after every dated record. Implemented as
the two stable passes `core/documents.py` already uses:

1. sort by title, ascending
2. sort by `(has date, date)`, descending — stable, so step 1 survives as the tie-break

**Relationships**

- Wraps `LinkTarget`, which is unchanged by this feature. No field is added to it and none of its 13
  construction sites is touched.
- Produced only by `link_candidates()`. `find_link_targets()` becomes a projection —
  `tuple(c.target for c in link_candidates(...))` — so both callers see the same matches in the same
  order.

---

## Selection list (transient, `tui/link_picker.py`)

The pending choice. Not a dataclass — it is the `LinkPicker` widget's own state.

| State | Type | Notes |
|-------|------|-------|
| `candidates` | `tuple[LinkCandidate, ...]` | Fixed when the picker opens. Never re-queried while open, so a workspace change mid-decision cannot move rows under the highlight (research R9). |
| highlighted index | `int` | `ListView.index`. Starts at 0 — the newest record. Wraps at both ends. |
| open / closed | `bool` | `display` on the widget. Closed is the resting state; the widget stays mounted and hidden. |

**State transitions**

| From | Event | To | Effect |
|------|-------|----|--------|
| closed | `/link` matches ≥ 2 and the screen is tall enough | open | candidates set, index 0, `ListView` focused, footer swaps to `LINK_PICKER_HELP` |
| closed | `/link` matches ≥ 2, screen too short | closed | falls back to `link_ambiguous_status()`; no list |
| closed | `/link` matches exactly 1 | closed | link inserted directly (unchanged path) |
| closed | `/link` matches 0 | closed | `link_no_match_status()` (unchanged path) |
| open | `↑` / `↓` | open | index moves, wrapping |
| open | `enter`, record still resolves | closed | line replaced with the link; focus and footer restored |
| open | `enter`, record no longer resolves | closed | reported; line left as typed |
| open | `esc` | closed | line left byte-identical; focus and footer restored |
| open | resize, still tall enough | open | rows rebuilt at the new width; candidates and index kept |
| open | resize, now too short | closed | fallback message; line left as typed |

In every transition out of `open`, focus returns to `#editor` and the footer returns to `EDIT_HELP` —
the editor is where the user was, and it is where they end up.
