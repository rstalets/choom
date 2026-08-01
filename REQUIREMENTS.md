# endpaper — Design Intent & Conventions

**What this file is.** The living record of what endpaper is for and the conventions every
feature must honour — the frontmatter schema, the id scheme, the file layout and why it is
frozen, the task line format, link semantics, and the registries that shift as features
ship. It is expected to change when a feature changes one of them.

**What it is not.** Not a tracker. Work in flight, backlog, and ideas live in GitHub
issues. Shipped behaviour is described in the README and recorded in the release notes.
Per-feature design history lives under `specs/`.

`.specify/memory/constitution.md` holds the bedrock — the principles that only change by
deliberate amendment. Where this document and the constitution disagree, the constitution
wins.

---

## 1. Problem statement

Markdown is the native format of AI assistants. Agents read it, write it, diff it, and reason over it without any adapter layer. A person whose working notes live in plain markdown files can hand their entire context to Claude, Copilot, or any other assistant for free.

Almost nobody at a large company can do this. Markdown-first tools — Obsidian, Logseq, Foam — are rarely on the approved-software list, and the sanctioned alternatives (OneNote, Confluence, SharePoint) store notes in proprietary formats behind authenticated APIs. The result is that the people with the most meetings, the most decisions to track, and the most to gain from an AI assistant that knows their context are precisely the people whose context is locked in a format their assistant can't reach.

The workarounds fail in predictable ways. Copy-pasting into a chat window loses everything the moment the session ends. Personal markdown folders become unnavigable within weeks because nothing enforces structure or provides search. Full note-taking apps demand installation rights, a server, or a cloud account.

**endpaper is a local-only, Python, terminal-based tool for capturing and organizing meeting notes, general notes, and tasks as plain markdown files** — structured enough for a human to navigate through a TUI, and legible enough that an AI assistant can read and edit the vault directly, without any integration work. It installs without admin rights, stores nothing outside a directory the user already has, and works on a OneDrive-synced folder so a team can share a workspace without a server.

---

## 2. Desired user experience

### The human

The tool disappears into the twenty seconds before a meeting starts. You type `/meeting.standup Q3 planning #platform`, a file exists with correct frontmatter and a date-stamped name, and you're typing notes before anyone has finished joining the call. You never decide where a file goes or what to call it.

Later you type `/meetings`, arrow down a list, and hit enter. The note opens rendered as formatted markdown, because reading it is what you came to do. You press `e` and you're editing the raw file. `ctrl+o` saves, `ctrl+x` saves and drops you back to the rendered view, and escape backs out without saving — asking first, but only if you'd actually lose something.

Tasks work the same way: `/task.followup send the vendor comparison #procurement` to capture, `/tasks` to see the list, arrows to move, space to complete. No project hierarchy, no due-date syntax, no priority scheme.

The whole surface is a filterable list and a preview pane. There is exactly one screen.

### The AI assistant

An assistant that lands in an endpaper workspace should be productive without instruction.
It reads `AGENTS.md` at the root, learns the folder layout and the commands that matter,
and works from there.

**Records are created through commands; bodies are edited directly.** Creating a record is
what puts a file in the right partition, with correct frontmatter and a generated id — the
conventions in §3.2 that an assistant would otherwise have to reproduce by hand. Once the
file exists, it is an ordinary markdown file and the assistant edits it the same way it
edits source. That follows from everything endpaper writes being hand-editable: if a human
can safely open the file in any editor, so can an assistant.

The commands it does reach for are non-interactive and machine-readable. `endpaper meeting
list --json` returns structured results; `endpaper links check` reports what has gone
stale. Nothing opens an editor, nothing waits for a keypress, nothing pages output.

The two interfaces are peers. Neither is a wrapper around the other; both call the same
core library.

---

## 3. Conventions

### 3.1 Tagging

Applies to every create command. The `#tag` shorthand works inline in the TUI, where
endpaper controls the input. It cannot be relied on in the CLI, because `#` begins a
comment in bash and zsh and an unquoted tag is silently discarded by the shell before
endpaper ever sees it. Therefore:

- **TUI:** `#tag` inline, anywhere in the description. Repeatable.
- **CLI:** `--tag <tag>` is the supported form. Repeatable.
- **CLI, additionally:** if a `#tag` appears inside a *quoted* description, endpaper parses
  it out and strips it from the title, so `endpaper task add "send the report
  #procurement"` works as expected.
