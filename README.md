# endpaper

```
⠀⠀⠀⠀⠀⠀⠀⠀⣀⣀⣤⣤⣤⣤⣤⣄⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢀⣠⣶⣾⡿⠿⢛⣛⣛⣛⡛⠻⠿⣿⣷⣦⡀⠀⠀⠀⠀⠀
⠀⠀⢀⣴⣿⡿⠛⠁⠀⣴⣿⣿⣿⣿⣿⣷⡄⠀⠉⠻⣿⣷⡀⠀⠀⠀
⠀⢀⣾⡿⠋⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⡧⠀⠀⠀⠈⠻⣿⣦⠀⠀
⢀⣿⡿⢁⣠⣤⣤⣤⣈⢿⣿⣿⣿⣿⣿⣿⠇⣠⣤⣤⣤⣀⠹⣿⣧⠀
⣼⣿⢳⣿⣿⣿⣿⣿⣿⣧⠙⢻⣿⣿⠛⢡⣾⣿⣿⣿⣿⣿⣷⣻⣿⡀
⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⢸⣿⣿⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇
⣿⣿⠘⣿⣿⣿⣿⣿⣿⣿⡀⢸⣿⣿⠀⣸⣿⣿⣿⣿⣿⣿⡿⢹⣿⡇
⢿⣿⡄⠈⠙⠛⠟⠛⠙⢿⣿⣾⣿⣿⣾⣿⠟⠙⠛⠟⠛⠉⠀⣸⣿⠁
⠈⣿⣷⡀⠀⠀⠀⠀⠀⠀⠙⢿⣿⣿⡟⠃⠀⠀⠀⠀⠀⠀⣰⣿⡟⠀
⠀⠘⢿⣷⣄⠀⠀⠀⠀⠀⠀⢸⣿⣿⠀⠀⠀⠀⠀⠀⢀⣴⣿⠟⠀⠀
⠀⠀⠈⠻⣿⣷⣄⡀⠀⠀⠀⢸⣿⣿⠀⠀⠀⠀⢀⣴⣿⡿⠃⠀⠀⠀
⠀⠀⠀⠀⠈⠙⠿⣿⣷⣶⣤⣼⣛⣻⣤⣤⣶⣾⡿⠟⠋⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠛⠛⠛⠛⠛⠛⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀
KEEP YOUR CORPO OVERLORDS HAPPY, FEED YOUR AI
```

**A corporate-friendly Markdown notes engine that makes your AI happy.**

A local-only, terminal-based tool for capturing and organizing meeting notes, general notes, and tasks as plain markdown files — structured enough for a human to navigate through a TUI, and legible enough that an AI assistant can search and edit the vault through a CLI without any integration work.

## Why

Markdown is the native format of AI assistants — they read it, write it, diff it, and reason over it without an adapter layer. Almost nobody at a large company can actually work that way, because the sanctioned note-taking tools (OneNote, Confluence, SharePoint) lock notes behind proprietary formats and authenticated APIs, and markdown-first apps like Obsidian or Logseq are rarely on the approved-software list.

endpaper installs without admin rights, stores nothing outside a directory you already have, and needs no server or account — just a folder.

The tool disappears into the twenty seconds before a meeting starts. You type `/meeting.standup Q3 planning #platform`, a file exists with correct frontmatter and a date-stamped name, and you're typing notes before anyone has finished joining the call. You never decide where a file goes or what to call it.

## Usage

> Screenshots coming soon — `docs/screenshots/tui-list.png` and `docs/screenshots/tui-preview.png` are referenced below and will render once added.

### Install

```bash
uv tool install endpaper
```

### Create a workspace

```bash
mkdir notes && cd notes
endpaper init
```

This creates `.endpaper/config.toml`, `AGENTS.md`, and `meetings/` in the current directory. This directory is now your workspace root — every command below runs from inside it.

### Capture a meeting

```bash
endpaper meeting new "Q3 planning" --type standup --tag platform
```

