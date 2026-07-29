# Phase 0 Research: General Notes

**Feature**: `002-general-notes` | **Date**: 2026-07-28 | **Plan**: [plan.md](./plan.md)

Feature 001 shipped a working meetings implementation. Every question below is therefore not "what
should endpaper do?" but "how does a second document kind land on code that was written for one?"
The spec fixed the behaviour; this document fixes the shape.

---

## R1: How notes share code with meetings

**Decision**: Extract a collection-parameterised document layer in `core/documents.py`. A frozen
`Collection` descriptor carries everything that differs between the two kinds; `meetings.py` and
`notes.py` become thin, typed modules that bind their descriptor and re-export.

```python
@dataclass(frozen=True, slots=True)
class Collection:
    id_prefix: str                    # "m_" | "n_"
    create_dir: str                   # "meetings" | "notes"
    scan_dirs: tuple[str, ...]        # ("meetings",) | ("notes", "notes/daily")
    reserved_types: frozenset[str]    # frozenset() | {"daily"}

MEETINGS = Collection("m_", "meetings", ("meetings",), frozenset())
NOTES = Collection("n_", "notes", ("notes", "notes/daily"), frozenset({"daily"}))
```

**Rationale**: `create_meeting` and `scan_meetings` are ~130 lines that differ, between the two
kinds, in exactly four values. Everything expensive to get right — the `O_EXCL` collision loop, the
tolerant frontmatter walk, the warning taxonomy, the sort order, the token validation — is
identical and must stay identical, because FR-011 requires notes to follow the meeting rules "with
no note-specific variation".

The `Collection` descriptor is four fields and no behaviour. It is not an abstraction layer; it is
the list of things that vary, written down once so the compiler can see it.

**Alternatives considered**:

- **Copy `meetings.py` to `notes.py`** (~180 lines duplicated). Rejected as the option Principle III
  actually punishes: two scanners drift, and the first divergence is a silent behaviour difference
  between two document kinds the spec says must behave the same. Every future fix to the collision
  loop or the warning taxonomy would need finding twice.
- **Add a `kind: Literal["meeting", "note"]` field to the record and branch inside each function.**
  Rejected — it puts a conditional in the hot path of every function and makes "which directory does
  this write to?" a scattered `if` rather than a value. Branching on a field is the same coupling as
  a descriptor with worse locality.
- **A `DocumentStore` class with `MeetingStore`/`NoteStore` subclasses.** Rejected under Principle
  VI ("prefer a plain function to a class, a class to a framework"). Nothing here holds state
  between calls; a class would exist only to carry the four values the descriptor already carries.

---

## R2: Naming and backward compatibility of the core API

**Decision**: `Document` becomes the canonical record type and `DocumentFilter` the canonical
filter. `Meeting` and `Note` are exported aliases of `Document`; `MeetingFilter` is an alias of
`DocumentFilter`. The generic functions are `create_document`, `scan_documents`,
`filter_documents`, `match_document`; `create_meeting`, `scan_meetings`, `filter_meetings`, and
`match_meeting` remain as bound wrappers with unchanged signatures.

**Rationale**: The two kinds carry byte-identical frontmatter — the same six fields fixed by
REQUIREMENTS.md §4.6 — so one record type is the honest model. Aliasing rather than renaming keeps
feature 001's ~30 test modules and both adapters compiling untouched, which keeps this feature's
diff about notes instead of about a rename.

`Meeting = Document` is a true alias, not a subclass: a subclass would let the two drift back apart
and would make `isinstance` checks meaningful where they should not be.

**Recorded in CHANGELOG** as an additive core API change (Principle VI): new names added, no name
removed, no signature changed.

**Alternatives considered**: A hard rename with no aliases was rejected — it churns every existing
test for no user-visible gain. Keeping `Meeting` canonical and calling notes "meetings" internally
was rejected as the kind of naming that costs a reader an hour six months from now.

---

## R3: Making the daily note idempotent without a read-modify-write

**Decision**: `open_daily_note` attempts an exclusive create and treats `FileExistsError` as the
success path for "already exists".

