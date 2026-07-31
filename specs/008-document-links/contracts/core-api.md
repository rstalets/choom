# Contract: `endpaper.core` public API

**Feature**: `008-document-links`

Every signature below is callable without a terminal, a TTY, or an event loop (Principle I). All
new functions carry type hints and a docstring stating what they return and what they raise
(Principle VI). Nothing here imports `textual`, `rich`, or `argparse` — enforced by the ruff
banned-api rule.

New module: **`endpaper/core/links.py`**. It holds the whole primitive — scanner, resolver, path
derivation, healer, inbound scan — because those are four views of one grammar and separating them is
how a byte-preservation guarantee gets quietly broken (see plan.md, Structure Decision).

---

## Scanning

```python
def find_links(text: str, *, source: Path, in_tasks_field: bool = False) -> tuple[Link, ...]:
    """Every CommonMark inline link in `text` that could name a record.

    Skips images, destinations carrying a URL scheme, and anything inside a fenced code
    block or an inline code span -- those are content, not links (FR-009, FR-010).
    Reference-style links (`[a][ref]`) are not recognised; endpaper never writes one.

    Each Link carries `start`/`end` character offsets into `text`, so a caller can splice
    a replacement destination in without re-rendering the document.

    Never raises. Any input is valid input.
    """
```