Prints the path to the new file: `meetings/2026-07-28-standup-q3-planning.md`, already stamped with frontmatter (`id`, `type`, `title`, `tags`, `created`, `updated`).

### Browse and list

```bash
endpaper meeting list --json
endpaper meeting list --type standup --since 2026-07-01
```

Or launch the TUI with no arguments:

```bash
endpaper
```

![TUI list view](docs/screenshots/tui-list.png)

`/` opens a combined filter/command bar — type to filter the list live, or type `meeting.standup <description>` and hit `enter` to create one without leaving the screen. Arrow keys move, `enter` opens the selected meeting in a rendered markdown preview, `e` drops into a raw editor, `ctrl+o`/`ctrl+x` save, `esc` backs out.

![TUI preview and edit](docs/screenshots/tui-preview.png)

### For AI assistants

An assistant working in an endpaper workspace reads `AGENTS.md` at the root and takes it from there — non-interactive, `--json`-capable, and scriptable by design. Nothing opens an editor or blocks on a prompt.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full CLI reference, frontmatter schema, and exit codes.

## Features (v0.0.1)

- **Meeting notes** — `/meeting.standup Q3 planning #platform` creates a dated, frontmatter-tagged file and drops you straight into it. Browse with `/meetings`, filter live, open with `enter`.
- **General notes** — `/note` opens (or creates) today's daily note; `/note.research vendor landscape #procurement` creates a typed note. Browse with `/notes`.
- **Tasks** — `/task.followup send the vendor comparison #procurement` appends a checkbox line to `tasks.md`. `/tasks` lists open items; `space` toggles done. The file stays hand-editable plain markdown — no database.
- **Workspace init** — `endpaper init` sets up a workspace (config, `AGENTS.md`, `meetings/`, `notes/daily/`, `tasks.md`) in the current directory. Multi-user shared workspaces are planned but not in v0.0.1 — see [Roadmap](#roadmap).
- **View and edit** — every note or meeting opens in a rendered markdown preview (`enter`), switches to a raw editor (`e`) with line numbers and soft wrap, and saves with `ctrl+o` (stay) or `ctrl+x` (save and return). `esc` discards, but only prompts when there's something to lose.
- **AI-friendly CLI** — every TUI action has a non-interactive CLI equivalent backed by the same core library: `endpaper find`, `read`, `write`, `append`, `--json` on every read command, meaningful exit codes, nothing that opens an editor or blocks on input.
- **No index, no database** — the markdown files are the only state. endpaper globs and parses the workspace in memory on launch; nothing to corrupt, nothing to reindex.
- **`AGENTS.md`** — generated at `init`, under ~60 lines, so an assistant landing in the workspace is productive immediately.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full v0.0.1 specification, including CLI syntax, frontmatter schema, and acceptance criteria. Not everything above has landed on `main` yet — check [CHANGELOG.md](CHANGELOG.md) for what's actually shipped so far.

## Roadmap

Planned for a future release, tracked in [REQUIREMENTS.md §6](REQUIREMENTS.md#6-backlog--future):

- **Multi-user shared workspaces** — `endpaper init <name>` inside a shared root (e.g. a OneDrive folder), `/workspace` switching, and cross-workspace search, so a team can share one root without a server.

Considered and explicitly out of scope for v0.0.1 (see [REQUIREMENTS.md §5](REQUIREMENTS.md#5-explicitly-out-of-scope-for-v001)):

- AI invocation from inside endpaper (`/claude` markers, SDK integration)
- Webcam or image capture (`/pic`)
- Embeddings, vector search, semantic retrieval
- Tasks created inline from inside a note or meeting
- Backlinks, wikilinks, graph views
- Syntax highlighting in the editor

## Status

Draft / pre-release. v0.0.1 targets Python 3.11+, installable via `uv tool install` or `pipx`, on Windows, macOS, and Linux with no network access required.

## License

See [LICENSE](LICENSE).
