# endpaper — Requirements v0.0.1

**Status:** Draft
**Date:** 2026-07-28
**Command name:** `endpaper`

---

## 1. Problem statement

Markdown is the native format of AI assistants. Agents read it, write it, diff it, and reason over it without any adapter layer. A person whose working notes live in plain markdown files can hand their entire context to Claude, Copilot, or any other assistant for free.

Almost nobody at a large company can do this. Markdown-first tools — Obsidian, Logseq, Foam — are rarely on the approved-software list, and the sanctioned alternatives (OneNote, Confluence, SharePoint) store notes in proprietary formats behind authenticated APIs. The result is that the people with the most meetings, the most decisions to track, and the most to gain from an AI assistant that knows their context are precisely the people whose context is locked in a format their assistant can't reach.

The workarounds fail in predictable ways. Copy-pasting into a chat window loses everything the moment the session ends. Personal markdown folders become unnavigable within weeks because nothing enforces structure or provides search. Full note-taking apps demand installation rights, a server, or a cloud account.

**endpaper is a local-only, Python, terminal-based tool for capturing and organizing meeting notes, general notes, and tasks as plain markdown files** — structured enough for a human to navigate through a TUI, and legible enough that an AI assistant can search and edit the vault through a CLI without any integration work. It installs without admin rights, stores nothing outside a directory the user already has, and works on a OneDrive-synced folder so a team can share a workspace without a server.

---

## 2. Desired user experience

### The human

The tool disappears into the twenty seconds before a meeting starts. You type `/meeting.standup Q3 planning #platform`, a file exists with correct frontmatter and a date-stamped name, and you're typing notes before anyone has finished joining the call. You never decide where a file goes or what to call it.

Later you type `/meetings`, arrow down a list, and hit enter. The note opens rendered as formatted markdown, because reading it is what you came to do. You press `e` and you're editing the raw file. `ctrl+o` saves, `ctrl+x` saves and drops you back to the rendered view, and escape backs out without saving — asking first, but only if you'd actually lose something.

Tasks work the same way: `/task.followup send the vendor comparison #procurement` to capture, `/tasks` to see the list, arrows to move, space to complete. No project hierarchy, no due-date syntax, no priority scheme.

The whole surface is a filterable list and a preview pane. There is exactly one screen.

### The AI assistant

An assistant that lands in an endpaper workspace should be productive without instruction. It reads `AGENTS.md` at the root, learns the folder layout and the four commands that matter, and works from there.

Every command it needs is non-interactive and machine-readable. `endpaper find "vendor renewal" --json` returns structured results. `endpaper read <id>` dumps raw markdown to stdout. `endpaper write <id>` accepts new content on stdin. Nothing opens an editor, nothing waits for a keypress, nothing pages output. The assistant searches, reads, refines, and writes — the same loop it already runs against a codebase.

The two interfaces are peers. Neither is a wrapper around the other; both call the same core library.

### The shared workspace

A team lead runs `endpaper init platform-team` inside a OneDrive folder. Each member runs `endpaper init <their-name>` in the same place. Everyone gets their own directory of markdown files, everyone can read everyone else's, and search spans the whole root. No server, no account, no sync logic in endpaper — OneDrive syncs files, and files are the only shared state.

---

## 3. Features for v0.0.1

Command syntax below is given in TUI form (`/meeting.standup ...`). Every TUI command has a CLI equivalent (`endpaper meeting new ...`) backed by the same core function. Both are listed per feature.

**Tagging rule — applies to every create command.** The `#tag` shorthand works inline in the TUI, where endpaper controls the input. It cannot be relied on in the CLI, because `#` begins a comment in bash and zsh and an unquoted tag is silently discarded by the shell before endpaper ever sees it. Therefore:

- **TUI:** `#tag` inline, anywhere in the description. Repeatable.
- **CLI:** `--tag <tag>` is the supported form. Repeatable.
- **CLI, additionally:** if a `#tag` appears inside a *quoted* description, endpaper parses it out and strips it from the title, so `endpaper task add "send the report #procurement"` works as expected.
- A tag silently vanishing is the worst possible outcome. `endpaper --help` and `AGENTS.md` must both state the `--tag` form explicitly.

