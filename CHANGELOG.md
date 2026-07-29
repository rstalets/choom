# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### 0.0.2

Daily notes and typed notes, on the same machinery meetings already use.

**Command surface added**

```
endpaper note today                         # open (creating if needed) today's daily note
endpaper note new <description>             # create a typed or untyped note
      [--type <type>] [--tag <tag>]...
endpaper note list                          # list notes, daily and typed together
      [--json] [--type <type>] [--tag <tag>]... [--since <YYYY-MM-DD>]
```

**`core` API** — additive: `Document`/`DocumentFilter` are now the canonical types, with
`Meeting`/`MeetingFilter`/`Note` retained as aliases. `create_document`, `scan_documents`,
`filter_documents`, and `match_document` generalise `create_meeting` et al., which remain
exported with unchanged signatures. No name removed, no signature changed.

**`note list --json` schema** — the same seven keys as `meeting list --json`, `n_`-prefixed
id, `notes/`-prefixed path:

```
id, path, title, type, tags, created, updated
```

`note today` is idempotent: it prints the same path every time it is called on the same day
and never modifies an existing daily note's bytes or mtime, even if its frontmatter is
broken by hand. `--type daily` is reserved and rejected by `note new` before any file is
written.

**TUI**: `/note` opens today's daily note; `/note.<type> <description>` and
`/note <description>` create a typed or untyped note; `/notes` and `/meetings` switch which
collection the existing list and preview panes show. No new screen, no new key binding — the
active collection is shown in the status bar and in the empty-state message.

**Guarantees**: unchanged from 0.0.1, extended to notes — malformed note files are skipped
with a warning and never rewritten; the daily note is never opened for writing once it
exists.

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