- A tag silently vanishing is the worst possible outcome. `endpaper --help` and `AGENTS.md`
  must both state the `--tag` form explicitly.

### 3.2 File and data layout

Frontmatter — exactly these fields, no more:

```yaml
---
id: meeting_20260728_a1b2c3d4
type: standup
title: Q3 planning
tags: [platform]
created: 2026-07-28T09:14:00
updated: 2026-07-28T09:41:00
---
```

- Ids are prefixed with their full collection name — `meeting_`, `note_`, `task_` — so a
  new collection never needs a registry of abbreviations.
- Filenames: `YYYY-MM-DD-<type>-<slug>.md`, ISO date first so lexical sort equals
  chronological sort.
- Slugs: lowercase, alphanumeric and hyphens only, truncated to 40 characters.
- Tasks are checkbox lines in `tasks.md`, metadata in a trailing HTML comment, field order
  `id`, `type`, `tags`, `links`, `created`; empty fields are omitted. An optional body is
  indented lines beneath the checkbox, after one blank line.
- **Dated files are partitioned by `YYYY/MM/` under their collection root.** The layout is:

  ```
  meetings/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
  notes/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
  notes/daily/YYYY/MM/YYYY-MM-DD.md
  tasks.md
  ```

  The partition is derived from the file's own date — the same date already in its filename and its `created` frontmatter — so a file's location is a pure function of data it already carries, and no lookup or index is needed to find or place one.

  **The full ISO date stays in the filename**, redundantly with the directory. A file that is copied, attached to an email, or dragged out of the vault must still say what it is, and lexical sort must still equal chronological sort within a directory. Filename collisions on the same day append `-2`, `-3`; the partition never disambiguates.

  Rationale: a flat collection accumulates one file per meeting and one per day forever. At a few years of daily use that is thousands of entries in a single directory — slow to open in Explorer and Finder, unpleasant to scroll, and awkward for OneDrive's per-folder sync behaviour. Partitioning was fixed before v0.0.1 shipped, specifically so it never has to be a migration. Changing this layout after users have vaults means moving their files, and moving a user's files is the one thing this tool must never need to do.

