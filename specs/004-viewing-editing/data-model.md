# Phase 1 Data Model: Viewing and Editing

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature introduces **no persistent data**. It adds no frontmatter field, no file, and no state
that outlives a keystroke — except the `CLAUDE.md` that `init` drops once. Everything below is either
an in-memory value that exists while a document is open, or a rule about how bytes move between the
buffer and the file.

`Document` is unchanged. This feature never constructs one and never writes one.

---

## Entities

### `EditableFile` (new, `core/models.py`)

What `load_for_edit` returns. Holds the buffer text plus exactly what is needed to put the file back
the way it was found.

```python
@dataclass(frozen=True, slots=True)
class EditableFile:
    path: Path
    text: str                  # normalised to "\n" — what the widget is given
    newline: str               # "\r\n" or "\n" — the convention to restore on write
    trailing_newline: bool     # whether the file ended with a line ending
```

| Field | Rule |
|---|---|
| `path` | The path the scan produced. Never derived, never rewritten to match a partition (FR-023). |
| `text` | The whole file including frontmatter (FR-009). Read with `errors="replace"`, matching the existing scan. |
| `newline` | The **first** line ending in the raw bytes. A file with none at all gets `"\n"`. |
| `trailing_newline` | True when the raw text ends with the line ending. Restored verbatim (FR-019). |

