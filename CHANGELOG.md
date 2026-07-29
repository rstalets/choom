# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### 0.0.1

Initial release: workspace scaffolding, meeting capture, and meeting retrieval, from both a
CLI and a terminal UI.

**Command surface**

```
endpaper                                    # no args -> open the TUI
endpaper --version / --help                 # exit 0, works anywhere
endpaper init                               # create a workspace here
endpaper meeting new <description>          # create a meeting
      [--type <type>] [--tag <tag>]...
endpaper meeting list                       # list meetings
      [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

**Exit codes**: `0` success · `1` target not found · `2` usage error · `3` workspace error.

**`meeting list --json` schema** — exactly these seven keys per object, `path` forward-slashed
on every platform, `type` `""` and `tags` `[]` when absent, never null:

```
id, path, title, type, tags, created, updated
```

**TUI**: one screen, list and preview panes, `/` opens a combined filter/command bar
(`meeting.<type> <description>` to create, plain text to filter), `enter` opens full-screen
preview, `ctrl+q` quits.

**Guarantees**: no network access, no admin rights required to install, data always on stdout
and diagnostics on stderr, no ANSI when piped, malformed meeting files are skipped with a
warning and never rewritten.
