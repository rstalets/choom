# Contract: Terminal interface (notes)

**Baseline**: [feature 001's TUI contract](../../001-meeting-notes/contracts/tui.md). Screens,
bindings, and the command-bar mechanics are unchanged except where stated.

**Principle V holds**: one screen, one-keystroke transitions, every binding in the footer. This
feature adds **no screen and no key binding**. Notes are a state of the existing list.

---

## Command-bar verbs

`VERBS` grows from `{meeting, meetings, init}` to `{meeting, meetings, note, notes, init}` (FR-024).
Everything else about mode resolution is unchanged: the first token's stem decides command vs
filter, a leading space forces filter mode, and the resolved mode is shown in the status bar as the
user types, before `enter` commits it.

The status bar shows `[command: note.research]` or `[filter]` exactly as it does for meetings — so a
user who types `notes` intending to filter for the literal word sees the mode flip and can prepend a
space.

---

## The `/note` grammar

Resolved on whether anything follows the verb token
([R5](../research.md#r5-disambiguating-note-note-description-and-notetype-description)):

| Typed | Type part | Rest | Action |
|---|---|---|---|
| `/note` | `""` | `""` | Open today's daily note |
| `/note vendor landscape` | `""` | non-empty | Create an untyped note |
| `/note vendor landscape #procurement` | `""` | non-empty | Create an untyped note tagged `procurement` |
| `/note.research vendor landscape` | `research` | non-empty | Create a `research` note |
| `/note.research` | `research` | `""` | **Usage error** — a type without a description |
| `/note.daily anything` | `daily` | non-empty | **Usage error** — reserved type (FR-012) |
| `/notes` | — | — | Switch the list to notes |
| `/meetings` | — | — | Switch the list to meetings |

**`/note` with a description never creates or opens the daily note.** This is the spec's Assumption
made concrete: a user who types words expects those words to become a note, and the reading in which
they are discarded is the one to avoid. Bare `/note` — no type, no description — is the daily note.

**`/note.research` with no description** is caught at the bar rather than falling through to
`create_note("")`, which would surface core's message about tag stripping. The bar's message names
the missing part: `note.research needs a description`.

Errors from a create appear in the status bar, styled as feature 001 already styles them, and clear
on the next keystroke. No modal, no dialog — nothing here is destructive.

---

## Collection switching

```
/notes     → active collection becomes notes,    filter cleared, selection reset to the top
/meetings  → active collection becomes meetings, filter cleared, selection reset to the top
```

**State** ([R6](../research.md#r6-holding-two-collections-in-a-one-screen-tui)): the app scans both
collections once at mount and holds `documents: dict[str, list[Document]]` keyed by collection name,
plus an `active` name. Switching re-derives the visible list from the already-scanned data — no disk
access, so it is instant and FR-026's no-disk-per-keystroke rule extends to switching.

**The active collection must be identifiable on screen** (FR-025). It appears in two places:

- The status bar names it: `notes` / `meetings` alongside the existing key hints.
- The empty-state message names it: `No notes yet. Press / then 'note' for today's note, or 'note <description>'.`

Two indicators rather than one because the status bar is where a user looks for state and the empty
state is the only thing on screen when the list is empty — the case where "which list am I even
looking at?" is hardest to answer.

**Filter is cleared on switch.** A filter typed against meetings almost never means the same thing
against notes, and carrying it over would show an unexplained empty list. Clearing is the behaviour
a user can predict.

**Both lists stay current** (FR-030). Creating a note updates the in-memory notes list immediately,
so switching away and back shows it without a rescan. This is the same mechanism feature 001 uses
for `on_screen_resume` after a create lands in preview.

---

## Opening the daily note from the bar

`/note` (bare) calls `open_daily_note` and lands the user in the preview of that file — created or
pre-existing, the destination is the same. This matches feature 001's rule that a create from the
bar leaves the user in preview of the new file.

Three cases, from the `DailyNote` result:

| Result | List | Preview |
|---|---|---|
| `created=True, document=<record>` | Insert at the top of the notes list | Preview the new record |
| `created=False, document=<record>` | Already present; select it | Preview that record |
| `created=False, document=None` | Not inserted — it does not parse, so it is not a listable record | Preview the file's body, with a status-bar note that its frontmatter could not be read |

The third row is the case FR-005 exists for. The user gets their note open, which is what they
asked for, and is told why it is absent from the list — rather than the tool silently creating a
second file for the day or refusing to open anything.

**Nothing in any of these paths writes to an existing file.**

---

## Preview of a document with no record

`render_preview_markdown` currently takes a `Document` and reads its `path`. It changes to take
`(path: Path, document: Document | None)`:

- `document` present — unchanged: an `# title` heading, a metadata line, then the body with the
  frontmatter block stripped.
- `document is None` — the body with the frontmatter block stripped, under a `# <filename>` heading,
  with no metadata line. Nothing is invented for the fields that could not be read.

The frontmatter block is stripped in both cases. It is not valid standalone markdown and collapses
into one paragraph if rendered, which is feature 001's existing reasoning and applies equally to a
file whose frontmatter is broken.

---

## Rows

A note row renders exactly like a meeting row: `date  type  title  tags`. A daily note shows its
date in both the date column and the title column, since its title is its ISO date. That repetition
is accepted — the alternative is a special case in the row renderer that makes daily notes look
different from every other document for no gain.

---

## Bindings

Unchanged. No key is added, rebound, or removed.

| Key | State | Action |
|---|---|---|
| `/` | list | Open the filter/command bar |
| `↑` `↓` `j` `k` | list | Move selection |
| `enter` | list | Open the selected document in preview |
| `esc` | preview | Back to the list |
| `ctrl+q` | any | Quit |

**`tab` is deliberately left unbound.** REQUIREMENTS.md §3.4 reserves it for the cross-workspace
scope toggle. Spending it on collection switching here would have to be undone in the next feature,
and a binding that moves between releases is worse than one that arrives late.

**No editing affordance.** The preview footer must not advertise an edit key (FR-028). §3.5's edit
state is a later feature, and a footer that promises a key which does nothing is worse than a footer
that stays quiet about it.
