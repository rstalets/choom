# endpaper

```
╔══════════════════════╗
║░░░░░░░░░░░░░░░░░░░░░░║
║░┌──────────────────┐░║
║░│ [x] standup      │░║
║░│ [ ] follow-up    │░║
║░│ #platform        │░║
║░└──────────────────┘░║
║░░░░░░░░░░░░░░░░░░░░░░║
╚══════════════════════╝
```

A local-only, terminal-based tool for capturing and organizing meeting notes, general notes, and tasks as plain markdown files — structured enough for a human to navigate through a TUI, and legible enough that an AI assistant can search and edit the vault through a CLI without any integration work.

## Why

Markdown is the native format of AI assistants — they read it, write it, diff it, and reason over it without an adapter layer. Almost nobody at a large company can actually work that way, because the sanctioned note-taking tools (OneNote, Confluence, SharePoint) lock notes behind proprietary formats and authenticated APIs, and markdown-first apps like Obsidian or Logseq are rarely on the approved-software list.

endpaper installs without admin rights, stores nothing outside a directory you already have, and works inside a OneDrive-synced folder so a team can share a workspace without a server.

## Features (v0.0.1)

- **Meeting notes** — `/meeting.standup Q3 planning #platform` creates a dated, frontmatter-tagged file and drops you straight into it. Browse with `/meetings`, filter live, open with `enter`.
- **General notes** — `/note` opens (or creates) today's daily note; `/note.research vendor landscape #procurement` creates a typed note. Browse with `/notes`.
- **Tasks** — `/task.followup send the vendor comparison #procurement` appends a checkbox line to `tasks.md`. `/tasks` lists open items; `space` toggles done. The file stays hand-editable plain markdown — no database.
- **Workspaces** — `endpaper init` sets up a single workspace; `endpaper init <name>` creates a named workspace in a shared root (e.g. a OneDrive folder), so each team member gets their own directory while search and browsing span the whole root.
- **View and edit** — every note or meeting opens in a rendered markdown preview (`enter`), switches to a raw editor (`e`) with line numbers and soft wrap, and saves with `ctrl+o` (stay) or `ctrl+x` (save and return). `esc` discards, but only prompts when there's something to lose.
- **AI-friendly CLI** — every TUI action has a non-interactive CLI equivalent backed by the same core library: `endpaper find`, `read`, `write`, `append`, `--json` on every read command, meaningful exit codes, nothing that opens an editor or blocks on input.
- **No index, no database** — the markdown files are the only state. endpaper globs and parses the workspace in memory on launch; nothing to corrupt, nothing to reindex.
- **`AGENTS.md`** — generated at `init`, under ~60 lines, so an assistant landing in the workspace is productive immediately.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the full v0.0.1 specification, including CLI syntax, frontmatter schema, and acceptance criteria.

## Status

Draft / pre-release. v0.0.1 targets Python 3.11+, installable via `uv tool install` or `pipx`, on Windows, macOS, and Linux with no network access required.

## License

See [LICENSE](LICENSE).
