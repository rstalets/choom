# Contract: Terminal interface

**Scope**: list and preview only. The edit state — line numbers, `ctrl+o`/`ctrl+x`, the
unsaved-changes prompt — belongs to REQUIREMENTS.md §3.5 and is **not** built here. Until it exists,
the preview footer must not advertise an edit key (FR-037).

---

## Layout — one screen

```
┌──────────────────────────────────────────────────────────────┐
│ endpaper · platform-team                        12 meetings  │  header
├──────────────────────┬───────────────────────────────────────┤
│ 2026-07-28 standup   │ # Q3 planning                         │
│   Q3 planning        │                                       │
│   platform           │ Rendered markdown of the selected     │
│ ─────────────────────│ meeting.                              │  list │ preview
│ 2026-07-27 vendor    │                                       │
│   Contoso renewal    │                                       │
│   procurement        │                                       │
├──────────────────────┴───────────────────────────────────────┤
│ / filter or command   ↑↓/jk move   enter open   ctrl+q quit  │  footer
└──────────────────────────────────────────────────────────────┘
```

One screen, two panes (FR-034). The preview pane tracks the selection live; `enter` promotes it to
full screen.

---

## States

```
        enter                 esc
list ──────────▶ preview ──────────▶ list
  ▲                                    │
  └────────────────────────────────────┘

/ opens the command bar in either state; esc closes it and returns focus.
```

Three states, not four — `edit` is absent by design this feature.

After creating a meeting from the command bar, the user lands in **preview** of the new file
(FR-037), so the flow is: type one line, get a note, look at it.

---

## Key bindings

Every binding listed here is visible in the footer for the current state (FR-035). No hidden keys.

### List state

| Key | Action |
|---|---|
| `/` | Open the command bar |
| `↑` `↓` `j` `k` | Move selection. Stops at both ends; no wrapping |
| `enter` | Open selected meeting in full-screen preview |
| `ctrl+q` | Quit |

### Preview state

| Key | Action |
|---|---|
| `esc` | Back to list |
| `↑` `↓` `pgup` `pgdn` | Scroll |
| `ctrl+q` | Quit |

### Command bar (open)

| Key | Action |
|---|---|
| any text | Live filter, or compose a command — see grammar below |
| `enter` | Run the command. In filter mode, close the bar and keep the filter |
| `esc` | Close the bar, clear the filter, restore focus |

### Reserved — never bind

| Key | Why |
|---|---|
| `ctrl+c` | Reserved by Textual |
| `ctrl+q` | XON, and Textual's conventional quit. Left as quit (FR-036) |
| `ctrl+s` | XOFF. Not used this feature; when edit arrives it is an alias only, never the advertised save key |
| any `cmd+…` | macOS terminals intercept before the app sees it. Never promise one |

---

## Command bar grammar

`/` opens one input that is both the filter and the command line
([research.md R4](../research.md#r4-the--key-filter-and-command-in-one-input)).

```
input      := command | filter
command    := verb ["." type] [SP description]
verb       := "meeting" | "meetings" | "init"
filter     := any text whose first-token stem is not a registered verb
```

**Resolution**: take the first whitespace-delimited token, take the part before any `.`, and look it
up in the registered verb set. Hit ⇒ command. Miss ⇒ filter.

| Typed | Mode | Effect |
|---|---|---|
| `vendor renew` | filter | List narrows live |
| `meeting.standup Q3 planning #platform` | command | Creates on `enter` |
| `meeting Q3 planning` | command | Untyped meeting |
| `meetings` | command | Clear filters, show all meetings |
| `␣meetings` (leading space) | filter | Escape hatch for filtering the literal word |

**Live vs deferred**: filtering applies on every keystroke; commands only run on `enter`. A
mis-sniffed command therefore never *does* anything without a confirming keypress.

**Mode is always visible.** The footer shows `[filter]` or `[command: meeting.standup]` as the user
types, so the decision is never a surprise (Principle V).

**Inline `#tag`** works anywhere in the description and is repeatable (FR-021). The TUI owns its own
input, so unlike the CLI there is no shell to eat the `#`.

---

## Behaviour rules

| Rule | Requirement |
|---|---|
| List sorted by date descending: date, type, title, tags | FR-027 |
| Filter matches title, type, and tags, case-insensitively, as a substring | FR-030 |
| Filtering reads only the in-memory list — zero disk access per keystroke | FR-031 |
| Malformed meeting files are absent from the list; the footer shows a warning count | FR-033 |
| Empty workspace shows an empty-state message, not a blank pane | US3 scenario 6 |
| Resize and very small terminals re-layout without crashing | Edge cases |

**Startup**: `core.scan_meetings` runs once, and the result is held in memory for the session
(Principle III — no index, no cache file). Creating a meeting appends its record to the in-memory
list rather than re-scanning the workspace.

---

## Testing

Headless via `App.run_test()` and `Pilot`, so every scenario here runs in CI with no terminal
attached (SC-006, [research.md R7](../research.md#r7-testing-a-textual-app-without-a-terminal)).

```python
async with EndpaperApp(workspace).run_test(size=(80, 24)) as pilot:
    await pilot.press("/")
    await pilot.press(*"meeting.standup Q3 planning")
    await pilot.press("enter")
    await pilot.pause()          # required: messages bubble asynchronously
    assert ...
```

`pilot.pause()` before every assertion. Without it, assertions race the message pump and fail
intermittently — which is worse than failing consistently.