- **`type` is carried in frontmatter and in the filename only. Never as a directory.** Types are free-form and user-invented, so directory-per-type would fragment the vault into a long tail of one-file folders and complicate cross-workspace scanning. Date is the only axis the directory tree encodes, because date is the only attribute every file has exactly one of.
- **The set of collections is fixed** — `meetings/`, `notes/`, `notes/daily/`, `tasks.md` — and does not grow. Only date partitions inside them grow, and only by year and month.
- **Partitions are created on demand and never pruned.** Writing the first file of a month creates its directory; nothing creates directories in advance, and an empty partition left behind by a deleted file is harmless and is left alone.
- **Scans are recursive.** Reading a collection means walking its whole subtree, not listing one directory. A file the user has filed under the wrong month still lists — its date comes from frontmatter, never from its path. endpaper never moves a file to match its partition.
- Paths must stay well under the Windows 260-character limit — assume the root is already something like `C:\Users\name\OneDrive - Contoso Corporation\Team Notes\`. The partition adds 8 characters (`/YYYY/MM`), taking the worst-case generated path from 107 to 115 characters below the workspace root.

### 3.3 Document links

Any record may point at any other, as an ordinary CommonMark inline link: `[text](path#id)`.

```markdown
See [Q3 planning](../../../meetings/2026/07/2026-07-28-q3-planning.md#meeting_20260728_a1b2c3d4).
```

- **The `#id` fragment is authoritative and permanent.** It is what endpaper resolves against; the path is never consulted when the id resolves.
- **The path is derived, not authored.** It is the relative path from the linking file to the target, computed by endpaper and repaired whenever it goes stale — a link may be written with no path at all (`[text](#id)`), and gains the correct one on the next save.
- **Repair is a byte-level splice.** Only the destination between `(` and `)` changes; link text, surrounding prose, and line endings are untouched. A link is never rewritten by re-rendering the document.
- **A link that cannot be resolved is dead, not an error.** It is left byte-identical and reported — `endpaper links check` and `endpaper links heal` distinguish *stale* (id resolves, path wrong — mechanically fixable) from *dead* (id resolves to nothing — needs a human decision).
- **Inbound links are never stored.** `endpaper links <id>` and the preview pane's Links section answer "what points at this record" by scanning the workspace at the moment they are asked, the same way `meeting list` scans a collection. No index, no cache, no back-reference written into any target.
- Text inside a fenced code block or an inline code span is never treated as a link — a note that documents link syntax is not rewritten.
- A task may carry links too, via the `links:` field on its checkbox line — bare ids, never paths, since a task line is already one line of metadata.

### 3.4 The CLI contract

The CLI is what an assistant drives to create records and read structured output, and it
must never behave like an interactive program.

- **Never opens an editor.** No `$EDITOR`, no `subprocess` to vim, ever.
- **Never blocks on input.** No prompts, no confirmations, no pagers. Destructive
  operations take an explicit flag instead of asking.
- **Never colorizes or decorates when stdout is not a TTY.**
- `--json` is available on every read command and emits a stable, documented schema. Adding
  a key is a minor change; renaming or removing one is breaking.
- Errors go to stderr; data goes to stdout. An assistant piping stdout must never receive
  an error message as data. Exit codes are meaningful — see §4.1.

### 3.5 AGENTS.md

- Generated at `init` at the workspace root.
- Carries what §4.2 lists, and nothing an assistant could infer from the workspace itself.
  It does not restate the README.
- That content rule is what binds; roughly 100 lines is its checkable backstop, not a
  budget to be spent. Short, human-curated, genuinely non-obvious guidance is what helps an
  assistant, and a bloated file measurably raises exploration cost. A real instruction that
  pushes the file past the cap means the whole file gets reviewed for content that has
  stopped earning its place — never that the instruction is dropped to fit under a number.

### 3.6 Search

**There is no index and no database.** The markdown files are the only state endpaper has.

- On launch, `core` globs the workspace recursively, walking the `YYYY/MM/` partitions
  described in §3.2, parses frontmatter from each file, and holds the result in memory as a
  list of records.
- The TUI's live filter operates on that in-memory list. No disk access per keystroke.
- On save, re-read and re-parse only the file that changed.
- There is no `reindex` command, because there is nothing to rebuild. Deleting nothing and
  corrupting nothing are properties, not features.

Semantic search is out of scope. AI assistants perform semantic retrieval by searching,
reading, and refining against the live filesystem — the agentic-search pattern — and never
touch endpaper's search path at all.

**Revisit only if** startup scan time becomes noticeable in practice. The first remedy is a
small JSON metadata cache keyed by file mtime, not a database.

### 3.7 Terminal reality and key bindings

- **`ctrl+o` (save) and `ctrl+x` (save and exit) are chosen for nano compatibility.** nano
  is the terminal editor the target user is most likely to have encountered, and neither
  key collides with terminal flow control or Textual's defaults.
- **`ctrl+s` is XOFF.** On terminals with legacy flow control it freezes output rather than
  reaching the app. Textual normally disables flow control on entering raw mode, so it
  usually works — but "usually" is not a guarantee to build a save key on. It is bound as
  an alias only; `ctrl+o` is what the footer advertises. Document `stty -ixon` as the
  fallback.
- **`ctrl+q` is XON and Textual's conventional quit binding.** Do not bind it to anything.
  Leaving it as quit avoids surprising users who expect it to exit.
- **`ctrl+c` is reserved by Textual.** Do not rebind.
- **Cmd is not deliverable to a terminal app on macOS.** Terminal emulators intercept
  `cmd+s` and `cmd+q` before the TUI sees them. `ctrl` is the only portable modifier; never
  promise a Cmd binding in the UI or docs.

---

## 4. Registries

The constitution states the rule for each of these; the contents live here, because they
change as features ship rather than by amendment.

### 4.1 Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | not found |
| `2` | usage error |
| `3` | workspace error |

Renaming or removing a code is a breaking change. Adding one is not.

### 4.2 What AGENTS.md carries

The folder layout; the frontmatter schema and id prefixes; the task line format and its
optional body; link syntax; the commands an assistant reaches for; the `--tag` rule from
§3.1; and the exit codes from §4.1 with their stream separation.

### 4.3 Target terminals

TUI changes are verified on these before release: Windows Terminal, iTerm2, macOS Terminal,
PuTTY, and inside tmux.

---

## 5. Held in the constitution

Two areas that were once described here are stated once, in
`.specify/memory/constitution.md`, rather than twice:

- **Architecture** — `endpaper.core` holds all logic, the CLI and TUI are peers over it,
  and core is testable without a terminal. Principle I, and Principle II for the peer rule.
- **Platform and environment** — supported operating systems, no admin rights, no network,
  Windows path limits, spaces and non-ASCII in paths, per-user state. The Platform &
  Distribution Constraints section.
