# Contract: `endpaper.core` public API

**Feature**: `009-inline-task-capture`

Every signature below is callable without a terminal, a TTY, or an event loop (Principle I). All new
functions carry type hints and a docstring stating what they return and what they raise (Principle VI).
Nothing here imports `textual`, `rich`, or `argparse`.

New module: **`endpaper/core/mirrors.py`**. It owns the edge between a checkbox in a document and a task in
`tasks.md` — recognition, splicing, conflict resolution, and the non-stamping write. `links.py` owns the
grammar; `tasks.py` owns `tasks.md`; this owns neither and depends on both. See
[plan.md](../plan.md#project-structure) for why it is a third module.

**Depends on `008-document-links`** for `find_links`, `resolve_id`, `relative_destination`, `Task.links`,
`render_task_line(links=…)`, and `ScanWarningReason`. None of it is reimplemented here.

---

## Recognition

```python
def find_mirrors(text: str, *, source: Path) -> tuple[Mirror, ...]:
    """Every checklist line in `text` that is a control surface onto a task.

    A line qualifies when it matches the checklist prefix *and* carries a link whose
    destination fragment is a task id. Where a line holds several such links the first
    is the mirror and the rest are ordinary links.

    Delegates link-finding to `links.find_links`, so fenced code blocks, inline code
    spans, images, and URL-scheme destinations are excluded before this ever sees them.

    Each Mirror carries the character offset of its single state character, so a caller
    splices rather than re-renders.

    Never raises. Any input is valid input; a line this cannot make sense of is a line
    the user typed.
    """
```

The prefix rule and the full set of what does and does not qualify are in
[mirror-format.md](mirror-format.md#recognition).

---

## Writing a mirror

```python
def mirror_line(task: Task, *, source: Path, tasks_file: Path) -> str:
    """The checklist line to leave in `source` for `task`.

    The destination path comes from `links.relative_destination(source, tasks_file)`,
    so it is correct from any depth the layout produces and is never assembled here.
    The link text is the task's description as stored -- tags already extracted.

    Pure string arithmetic. Touches no filesystem. Never raises.
    """
```

```python
def capture_task(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    source: Path,
    source_id: str,
    now: datetime | None = None,
) -> tuple[Task, str]:
    """Create a task linked to the document it was captured in, and return it with the
    line to leave behind.

    Description parsing, #tag extraction, token validation, id generation, and line
    rendering all go through `tasks.add_task` -- this adds the link and the mirror and
    nothing else, so a task's shape never depends on where it was typed (FR-004).

    Raises:
        UsageError: the description is empty after removing #tag tokens, or a type or
            tag token is rejected. Nothing is written.
        OSError: tasks.md could not be written. Nothing is written.
    """
```

`capture_task` deliberately does not save `source`. The caller saves first (FR-005) and is the only party
that knows whether the buffer is dirty; ordering is specified in
[research.md](../research.md#r8-the-capture-sequence-and-what-happens-when-a-step-fails).

---

## Reconciliation

```python
def reconcile_on_open(workspace: Workspace, text: str, *, source: Path) -> MirrorReport:
    """Bring every mirror in `text` into agreement with tasks.md.

    The task is authoritative: the user has not acted on this document yet. A mirror whose
    id resolves to no task is left byte-identical and warned about (FR-028).

    Returns `text` itself -- the same object -- when nothing needed correcting, so a caller
    can test identity and skip the write entirely (FR-030).

    Reads tasks.md only when `text` actually contains a mirror; a document with none costs
    one scan of a string already in memory and no file read at all (SC-007).

    Never raises. An unreadable tasks.md yields the text unchanged plus a warning.
    """
```

```python
def reconcile_on_save(
    workspace: Workspace,
    text: str,
    *,
    source: Path,
    baseline: Mapping[str, bool],
) -> MirrorReport:
    """Reconcile at save time, writing tasks.md where the user's edit should win.

    `baseline` is what each mirror read when the document was opened or last reconciled.
    It is what distinguishes "the user ticked this box" from "this box is stale", and so
    what makes the both-sides-changed warning possible (FR-024). A task id absent from
    `baseline` is a mirror that appeared during this session and counts as the user's edit.

    Writes tasks.md through `tasks.set_task_state`, one character on one line located by id.
    Corrections that should flow the other way are applied to the returned text in the same
    pass, so nothing cascades (FR-027).

    The full outcome matrix is in mirror-format.md.

    Never raises. A task that cannot be written is reported in `warnings`, and every other
    task in the document is still reconciled.
    """
```

```python
def propagate_to_documents(
    workspace: Workspace,
    task: Task,
    *,
    skip: Container[Path] = (),
) -> tuple[ScanWarning, ...]:
    """Write `task`'s state into the mirrors of every document it links to.

    Called after tasks.md has already been written -- never before, and never conditionally.
    A document that is missing, unreadable, unwritable, or whose link is dead produces a
    warning and does not stop the others (FR-032).

    `skip` names documents the caller knows are open with unsaved changes; they are left
    alone and reconciled at the user's next save (FR-033).

    Documents are written without stamping `updated` (FR-029), and only when a splice
    actually changed something.

    Never raises. Every failure is a warning.
    """
```

---

## The non-stamping write

```python
def write_document(path: Path, text: str, file: EditableFile) -> SaveResult:
    """Write `text` to `path` atomically, restoring `file`'s line endings and trailing
    newline, without stamping `updated`.

    This is the sync path. A user save goes through `editing.save_buffer`, which stamps.
    The distinction is the whole of FR-029: ticking a box in the tasks list is not an edit
    to the meeting note.

    Same-directory temp file plus os.replace, exactly as `save_buffer` and
    `tasks._atomic_write` already do. Never raises on a write failure -- returns
    SaveResult(ok=False) with a user-facing message, leaving the target byte-identical.
    """
```

---

## Changes to existing signatures

### `core.tasks.add_task` — gains `links`

```python
def add_task(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    links: Sequence[str] = (),     # NEW
    now: datetime | None = None,
) -> Task:
```

Passed straight through to `render_task_line`, which 008 already teaches to emit the field between `tags`
and `created`. A call without `links` produces a line identical to today's (FR-019).

### `core.editor_commands` — `/task` registered, and a dotted suffix

```python
EDITOR_COMMANDS = (
    EditorCommand(name="ai",   ...),
    EditorCommand(name="link", ...),                       # from 008
    EditorCommand(name="task", argument="<description>",   # NEW
                  description="Capture a task; this line becomes a link to it",
                  requires_argument=True,
                  accepts_suffix=True),                    # NEW field on EditorCommand
)
```

`parse_line` gains one `partition(".")` on the verb before the table lookup, mirroring
`tui/command_bar.py:114` so the two never disagree about what `/task.followup` means. A suffix on a command
whose `accepts_suffix` is `False` returns a parse result the dispatcher rejects with a message, rather than
silently discarding it.

`ParsedCommand` gains `suffix: str = ""`.

### `core.models` — new members

`Mirror`, `MirrorReport`, `MirrorResolution` as described in [data-model.md](../data-model.md#in-memory).

`ScanWarningReason` gains `"mirror_conflict"` and `"mirror_ambiguous"`. Dead mirrors reuse 008's
`"link_dead"` — a mirror pointing at a task that does not exist is a dead link, and inventing a second
reason for it would split one condition across two channels.

---

## Exports

All of the above are re-exported from `endpaper.core.__init__` alongside the existing surface.
`tests/unit/test_core_imports.py` guards that the public names stay importable.

---

## What this contract deliberately does not add

- **No workspace scan.** Nothing here calls `inbound_links`. Reconciliation reads the document in hand and
  `tasks.md`, and propagation reads the documents a task names. See
  [research.md](../research.md#r3-which-documents-a-toggle-writes-to).
- **No new argument on `save_buffer`.** 008 threads `workspace` through it for link healing; this feature
  does not thread a baseline through as well. See
  [research.md](../research.md#r5-the-two-write-paths-and-why-save_buffer-is-not-overloaded).
- **No persisted baseline.** It is a call argument and a screen attribute, and it dies with the screen.