### 3.1 Meeting notes

**Create**

```
TUI:  /meeting.<type> <description> #<tag>
CLI:  endpaper meeting new <description> --type <type> --tag <tag>
```

- `<type>` is a free-form string (`standup`, `1on1`, `vendor`, `retro`). Optional; omitting the dot suffix creates an untyped meeting.
- `<description>` is free text, used for the title and slugified into the filename.
- `#<tag>` is optional and repeatable.
- File is created at `meetings/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md` with frontmatter, then opened for editing immediately (TUI) or its path printed to stdout (CLI). The `YYYY/MM/` partition is created on demand; see §4.6.
- Filename collisions on the same day append `-2`, `-3`.

**Browse**

```
TUI:  /meetings
CLI:  endpaper meeting list [--json] [--tag <tag>] [--type <type>] [--since <date>]
```

- TUI shows a list sorted by date descending: date, type, title, tags.
- Up/down or `j`/`k` to move.
- `/` opens a single input that is both the filter and the command line. Its first token decides: if the part before any `.` is a registered command verb (`meeting`, `meetings`, `init`, and later `note`, `task`, `workspace`), the input is a command and runs on `enter`; otherwise every keystroke filters the list live. The footer shows the resolved mode — `[filter]` or `[command: meeting.standup]` — as the user types, and a leading space forces filter mode.
- One key, not two. `/` is specified both as the filter key here and as the prefix of `/meeting.<type>` above, so it must do both. Filtering is live while commands require `enter`, which means a mis-read command never acts without a confirming keystroke.
- `enter` opens the selected meeting — see §3.5 for view and edit behaviour.

**Acceptance criteria**

1. `/meeting.standup Q3 planning #platform` creates exactly one file with `type: standup`, `tags: [platform]`, today's date, and title "Q3 planning".
2. `endpaper meeting new "Q3 planning" --type standup --tag platform` produces a file identical to (1) in every field except `id`, `created`, and `updated`, and prints its path. Those three are generated per invocation, so byte-equality across two separate runs is not achievable; what is required — and what the test asserts — is that both front doors call the same core function and neither has behaviour the other lacks.
3. `endpaper meeting list --json` emits an array of objects with stable keys: `id`, `path`, `title`, `type`, `tags`, `created`, `updated`.
4. Creating two meetings with the same description on the same day yields two distinct files, neither overwritten.

### 3.2 General notes

**Create — daily note**

```
TUI:  /note
CLI:  endpaper note today
```

- Creates `notes/daily/YYYY/MM/YYYY-MM-DD.md` if it does not exist; opens the existing file if it does. Never creates a second file for the same day — uniqueness is per date, not per directory, so a stray copy of the same date under a different partition is a duplicate and must not be created.

**Create — typed note**

```
TUI:  /note.<type> <description> #<tag>
CLI:  endpaper note new <description> --type <type> --tag <tag>
```

- Same semantics as meetings. File at `notes/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md`.
- Intended for idea documents, research notes, drafts, reference material.

**Browse**

```
TUI:  /notes
CLI:  endpaper note list [--json] [--tag] [--type] [--since]
```

- Same list behaviour as `/meetings`; `enter` opens per §3.5. Daily notes appear in the list alongside typed notes, distinguished by `type: daily`.

**Acceptance criteria**

1. `/note` on a day with no daily note creates one; running it again the same day opens the same file and does not modify its content.
2. `/note.research vendor landscape #procurement` creates a typed note with `type: research`.
3. Daily and typed notes both appear in `/notes` and in `endpaper note list --json`.

### 3.3 Tasks

**Create**

```
TUI:  /task.<type> <description> #<tag>
CLI:  endpaper task add <description> --type <type> --tag <tag>
```

- A task may optionally name the records it came from via a `links:` field (see 4.6.1) —
  comma-separated ids, never paths, since the id prefix already says which collection to look in.