The masking rules are the load-bearing part and are specified in
[link-format.md](link-format.md#grammar). They were verified against 15 probe cases (research R1),
including a double-backtick span containing a backtick, an unclosed fence, and a fence whose info
string contains the fence character.

---

## Resolution

```python
def resolve_id(workspace: Workspace, target_id: str) -> tuple[LinkTarget | None, tuple[ScanWarning, ...]]:
    """Find the record `target_id` names, searching documents and then tasks.md.

    The id prefix says which collection to look in, so a full workspace scan is avoided
    where the prefix is recognised. Ids are compared whole, never split or offset-parsed
    (FR-014), so ids written under the old single-letter scheme resolve unchanged.

    Returns (None, ()) when nothing carries the id -- that is `dead`, a valid state, not an
    error. When two records carry the same id, returns the first in path-sort order plus a
    `link_ambiguous` warning naming every path (R11).

    Never raises.
    """


def resolve_link(workspace: Workspace, link: Link) -> tuple[LinkTarget | None, LinkStatus]:
    """Resolve one link, id first and path second (FR-006).

    Returns the target and what is currently true of the link:
      resolved -- id resolves and the path already points at it
      stale    -- id resolves but the path is wrong or absent, or the fragment is absent
      dead     -- neither the id nor the path names anything

    Never raises.
    """
```

---

## Path derivation

```python
def relative_destination(source: Path, target: Path) -> str:
    """The link destination path from `source`'s directory to `target`.

    Forward slashes on every platform, because a link destination is a URL and a
    Windows-authored `\\` does not resolve for a colleague on macOS (R3). Wrapped in angle
    brackets by the caller when it contains a space or parenthesis (R4).

    Pure string arithmetic on two paths; touches no filesystem. Never raises.
    """
```

Verified to round-trip from every depth the layout produces, including a document outside the dated
layout — table in [link-format.md](link-format.md#path-derivation).

---

## Healing

```python
def heal_text(
    workspace: Workspace,
    text: str,
    *,
    source: Path,
) -> tuple[str, tuple[LinkReport, ...], tuple[ScanWarning, ...]]:
    """Rewrite every stale link in `text`; leave every dead link byte-identical.

    A byte-level splice of link destinations only. Link text, surrounding prose, and line
    endings are untouched (FR-026); the document is never round-tripped through a parser.

    Returns the new text, a report per link that was stale or dead, and a warning per dead
    link. `text` is returned unchanged when nothing is stale, so a caller can compare
    identity to decide whether a write is needed at all.

    Never raises. A dead link is reported, not fatal (FR-025).
    """
```

The "returned unchanged when nothing is stale" property is what lets `links heal` honour "a repair
pass does not invent modifications" — a file with nothing stale is never opened for writing.

---

## Inbound and outbound

```python
def outbound_links(workspace: Workspace, source: Path) -> tuple[tuple[Link, LinkStatus], ...]:
    """Links `source` points at, including any that do not resolve.

    Reads one file. For a document already in memory, prefer `find_links` directly -- this
    is the convenience form. Never raises; an unreadable file yields ().
    """


def inbound_links(workspace: Workspace, target_id: str) -> tuple[Link, ...]:
    """Every link in the workspace that points at `target_id`, computed now by scanning.

    Nothing is stored, nothing persists between calls, and no file is written (FR-027,
    FR-028). Each file's bytes are substring-tested for the id first and only parsed when
    that hits, so this never parses the frontmatter of the workspace (FR-030).

    An occurrence of the id that is not inside a link -- prose, or the target's own
    frontmatter `id:` line -- is not a link and is not returned.

    Measured at 155 ms across 6,000 documents (50.3 MB) against SC-006's 500 ms budget.

    Never raises. An unreadable file is skipped.
    """
```

The candidate filter is a correctness boundary as well as a performance one: a substring hit is a
*candidate*, and only a link found by `find_links` whose fragment equals `target_id` is a result.

---

## Search, for `/link`

```python
def find_link_targets(workspace: Workspace, query: str) -> tuple[LinkTarget, ...]:
    """Records whose title or id matches `query`, case-insensitive substring.

    Reuses the same matching rule as the list filter (`match_document`) so `/link` and the
    TUI filter never disagree about what "matches" means. Caller decides what to do with
    zero or several results; this reports, it does not choose (FR-044).

    Never raises.
    """
```

---

## Changes to existing signatures

### `core.editing.save_buffer` — gains `workspace`

```python
def save_buffer(
    path: Path,
    text: str,
    file: EditableFile,
    *,
    now: datetime | None = None,
    workspace: Workspace | None = None,   # NEW
) -> SaveResult:
```

When `workspace` is given, stale links are healed **before** `updated` is stamped; dead links are
reported in `SaveResult.warnings`. When it is `None`, behaviour is exactly as today.

This is the seam that makes FR-022 true for both adapters from one place. It has one production
caller (`tui/edit_screen.py`), and the keyword default keeps the four existing test call sites
compiling (R5).

`SaveResult` gains `warnings: tuple[ScanWarning, ...] = ()`. A dead link never sets `ok=False`.

### `core.tasks` — `links` throughout

```python
_RECOGNIZED_KEYS = frozenset({"id", "type", "tags", "links", "created"})   # + "links"

def render_task_line(
    text: str, *, done: bool = False, id: str,
    type: str = "", tags: Sequence[str] = (),
    links: Sequence[str] = (),        # NEW -- rendered between tags and created
    created: date | None = None,
) -> str:
```

`Task` gains `links: tuple[str, ...]`, defaulting to `()`.

Adding the key to `_RECOGNIZED_KEYS` is not merely additive. Today an unrecognised key makes
`_classify_body` return `malformed`, which drops the whole task from every listing — so a user who
hand-writes `links:` currently loses that task. This fixes that (R7).

### `core.text` / collections — id prefixes

```python
MEETINGS = Collection("meeting_", ...)   # was "m_"
NOTES    = Collection("note_", ...)      # was "n_"
def new_meeting_id(when: date) -> str: ...  # "meeting_" prefix
def new_task_id(taken: Container[str]) -> str: ...  # "task_" prefix
```

No signature changes; four literals. `new_meeting_id` has no production caller and is updated for
consistency only.

### `core.editor_commands` — `/link` registered

```python
EDITOR_COMMANDS = (
    EditorCommand(name="ai",   ...),
    EditorCommand(name="link", argument="<search terms>",
                  description="Insert a link to the matching record",
                  requires_argument=True),   # NEW
)
```

`parse_line` needs no change — it dispatches off the table, so registering the command is the whole
parser change, and `/help` picks it up automatically.

### `core.models` — new members

`ScanWarningReason` gains `"link_dead"` and `"link_ambiguous"`. Reusing `ScanWarning` rather than
inventing a second reporting channel means dead links surface through the paths that already print
warnings in both adapters.

---

## Exports

All of the above are re-exported from `endpaper.core.__init__` alongside the existing surface, and
`tests/unit/test_core_imports.py` guards that the public names stay importable.
