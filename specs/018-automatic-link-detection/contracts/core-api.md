# Contract: the core API

**Feature**: `018-automatic-link-detection`

Two new public functions in `src/choom/core/links.py`, one new value type in `core/models.py`, one new
field on an existing one. Both functions are exported from `choom.core.__all__`.

---

## C1. `format_bare_urls`

```python
def format_bare_urls(text: str) -> tuple[str, tuple[UrlConversion, ...]]:
    """Wrap every bare http:// or https:// URL in `text` as a markdown link.

    Each bare URL becomes ``[<url>](<destination>)`` with the URL reproduced
    byte-for-byte in both slots; the destination is angle-wrapped only when it
    contains a space, ``(``, ``)``, ``<``, or ``>``, by the same rule
    `_render_destination` applies to every other link choom writes.

    A URL is skipped -- left byte-identical -- when it sits in frontmatter, a
    fenced code block, an inline code span, an HTML comment, an existing link or
    image, a CommonMark autolink, a raw HTML tag, or a link reference
    definition; when it has no host after ``://``; when it does not begin a
    token; or when it contains ``[`` or ``]``.

    Returns `text` itself -- the same object -- when nothing was converted, so a
    caller can test identity and skip work entirely.

    Idempotent: `format_bare_urls(format_bare_urls(t)[0])[0] == format_bare_urls(t)[0]`.

    Never raises. Any input is valid input.
    """
```

### Guarantees

| # | Guarantee |
|---|---|
| G1 | Only ever wraps. No character of a URL is edited, reordered, re-encoded, or dropped. |
| G2 | Never inserts or removes a newline, so every line number in `text` is stable. |
| G3 | Exactly idempotent, through any number of passes. |
| G4 | Returns the identical object when there is nothing to do. |
| G5 | Never raises, for any input including the empty string. |
| G6 | Conversions are non-overlapping and ascending by `start`. |
| G7 | Requires no `Workspace`, no `Path`, no filesystem, no network, no terminal. |

### Non-goals

Resolves nothing against the workspace, unlike `heal_text` — a URL is self-describing. Reports no
warnings: there is no such thing as a dead external URL to choom, and checking would need the network.

---

## C2. `map_cursor_offset`

```python
def map_cursor_offset(conversions: tuple[UrlConversion, ...], offset: int) -> int:
    """Where `offset` -- a character offset into the text handed to
    `format_bare_urls` -- ends up in the text it returned.

    An offset before every conversion is unchanged. An offset after one is
    shifted right by the length each earlier conversion added. An offset
    strictly inside a converted span lands at the end of that span's
    replacement, since there is no meaningful position between the two copies
    of the URL.

    Pure integer arithmetic over `conversions`; reads no text. Never raises.
    """
```

Exists so the cursor rule is decided in core and unit-tested against integers, rather than re-derived
inside a widget by diffing two strings.

---

## C3. `UrlConversion`

Frozen slotted dataclass in `core/models.py`. Fields and invariants: see
[data-model.md](../data-model.md) §1.

```python
@dataclass(frozen=True, slots=True)
class UrlConversion:
    start: int
    end: int
    url: str
    replacement: str
```

---

## C4. `SaveResult.conversions`

One additive, defaulted field:

```python
conversions: tuple[UrlConversion, ...] = ()
```

Additive and defaulted, so every existing construction site and test is unaffected. `SaveResult` is
internal to core — it appears in no `--json` payload and no CLI output — so Principle II's schema
stability rule is not engaged. `()` on a failed save.

---

## C5. `save_buffer` — changed behaviour

Signature unchanged. The conversion is **unconditional**: unlike link healing, it does not depend on
`workspace` being passed, because it needs nothing from the workspace.

Order inside the function (research R10):

```
1. heal_text(...)              # existing; only when workspace is not None
2. format_bare_urls(...)       # NEW; always
3. stamp_updated(...)          # existing
4. _apply_line_ending_policy   # existing
5. write_text_atomic           # existing -- still exactly one write
```

- `saved_text` reflects the conversion, so the caller's buffer re-sync shows what landed.
- `conversions` carries the edits.
- Steps 1 and 2 act on provably disjoint spans: a healed record link's destination carries no scheme,
  and this feature masks that whole span; a converted link's destination *does* carry a scheme, and
  `_link_from_match` returns `None` for it.

### Callers that must NOT gain this behaviour

| Function | Why not |
|---|---|
| `mirrors.write_document` | The sync path. Ticking a checkbox is not an edit to the note (FR-029 of spec 008). |
| `mirrors.reconcile_on_open` | Runs on open. Converting there would rewrite a document the user has not touched. |
| `tasks.set_task_body` | Two callers, one of which is reconcile-on-open (research R9). The conversion goes at the *save* call site instead. |
| `links.heal_links` | Would rewrite prose across a whole workspace — the outcome the 008 contract records as rejected outright. |
| `links.check_links` | Writes nothing, ever. |
| `documents.create_document` | Writes frontmatter and no body. Nothing to convert. |
| `tasks.add_task` | A task description becomes a mirror's link text; a nested link is not valid CommonMark (FR-018). |

An integration test pins the second and third rows: opening a task whose body holds a bare URL, with
no save, must leave the file byte-identical.

---

## C6. No CLI change

No command, no flag, no `--json` key, no exit code, no `AGENTS.md` change (FR-029). `tests/contract/`
is untouched.
