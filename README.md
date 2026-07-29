# endpaper

A corporate-friendly Markdown notes engine that makes your AI happy.

endpaper stores meeting notes as plain Markdown files with YAML frontmatter in a workspace
directory you control — no database, no server, no lock-in. Capture a note in one command from
the CLI or a two-pane terminal UI, and find it again by type, tag, or date. Every command is safe
to drive from a script or an AI assistant: stable JSON output, predictable exit codes, and nothing
that blocks on a keypress.

## Install

```bash
uv tool install endpaper
```

## Quickstart

```bash
endpaper init                                        # create a workspace here
endpaper meeting new "Q3 planning" --type standup --tag platform
endpaper meeting list --json
endpaper                                              # open the TUI
```

See `AGENTS.md` in a workspace for the full command reference, or the `endpaper --help` output.
