# Data Model: Bare URLs Become Markdown Links on Save

**Feature**: `018-automatic-link-detection` | **Date**: 2026-08-02

This feature introduces **no persisted state**. Nothing here is written to disk, serialised, cached,
or carried between saves. Every value below lives for the duration of one save and is discarded.

---

## 1. `UrlConversion` (new)

`src/choom/core/models.py`, a frozen slotted dataclass alongside the module's other value types.

| Field | Type | Meaning |
|---|---|---|
| `start` | `int` | Character offset in the **original** text where the bare URL begins |
| `end` | `int` | Character offset in the **original** text one past the URL's last character |
| `url` | `str` | The matched URL, byte-for-byte as it appeared |
| `replacement` | `str` | What was written in its place — `[url](destination)` |

### Invariants

1. `original[start:end] == url` — the record always describes a slice that was really there.
2. `replacement == f"[{url}]({render})"` where `render` is `_render_destination(url)`: `url` bare, or
   `<url>` when it contains any of ` ()<>`.
3. `len(replacement) > len(url)` — the transform only ever grows the text. There is no conversion
   that shortens or preserves length, which is what makes the cursor mapping in §3 monotonic.
4. `"\n" not in replacement and "\r" not in replacement` — no conversion inserts a line break.
   This is what keeps every line number in the document stable across a save (research R2).
5. `url` contains no whitespace and none of `<`, `>`, `[`, `]` (research R7), so neither slot of
   `replacement` can be malformed.
6. Conversions in a tuple are **non-overlapping and strictly ascending** by `start`.

### Why the edits are returned rather than just a count

FR-025 needs only a count, which `len(conversions)` gives. The offsets exist for FR-026's cursor
mapping (§3). Returning the edits keeps that arithmetic in core, where it is unit-testable against
integers, instead of re-deriving it in a widget from the before/after strings.

### Lifetime

Constructed inside `format_bare_urls`, returned to `save_buffer`, carried on `SaveResult`, read once
by `EditorPane._save`, discarded. Never persisted, never compared across saves.

---

## 2. `SaveResult.conversions` (new field)

`SaveResult` already exists and already carries `warnings`. One field is added:

```python
@dataclass(frozen=True, slots=True)
class SaveResult:
    ok: bool
    saved_text: str
    stamped: bool
    message: str
    warnings: tuple[ScanWarning, ...] = ()
    conversions: tuple[UrlConversion, ...] = ()   # new, defaulted
```

Additive and defaulted, so every existing construction site and every existing test keeps working
unchanged. `SaveResult` is an internal core return type — it is not part of any `--json` schema and
appears in no CLI output — so Principle II's schema-stability rule is not engaged.

On a failed save (`ok=False`) `conversions` is `()`, matching how `saved_text` is already `""` there:
nothing landed, so nothing is reported.

---

## 3. Cursor mapping (derived, not stored)

`map_cursor_offset(conversions, offset) -> int` is a pure function over §1, with no state of its own.

Given a character offset into the **original** text, it returns the corresponding offset in the
converted text:

| Where the offset falls | Result |
|---|---|
| Before every conversion | unchanged |
| After a conversion | shifted right by `len(replacement) - (end - start)`, summed over all conversions ending at or before it |
| Strictly inside a conversion's span | the offset of the **end** of that conversion's replacement |

The third row is the case that matters: a cursor sitting in the middle of a URL the user just pasted
has no meaningful position inside `[url](url)`, so it lands after the whole link rather than between
the two copies.

Row is not part of the mapping. Invariant 4 guarantees no conversion inserts a newline, so a cursor
never changes line and the adapter only ever needs the column corrected.

---

## 4. Excluded span (transient, internal)

Not a type. The seven masks in research R2 produce a single length-preserving masked **string**, not
a list of ranges — the same representation `_mask_fences` and `_mask_code_spans` already use, and the
reason offsets found in the masked text are valid in the original.

Recorded here because it is a deliberate modelling choice: a list of `(start, end)` exclusion ranges
would have to be merged, sorted, and searched per candidate, and would let two masks disagree about
an overlap. A masked string composes by function application and cannot.

---

## 5. What is deliberately *not* modelled

| Not modelled | Why |
|---|---|
| A record of which URLs were converted in a file | Nothing persists. The next save recomputes from the text, and idempotency makes that free. |
| An "already converted" marker in the document | The markdown *is* the marker — a converted URL is inside a link span and is therefore masked (research R6). A sentinel would be a second source of truth. |
| A per-workspace or per-document setting | FR-027. See spec.md §"Why there is no setting". |
| An undo record | FR-028. The editor's own undo and the buffer re-sync are the remedy. |
| A `Link` for a converted URL | External URLs are outside the 008 id-and-path grammar by design. `_link_from_match` returns `None` for any scheme-carrying destination, so a converted link never becomes a `Link`, never reaches the Links pane, and never appears in `links check` (FR-020, verified). |