**Known deviation**: a file with *mixed* line endings is normalised to `newline` on save. Recorded
here rather than hidden; see [research.md R2](./research.md#r2-line-endings-and-the-trailing-newline).

---

### `SaveResult` (new, `core/models.py`)

What `save_buffer` returns. A save has three distinguishable outcomes and the screen renders each
differently, so this is a value rather than an exception.

```python
@dataclass(frozen=True, slots=True)
class SaveResult:
    ok: bool
    saved_text: str            # "\n"-normalised text now on disk; "" when ok is False
    stamped: bool              # False when the updated: line could not be found
    message: str               # "" when ok and stamped; otherwise user-facing
```

| Outcome | `ok` | `stamped` | Screen behaviour |
|---|---|---|---|
| Normal save | True | True | Clear dirty state, no message |
| Saved, frontmatter not stampable | True | False | Clear dirty state, **warn** (FR-018) |
| Write failed | False | False | Stay in edit, buffer intact, **error** (FR-020) |

`saved_text` exists so the screen can reset its dirty baseline to exactly what landed on disk,
including the stamped `updated` line — otherwise the buffer would read as dirty the instant it saved.

---

### `InitResult` (new, `core/models.py`)

```python
@dataclass(frozen=True, slots=True)
class InitResult:
    workspace: Workspace
    written: tuple[str, ...]   # guidance filenames created, e.g. ("AGENTS.md", "CLAUDE.md")
    skipped: tuple[str, ...]   # guidance filenames left alone because they already existed
```

Breaking change to `init_workspace`'s return type — justified in
[plan.md](./plan.md#complexity-tracking), migration is one line per call site.

---

### `EditSession` (in-memory, `tui/edit_screen.py`)

Not a dataclass — the screen's own attributes. Listed because the dirty rule is the feature's most
load-bearing invariant.

| Attribute | Meaning |
|---|---|
| `original_text` | The `\n`-normalised text the buffer is compared against. Set at load, **reset on every successful save** to `SaveResult.saved_text`. |
| `is_dirty` | Derived, never stored: `text_area.text != original_text`. |

**Invariant**: `is_dirty` is the sole trigger for the discard prompt (FR-024). Because it is a
comparison and not a flag, "no prompt after a save" and "no prompt after you retype the original" are
the same rule rather than two special cases.

---

## The save pipeline

The order is fixed and every step is required. `save_buffer(path, text, file, now)`:

```
1. stamp      stamp_updated(text, timestamp) -> (stamped_text, stamped: bool)
                 never raises; returns (text, False) when the block cannot be located
2. denormalise  "\n" -> file.newline; restore file.trailing_newline
3. write        NamedTemporaryFile in path.parent, newline="" -> flush -> os.replace(tmp, path)
                 any OSError -> unlink tmp, return SaveResult(ok=False, ...)
4. return       SaveResult(ok=True, saved_text=stamped_text, stamped=stamped, ...)
```

Step 1 before step 2 matters: the stamp operates on `\n` text so its line matching has one form to
handle. Step 3's temp file lives beside the target so the rename stays on one filesystem and stays
atomic.

**Nothing in this pipeline parses the buffer**, which is what lets FR-016 hold.

---

## `stamp_updated` — the matching rules

```python
def stamp_updated(text: str, timestamp: str) -> tuple[str, bool]: ...
```

Locates the block exactly as `_parse_document` does, so a file the scanner accepts is a file the
stamper accepts:

1. `text` must start with `---\n`, else `(text, False)`.
2. The block ends at the first `\n---` found from index 3, else `(text, False)`.
3. Within the block, find the **first** line matching `^updated:`; if none, `(text, False)`.
4. Replace that line with `updated: {timestamp}`, preserving the line's own ending. Everything before
   and after is untouched.

| Input shape | Result | Requirement |
|---|---|---|
| Well-formed six-field block | stamped, byte-identical elsewhere | FR-016, FR-017 |
| `created` present | **never touched** — it is not matched | FR-017 |
| Extra user-added field | preserved verbatim, still stamped | buffer-wins assumption |
| Fields reordered by hand | order preserved, still stamped | FR-016 |
| Single-quoted or unquoted values | quoting preserved, still stamped | FR-016 |
| No frontmatter at all | `(text, False)` | FR-018 |
| Unterminated block | `(text, False)` | FR-018 |
| Block with no `updated:` line | `(text, False)` | FR-018, [R1](./research.md#r1-the-updated-stamp-is-surgical-not-a-re-render) |
| Two `updated:` lines | first stamped, second untouched | deterministic; no guessing |
| `updated:` in the **body**, below the block | untouched | matching is scoped to the block |
| Empty buffer | `(text, False)` | edge case: empty save is allowed |

`timestamp` is `datetime.now().replace(microsecond=0).isoformat()` — the same shape
`create_document` already writes (`documents.py:51`), so a stamped file is indistinguishable in form
from a freshly created one.

---

## Validation rules

| Rule | Where enforced | Requirement |
|---|---|---|
| The buffer is written exactly, except the `updated:` line | `stamp_updated` never rewrites anything else | FR-016 |
| `created` is never modified | it is never matched by the stamper | FR-017 |
| A failed write leaves the file byte-identical | temp + `os.replace`; temp unlinked on error | FR-020 |
| Line endings and trailing newline survive | captured in `EditableFile`, restored in step 2 | FR-019 |
| No file but the target is touched | `save_buffer` takes one path and opens one directory | FR-023 |
| A document is never moved to match its date | no path is ever derived from frontmatter | FR-023 |
| An existing guidance file is never overwritten | `O_EXCL` in `init_workspace` | FR-049, FR-050 |
| `CLAUDE.md` duplicates no convention | contract test's forbidden-substring list | FR-048, SC-013 |

---

## State transitions

```
                 enter                    e
   ListScreen ──────────► PreviewScreen ──────► EditScreen
        ▲                    │     ▲                │
        └────── esc ─────────┘     │                │ ctrl+o  save, stay
                                   │                │ ctrl+s  alias
                                   │                │ ctrl+x  save, then ──┐
                                   │                │ esc                  │
                                   │                ▼                      │
                                   │        is_dirty ? DiscardDialog       │
                                   │           │            │              │
                                   │      Cancel│      Discard│             │
                                   │           ▼            ▼              │
                                   └───── back to Edit ─── to Preview ◄─────┘
```

Every transition is one keystroke (FR-001). The only branch in the diagram is the dirty check, and it
is the only place a confirmation can appear (FR-024, Principle V).

`PreviewScreen.on_screen_resume` re-reads the file on every return from `EditScreen`, so preview shows
saved content (FR-007) without the edit screen having to push anything back up the stack.

---

## What is *not* modelled

- **No undo stack of our own.** The widget's native history is whatever it is; the discard
  confirmation is the guarantee against losing work, per the spec's Assumptions.
- **No external-modification detection.** No mtime is recorded at load, deliberately — §5 makes the
  sync tool's conflict-copy behaviour the answer, and storing an mtime would be the first half of an
  implementation the spec forbids.
- **No `Document` reconstruction on save.** The list refreshes by re-scanning the one changed file
  through the existing scan path (FR-021), which is already the single place frontmatter becomes a
  `Document`.
