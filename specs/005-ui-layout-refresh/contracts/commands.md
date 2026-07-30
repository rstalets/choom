# Contract: command bar verbs

**Feature**: `005-ui-layout-refresh`

The command bar's verb table is the single source for three things: what the parser accepts, what
`/help` displays, and what error an unknown word produces. One table, three consumers — a command
cannot exist without appearing in help (FR-039).

---

## The verb table

| Verb | Alias | Argument | Description (shown in `/help`) |
|---|---|---|---|
| `filter` | `f` | `<term>` (optional) | Narrow the list; no term clears it |
| `help` | — | — | Show this pane |
| `meeting` | — | `<description>` | Create a meeting and open it for editing |
| `note` | — | `<description>` (optional) | Create a note; with no description, today's daily note |
| `task` | — | `<description>` | Add a task |
| `meetings` | — | — | Switch to the Meetings collection |
| `notes` | — | — | Switch to the Notes collection |
| `tasks` | — | — | Switch to the Tasks collection |
| `init` | — | — | Registered, no TUI action (reserved) |

`meeting`, `note`, and `task` also accept the existing `verb.type` form (`meeting.standup`,
`note.research`), which is unchanged by this feature.

---

## Parsing rules

1. The leading `/` is a separate widget and is never part of the input value (see
   [tui-keys.md](./tui-keys.md)). The parser therefore receives the text with no slash to strip —
   the current `_normalize()` helper is deleted.
2. The first whitespace-separated token, lowercased and split at the first `.`, is matched against
   the verb table.
3. **A token that is not in the table is an error** (FR-031): `unknown command: 'budgt'. Press
   / then 'help' for the list.` The list is left untouched. This is the change that removes the
   namespace collision — no unrecognised word is silently reinterpreted as a search term.
4. The leading-space escape hatch (`" meetings"` to filter for the literal word) is **removed**. It
   existed only because bare words were filters; `/filter meetings` now says the same thing
   explicitly.

### Filter timing

Filtering stays live, which the constitution names as inherently interactive:

| Input state | Behaviour |
|---|---|
| `filt`, `f` (verb incomplete) | Nothing filters yet |
| `filter ` / `f ` (verb complete, no term) | Filter cleared; displayed month restored |
| `filter bu` → `filter bud` … | Filters live on each keystroke |
| Submitted with `enter` | Bar closes, filter stays applied |
| `escape` | Bar closes, filter cleared, displayed month restored (FR-034) |

The first live filter keystroke in a collection starts the cross-month load on a worker thread
(research R7); later keystrokes and later filters read the session cache.

---

## Errors

| Condition | Message |
|---|---|
| Unknown verb | `unknown command: '<token>'. Press / then 'help' for the list.` |
| `task` with no description | `task needs a description` (unchanged) |
| `note.<type>` with no description | `note.<type> needs a description` (unchanged) |
| Create rejected by core | The `UsageError` text, unchanged |

Errors render in the status bar with the existing `⚠ ` prefix. No error opens a dialog — nothing is
lost, so Principle V forbids a confirmation.

---

## `/help` pane content

Rendered from the verb table above, in table order, one row per verb:

```text
  /filter <term>   (/f)   Narrow the list; no term clears it
  /help                   Show this pane
  /meeting <desc>         Create a meeting and open it for editing
  ...

  esc to close
```

The pane also lists the key bindings from [tui-keys.md](./tui-keys.md), because "every available
command" as a user understands it includes the keys. A test asserts that every verb in the table
appears in the rendered pane, so the two cannot drift (FR-039).

---

## CLI parity

| TUI verb | CLI equivalent | Note |
|---|---|---|
| `filter` | — | Live filtering is inherently interactive (Principle II) |
| `help` | `endpaper --help` | Already exists |
| `meeting` | `endpaper meeting new` | Exists; the TUI now opens the editor after, the CLI never does |
| `note` | `endpaper note new` / `endpaper note today` | Exists |
| `task` | `endpaper task add` | Exists |
| collection switches | `endpaper <collection> list` | Exists |
| Done category | **`endpaper task list --done`** | **New** — see research R8 |

`--done` is the only CLI change in this feature. It is additive: no existing flag, exit code, or
`--json` key changes, and `--done` wins if combined with `--all` rather than erroring, because the
CLI must not fail on input it can interpret.