- Stored as markdown checkboxes in a single file, `tasks.md`, one per line:
  `- [ ] send the vendor comparison <!-- id:task_a1b2 type:followup tags:procurement links:meeting_20260728_a1b2c3d4 created:2026-07-28 -->`
- The HTML comment carries metadata without breaking rendering in any markdown viewer. Field
  order is `id`, `type`, `tags`, `links`, `created`; empty fields are omitted, so a task with no
  links renders exactly as it did before this field existed.
- **The parser must tolerate hand-editing of `tasks.md`.** Users will edit this file directly, in endpaper and elsewhere. Therefore:
  - A checkbox line with no id comment is valid. On scan, generate an id and write it back.
  - A line with a malformed or partial comment is skipped, not fatal. Log it and continue parsing the rest of the file.
  - A parse failure must never lose a line or truncate the file.

**Manage**

```
TUI:  /tasks
CLI:  endpaper task list [--json] [--all] [--tag] [--type]
      endpaper task done <id>
      endpaper task undone <id>
```

- TUI shows open tasks by default, sorted by creation date.
- Up/down (or `j`/`k`) to navigate; `space` toggles complete and rewrites the line in `tasks.md` immediately.
- `a` shows completed tasks as well, rendered struck through.

**Acceptance criteria**

1. `space` on a task in the TUI changes `- [ ]` to `- [x]` in `tasks.md` within one second, preserving the id comment.
2. `endpaper task done task_a1b2` produces the identical file change.
3. `tasks.md` remains valid CommonMark and renders as a checklist in any markdown viewer.
4. The task parser reads checkboxes by scanning markdown, not by reading a database — so that v0.1 can extend it to any file without a migration.
5. A hand-written line `- [ ] buy milk` with no id comment is picked up on the next scan and given an id, in place, without disturbing surrounding lines.
6. A line with a broken comment (`- [ ] thing <!-- id:`) is skipped without raising, and every other task in the file still parses.

### 3.4 File organization and workspaces

**Single workspace**

```
TUI:  /init
CLI:  endpaper init
```

- Run in an empty (or endpaper-free) directory. Creates:
  ```
  .endpaper/config.toml
  AGENTS.md
  meetings/
  notes/daily/
  tasks.md
  ```
- Only the four collection roots are created at init. Date partitions (`meetings/YYYY/MM/`) are created on demand by the first file written into them, so a fresh workspace has no empty year directories.
- This directory is now the workspace and the root.

**Acceptance criteria**

1. `endpaper init` in an empty directory creates all five paths above and exits 0.
2. Running `endpaper init` in a directory that is already a workspace exits non-zero with a clear message and changes nothing.