```python
path = workspace.daily_dir / f"{when:%Y-%m-%d}.md"
path.parent.mkdir(parents=True, exist_ok=True)
try:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
except FileExistsError:
    return DailyNote(path=path, document=_read_one(path), created=False)
```

**Rationale**: FR-004 forbids altering an existing daily note in any way, and the strongest possible
guarantee of that is a code path that never opens the file for writing. `O_EXCL` makes the
create-or-open decision atomic in the kernel, so two processes racing on `endpaper note today`
cannot both create, cannot truncate each other, and cannot produce a second file for the day. This
is the same primitive feature 001 already uses for collision suffixing, so the failure mode is one
the codebase already understands.

The `exists()`-then-`create()` alternative has a window between the two calls. On a OneDrive-synced
folder, where a sync client can materialise a file at any moment, that window is not theoretical.

**Alternatives considered**:

- `path.touch(exist_ok=True)` then write if empty. Rejected: `touch` updates mtime on an existing
  file, and "did not modify" in SC-003 is verified by comparing file bytes *and* stat.
- `open(path, "x")` — equivalent semantics, but the codebase already uses raw `os.open` for the
  collision loop and mixing the two idioms for the same guarantee invites someone to "simplify" one
  of them into `"w"`.

---

## R4: What `open_daily_note` returns when the existing file is unparseable

**Decision**: Return a small result record, not a bare `Document`:

```python
@dataclass(frozen=True, slots=True)
class DailyNote:
    path: Path
    document: Document | None   # None when an existing file's frontmatter does not parse
    created: bool
```

**Rationale**: FR-005 and FR-021 pull in opposite directions on purpose. A daily note whose
frontmatter a user broke by hand is still *that day's note* — resolved by path, so `/note` must open
it rather than creating a second file — but it is *not* a listable record, because listing skips
what it cannot parse. Any return type that must produce a `Document` would have to invent an `id`,
a `created`, and a `title` for a file that has none, and inventing metadata is one short step from
writing it back.

`document=None` states the situation exactly: the file is real, we know where it is, and we know
nothing else about it. The CLI prints `path` regardless (FR-007). The TUI previews the file and
skips the in-memory list insert.

**Alternatives considered**:

- Return `Document | None` and let the caller re-derive the path. Rejected: the CLI must print a
  path even in the unparseable case, so `None` would lose the one thing it needs.
- Raise on unparseable. Rejected outright by Principle IV and FR-005 — this is the case where a
  user most needs the tool to still work.
- Repair the frontmatter in place. Rejected: Principle IV permits in-place repair only for the task
  format, where REQUIREMENTS.md §3.3 asks for it explicitly. FR-004 forbids it here.

---

## R5: Disambiguating `/note`, `/note <description>`, and `/note.<type> <description>`

**Decision**: Resolve on the *rest* of the input after the verb token, inside the existing command
bar:

| Typed | Stem | Type part | Rest | Action |
|---|---|---|---|---|
| `/note` | `note` | `""` | `""` | Open today's daily note |
| `/note vendor landscape` | `note` | `""` | non-empty | Create an untyped note |
| `/note.research vendor landscape` | `note` | `research` | non-empty | Create a `research` note |
| `/note.research` | `note` | `research` | `""` | Usage error: description required |
| `/notes` | `notes` | — | — | Switch the list to notes |

**Rationale**: The spec's Assumptions already settled the user-facing question (a description means
a note, never the daily note). What research adds is that this needs no new machinery:
`_run_command` already computes `stem`, `type_part`, and `rest`, so the rule is one branch on
`rest` being empty. `VERBS` gains `note` and `notes`, which is what FR-024 asks for.

The bare-`/note.research` row matters because it is the one input that would otherwise fall through
to `create_note("")`, which raises `UsageError` deep in core with a message about tag stripping.
Catching it at the bar produces the message the user needs.

**Alternatives considered**: A dedicated `/daily` verb was considered and rejected — REQUIREMENTS.md
§3.2 specifies `/note`, and adding a synonym means two things to document and two to type wrong.

---

## R6: Holding two collections in a one-screen TUI

**Decision**: The app scans both collections at mount and holds them in a `dict[str, list[Document]]`
keyed by collection name, with an `active` name. `/meetings` and `/notes` switch `active` and clear
the filter. The active collection is named in the status bar and in the empty-state message.

