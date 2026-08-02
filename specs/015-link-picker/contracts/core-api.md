# Contract: Core API

**Feature**: `015-link-picker` | **Module**: `choom.core.links`, `choom.core.models`

One function is added and one is re-expressed. No existing signature changes, and no existing return
type changes.

---

## `link_candidates(workspace, query) -> tuple[LinkCandidate, ...]`

```python
def link_candidates(workspace: Workspace, query: str) -> tuple[LinkCandidate, ...]:
    """Records whose title, id, type, or tags match `query`, ready to be chosen from.

    The same matching rule as the list filter (`match_document` / `match_task`) and
    the same records `find_link_targets` reports -- this is that search plus the
    ordering and the per-row facts a picker needs. Newest first, ties by title,
    undated records last.

    Caller decides what to do with zero, one, or several results; this reports,
    it does not choose.

    Never raises.
    """
```

**Guarantees**

| # | Guarantee |
|---|-----------|
| C1 | Returns every record `find_link_targets` would return, and no others. The two share one scan. |
| C2 | Ordered newest first by `date`; ties broken by `title`, case-insensitive, ascending. |
| C3 | Candidates with `date is None` sort after every candidate with a date, keeping the title tie-break among themselves. |
| C4 | `collection` is exactly one of `"meeting"`, `"note"`, `"task"`, matching `target.kind`. |
| C5 | Never raises. A malformed record is skipped by the underlying scan, exactly as today; a malformed `created:` value is carried through as a string rather than raising (Principle IV). |
| C6 | Callable without a terminal, a TTY, or an event loop (Principle I). |
| C7 | Deterministic: the same workspace and query produce the same tuple in the same order. |
| C8 | `date` is a bare `YYYY-MM-DD` string or `None` — never a full timestamp. `Document.created` holds a timestamp and is sliced to its date half, matching every other surface that shows it. |

**Parameters**

- `workspace` — the workspace to search. Scanned live; nothing is cached between calls.
- `query` — the writer's search terms. Every term must appear, order irrelevant, case-insensitive.
  An empty query is the caller's problem to reject; `/link` already does.

---

## `find_link_targets(workspace, query) -> tuple[LinkTarget, ...]`

**Unchanged signature, re-expressed body**:

```python
return tuple(candidate.target for candidate in link_candidates(workspace, query))
```

**What changes for existing callers**: the returned order. Previously the tuple was in scan order
(meetings, then notes, then tasks); it is now newest-first. The only caller is `/link`'s single-match
path, which reads `matches[0]` only when `len(matches) == 1`, so no behaviour depends on the old order.
Membership — which records match — is byte-for-byte unchanged.

---

## `LinkCandidate` (`choom.core.models`)

```python
@dataclass(frozen=True, slots=True)
class LinkCandidate:
    """One record a `/link` search matched, with the facts a picker row needs.

    Wraps `LinkTarget` rather than extending it: a link's resolved destination and
    a row in a chooser are different jobs, and `LinkTarget` is built in a dozen
    places that have nothing to do with choosing.
    """

    target: LinkTarget
    collection: str
    date: str | None
```

Frozen and slotted, like every other model in this codebase.

---

## Exports

Both names are added to `choom.core.__init__`'s imports and `__all__`, following the existing entries
for `find_link_targets` and `LinkTarget`. Adding a name is a minor change; nothing is renamed or
removed.

---

## Out of contract

- No CLI command, `--json` schema, or exit code changes. The picker is inherently interactive, and
  Principle II forbids the CLI to block on a prompt (see the plan's gate II).
- No change to what counts as a match (FR-016). `match_document` and `match_task` are untouched.
- No change to `format_link`, `relative_destination`, or `resolve_id` — the picker calls them as they
  are.