> Named workspaces in a shared root, workspace switching, and cross-workspace visibility are deferred — see [§6 Backlog / future](#6-backlog--future).

### 3.5 Viewing and editing (meetings and notes)

Applies identically to anything opened from `/meetings` or `/notes`. There are exactly three states: **list → preview → edit**, and every transition is one keystroke.

**Preview state**

- `enter` on a list row opens the file in a full-screen **Markdown preview**. This is the default view for any existing note or meeting — reading is the common case, editing is the exception.
- Rendered, not raw: headings, lists, tables, checkboxes, emphasis.
- `e` enters edit state.
- `esc` returns to the list.

**Edit state**

- Textual's built-in `TextArea` widget, containing the raw markdown including frontmatter.
- **Line numbers are shown in the gutter on the left**, for the whole buffer including frontmatter — so line 1 is the opening `---`.
- Soft wrapping stays **on**, since this is prose rather than code. Wrapped continuation rows show no number in the gutter; only real lines are numbered.

| Key | Action |
|---|---|
| `ctrl+o` | Save, stay in edit state |
| `ctrl+x` | Save and return to preview state |
| `esc` | Return to preview state, discarding changes |

- `ctrl+s` is bound as an additional alias for save. Muscle memory for it is near-universal, and binding both costs nothing. `ctrl+o` is the canonical binding shown in the footer, because `ctrl+s` cannot be guaranteed to arrive (see §4.5).
- The footer displays the active bindings at all times. No hidden keys.
- **`esc` prompts only when the buffer differs from the file on disk.** With no unsaved changes it returns to preview immediately and silently. A confirmation that fires when there is nothing to lose teaches users to dismiss it reflexively, which disarms it for the one time it matters.
- When it does fire, the prompt is a modal dialog — *"Discard unsaved changes?"* with Discard and Cancel. Cancel returns to edit with the buffer intact.
- On save: write to disk, update `updated` in frontmatter, re-parse the file into the in-memory list.
- The preview state must reflect saved changes on return.

**Acceptance criteria**

1. `enter` on a list row shows rendered markdown, not raw source.
2. `e` then typing then `ctrl+o` writes to disk; the file on disk matches the buffer. `ctrl+s` does the same.
3. `e` then typing then `esc` shows a confirmation; choosing Cancel preserves every keystroke; choosing Discard leaves the file on disk byte-identical to before editing.
4. `e` then no changes then `esc` returns to preview with no dialog. This holds after a save too — saving clears the dirty state, so `ctrl+o` followed by `esc` never prompts.
5. `ctrl+x` saves and lands in preview showing the new content.
6. `updated` in frontmatter changes on save; `created` never does.
7. Every binding in the table is visible in the footer while in edit state.
8. Edit state shows line numbers in the left gutter, starting at 1 on the opening `---` of the frontmatter. Long lines wrap rather than scrolling horizontally.

---

## 4. Non-functional requirements

### 4.1 Architecture

- **Python.** Target 3.11+. Installable via `uv tool install` / `pipx` with no admin rights.
- **`endpaper.core` holds all logic.** Vault resolution, frontmatter parsing, file creation, markdown scanning, search, task toggling. No I/O formatting, no widget code, no argument parsing.
- **The CLI and the TUI are peers.** Both are thin adapters over `core`. Neither shells out to the other. Any behaviour available in one must be available in the other unless it is inherently interactive (live filtering) or inherently non-interactive (stdin piping).
- Core functions must be callable and testable without a terminal.

### 4.2 CLI must be AI-friendly

This is a hard requirement, not a preference. The CLI is the assistant's only interface.

- **Never opens an editor.** No `$EDITOR`, no `subprocess` to vim, ever.
- **Never blocks on input.** No prompts, no confirmations, no pagers. Destructive operations take an explicit flag instead of asking.
- **Never colorizes or decorates when stdout is not a TTY.**
- `endpaper read <id|path>` dumps raw file contents to stdout, unmodified.
- `endpaper write <id|path>` reads replacement content from stdin and overwrites the file.
- `endpaper append <id|path>` reads from stdin and appends.
- `--json` is available on every read command and emits a stable, documented schema.
- Exit codes are meaningful: 0 success, 1 not found, 2 usage error, 3 workspace error.
- Errors go to stderr; data goes to stdout. An assistant piping stdout must never receive an error message as data.

### 4.3 AGENTS.md

- Generated at `init` at the workspace root.
- Contains: folder layout, frontmatter schema, the task line format, and the six commands an assistant should reach for. Nothing else.
- **Content is the rule; the line count is its backstop.** Carry nothing an assistant could infer from the workspace itself. Do not restate the README. Do not explain what markdown is. Research on context files is clear that short, human-curated, genuinely non-obvious content helps and that bloated files measurably increase exploration cost and can degrade performance. Roughly 100 lines is the checkable form of that rule, not a budget to fill: a genuine instruction that pushes the file over the cap triggers a review of the whole file for content that has stopped earning its place, never the deletion of whatever was added last.

### 4.4 Search

**There is no index and no database.** The markdown files are the only state endpaper has.

- On launch, `core` globs the workspace recursively (or the root, when scope is widened), walking the `YYYY/MM/` partitions described in §4.6, parses frontmatter from each file, and holds the result in memory as a list of records.
- The TUI's live filter operates on that in-memory list. No disk access per keystroke.
- On save, re-read and re-parse only the file that changed.
- `endpaper find <query>` performs a plain substring scan over titles, tags, and file bodies in pure Python. No `ripgrep` or other external binary dependency — it cannot be assumed installable on a locked-down machine.
- There is no `reindex` command, because there is nothing to rebuild. Deleting nothing and corrupting nothing are properties, not features.

Rationale: at the target scale — on the order of hundreds to low thousands of files — a full scan costs a fraction of a second at launch, which is cheaper than the invalidation logic, staleness bugs, and cache-corruption risk an index would introduce. A SQLite file inside a OneDrive-synced folder is a genuine corruption hazard; the simplest way to avoid it is to not have one.

Semantic search is out of scope. AI assistants perform semantic retrieval by searching, reading, and refining against the live filesystem — the agentic-search pattern — and never touch endpaper's search path at all.

**Revisit only if** startup scan time becomes noticeable in practice. The first remedy is a small JSON metadata cache keyed by file mtime, not a database.

### 4.5 TUI

- **Textual.** Three states — list, Markdown preview, edit — as specified in §3.5.
- **Editing uses Textual's built-in `TextArea` widget.** No embedded nvim, no external editor, no custom editor implementation in v0.0.1.
- Configure it with `show_line_numbers=True` and soft wrapping left enabled. **Do not use the `TextArea.code_editor()` convenience constructor** — it turns line numbers on but also disables soft wrapping and makes tab insert a literal `\t`, both wrong for prose. Set the options explicitly instead.
- Tasks navigate with up/down arrows; `space` marks complete.
- Saves write to disk and re-parse only the changed file into the in-memory list.

**Key-binding rationale and hazards:**

- **`ctrl+o` (save) and `ctrl+x` (save and exit) are chosen for nano compatibility.** nano is the terminal editor the target user is most likely to have encountered, and neither key collides with terminal flow control or Textual's defaults.
- **`ctrl+s` is XOFF.** On terminals with legacy flow control it freezes output rather than reaching the app. Textual normally disables flow control on entering raw mode, so it usually works — but "usually" is not a guarantee to build a save key on. It is bound as an alias only; `ctrl+o` is what the footer advertises. Document `stty -ixon` as the fallback.
- **`ctrl+q` is XON and Textual's conventional quit binding.** Do not bind it to anything. Leaving it as quit avoids surprising users who expect it to exit.
- **`ctrl+c` is reserved by Textual.** Do not rebind.
- **Cmd is not deliverable to a terminal app on macOS.** Terminal emulators intercept `cmd+s` and `cmd+q` before the TUI sees them. `ctrl` is the only portable modifier; never promise a Cmd binding in the UI or docs.
- **Verify on the target terminals** before release: Windows Terminal, iTerm2, macOS Terminal, PuTTY, and inside tmux.

### 4.6 Data conventions

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

- Filenames: `YYYY-MM-DD-<type>-<slug>.md`, ISO date first so lexical sort equals chronological sort.
- Slugs: lowercase, alphanumeric and hyphens only, truncated to 40 characters.
- **Dated files are partitioned by `YYYY/MM/` under their collection root.** The layout is:

  ```
  meetings/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
  notes/YYYY/MM/YYYY-MM-DD-<type>-<slug>.md
  notes/daily/YYYY/MM/YYYY-MM-DD.md
  tasks.md
  ```

  The partition is derived from the file's own date — the same date already in its filename and its `created` frontmatter — so a file's location is a pure function of data it already carries, and no lookup or index is needed to find or place one.

  **The full ISO date stays in the filename**, redundantly with the directory. A file that is copied, attached to an email, or dragged out of the vault must still say what it is, and lexical sort must still equal chronological sort within a directory. Filename collisions on the same day append `-2`, `-3` as before; the partition never disambiguates.

  Rationale: a flat collection accumulates one file per meeting and one per day forever. At a few years of daily use that is thousands of entries in a single directory — slow to open in Explorer and Finder, unpleasant to scroll, and awkward for OneDrive's per-folder sync behaviour. Partitioning is stated here, before v0.0.1 ships, specifically so it never has to be a migration. Changing this layout after users have vaults means moving their files, and moving a user's files is the one thing this tool must never need to do.

- **`type` is carried in frontmatter and in the filename only. Never as a directory.** Types are free-form and user-invented, so directory-per-type would fragment the vault into a long tail of one-file folders and complicate cross-workspace scanning. Date is the only axis the directory tree encodes, because date is the only attribute every file has exactly one of.
- **The set of collections is fixed** — `meetings/`, `notes/`, `notes/daily/`, `tasks.md` — and does not grow. Only date partitions inside them grow, and only by year and month.
- **Partitions are created on demand and never pruned.** Writing the first file of a month creates its directory; nothing creates directories in advance, and an empty partition left behind by a deleted file is harmless and is left alone.
- **Scans are recursive.** Reading a collection means walking its whole subtree, not listing one directory. A file the user has filed under the wrong month still lists — its date comes from frontmatter, never from its path. endpaper never moves a file to match its partition.
- Paths must stay well under the Windows 260-character limit — assume the root is already something like `C:\Users\name\OneDrive - Contoso Corporation\Team Notes\`. The partition adds 8 characters (`/YYYY/MM`), taking the worst-case generated path from 107 to 115 characters below the workspace root.

#### 4.6.1 Document links

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
- A task may carry links too, via the `links:` field on its checkbox line (3.3) — bare ids, never paths, since a task line is already one line of metadata.

### 4.7 Platform and environment

- Windows, macOS, Linux. Windows is a first-class target — the primary user is a corporate employee.
- No network access required for any operation.
- No admin rights required to install or run.
- Handles spaces and non-ASCII characters in workspace paths.

---

## 5. Explicitly out of scope for v0.0.1

AI invocation from inside endpaper and configuration beyond workspace paths shipped in v0.0.2
(`/ai <prompt>`, `endpaper config assistant`) — see [CHANGELOG.md](CHANGELOG.md).

- Webcam or image capture (`/pic`)
- Embeddings, vector search, semantic retrieval
- Tasks created inside a note or meeting (`/task` while editing)
- Backlinks, wikilinks, graph views
- Syntax highlighting in the editor
- Conflict resolution for simultaneous edits — OneDrive's own conflict-copy behaviour is the answer
- MCP server

---

## 6. Backlog / future

### 6.1 Multi-user shared workspaces

De-scoped from v0.0.1 (originally part of §3.4). The single-workspace `endpaper init` remains in v0.0.1 scope; the shared-root/multi-workspace features below do not.

**Named workspace in a shared root**

```
TUI:  /init <name>
CLI:  endpaper init <name>
```

- Creates `<name>/` in the current directory with the structure above.
- If a root workspace file (`.endpaper/root.toml`) exists in the current directory, adds `<name>` to it. If not, creates one.
- Intended use: a OneDrive or shared-drive folder where each team member has their own workspace directory.

**Switching**

```
TUI:  /workspace
CLI:  endpaper workspace list [--json]
      endpaper workspace use <name>
      endpaper workspace current
```

- `/workspace` presents the workspaces listed in the root file and sets the current one on selection.
- The current workspace persists across sessions until changed.
- **The current-workspace setting is stored in per-user local state, not in the workspace directory** — otherwise two people sharing a OneDrive folder would overwrite each other's selection.

**Cross-workspace visibility**

- `/meetings`, `/notes`, and search operate on the current workspace by default.
- `--all` (CLI) and a scope toggle (`tab` in the TUI) widen to every workspace in the root.
- All workspaces are readable. v0.0.1 does not prevent writing to another member's workspace; it simply doesn't provide a command that does.

**Acceptance criteria**

1. `endpaper init alice` followed by `endpaper init bob` in the same directory produces two workspace directories and one root file listing both.
2. `endpaper workspace use bob`, then a new shell, then `endpaper workspace current` prints `bob`.
3. Running `endpaper init <name>` from inside an existing workspace exits non-zero with a message naming the root directory where it should be run instead. Workspaces do not nest.