**Rationale**: Principle V fixes the TUI at one screen, so a second document kind must be a state of
the existing list, not a second screen. Scanning both at mount costs one extra directory walk —
measured against SC-005's 2-second budget for 1,000 files, the existing scan is comfortably inside
it and doubling it stays inside it. The alternative, scanning lazily on first switch, introduces a
visible pause on a keystroke, which is worse than a few milliseconds at startup.

Keying by name rather than by the `Collection` object keeps the dataclass out of the widget layer
and keeps the app's state trivially inspectable in tests.

**Alternatives considered**:

- **One merged list with a kind column.** Rejected: the spec's Assumptions rule it out, and FR-018
  requires the two to stay separate.
- **A `tab` toggle instead of verbs.** Rejected for this feature: REQUIREMENTS.md §3.4 reserves
  `tab` for the cross-workspace scope toggle, and spending it here would have to be undone.

---

## R7: Keeping `AGENTS.md` under 60 lines while documenting twice the commands

**Decision**: Restructure rather than append. The layout block gains real descriptions for `notes/`
and `notes/daily/` (replacing two "reserved for a future feature" lines), the frontmatter section is
retitled to cover both kinds since the schema is identical, and the command section documents
meetings fully and notes by their difference — the daily note and the two paths — rather than
repeating the tag rules.

**Rationale**: The template is at 57 lines against a ~60-line budget that Principle III and
REQUIREMENTS.md §4.3 both treat as a real constraint, backed by the finding that bloated context
files measurably increase exploration cost. Appending a parallel notes section would land near 90.
The saving is available because the two kinds genuinely share their schema and their tag rules:
saying so once is both shorter and more accurate than saying it twice.

Target after restructuring: ≤58 lines, asserted by the existing `test_agents_md.py` line-count test.

**Alternatives considered**: Raising the budget to 80 lines. Rejected — §4.3's number is a
deliberate constraint, and the first feature to argue its way past it makes it meaningless for the
next four.

---

## R8: The reserved `daily` type

**Decision**: `Collection.reserved_types` is checked in `create_document` before any filesystem
work, raising `UsageError` with a message that names `endpaper note today`.

**Rationale**: FR-012 requires the rejection and requires the message to name the alternative. Doing
it in `create_document` rather than in each adapter means the TUI and the CLI cannot disagree, which
is Principle II. Checking before the `mkdir` means a rejected create leaves no trace at all.

The concrete hazard being closed: `--type daily` would write `notes/2026-07-28-daily-x.md`, which
lists as a daily note (its frontmatter says so) but is not unique per day and is not what
`endpaper note today` resolves. Two things claiming to be the day's note is exactly the confusion
FR-004 exists to prevent.

**Alternatives considered**: Silently rewriting the type to `""`. Rejected — it discards what the
user typed without telling them, and Principle V requires errors that name what to do instead.

---

## R9: Windows path budget for notes

**Decision**: No new budget work is needed; notes are strictly shorter than meetings.

**Rationale**: Feature 001 computed the budget against `meetings/YYYY-MM-DD-<type>-<slug>.md`.
`notes/` is three characters shorter than `meetings/`, so a typed note with the same type and slug
is three characters shorter. `notes/daily/YYYY-MM-DD.md` is 25 characters, well under any typed
path. The existing `test_path_budget.py` is extended to cover the note paths so the property is
asserted rather than argued.

---

## R10: Test strategy for "the file did not change"

**Decision**: Assert on the file's bytes and its `st_mtime_ns` together, captured before and after
the second invocation.

**Rationale**: SC-003 promises a byte-identical file, and FR-004 separately forbids touching the
`updated` timestamp. Bytes alone would pass if a future change rewrote the file with identical
content, which would still be a violation on a synced folder — OneDrive re-uploads on mtime, so a
no-op rewrite is a real cost to the user even when the content matches. Checking both makes the
weaker implementation fail the test.

**Alternatives considered**: Content-only comparison, rejected above. Mocking the filesystem,
rejected — the guarantee being tested is about real `open` flags, and a mock would assert the
implementation rather than the property.
