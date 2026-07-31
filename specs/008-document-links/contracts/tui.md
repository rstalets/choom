# Contract: TUI surfaces

**Feature**: `008-document-links`

Two surfaces: a Links section in the preview pane, and `/link` in the editor. Both obey Principle V —
the app stays one screen with the state model **list → preview → edit**, every active binding is
visible in the footer, and no confirmation fires when nothing would be lost.

---

## The Links section

A collapsible region inside the existing `PreviewScreen`. **Not a fourth state.** `esc` still means
"back to the list" and `e` still means "edit"; nothing about the existing model moves.

### Bindings

| Key | State | Action | In footer |
|---|---|---|---|
| `l` | Preview | Toggle the Links section | Yes |
| `↑` / `↓`, `j` / `k` | Links section focused | Move between links | Yes |
| `enter` | Links section focused | Open the selected record | Yes |
| `o` | Links section focused | Alias for `enter` | Yes (as `enter/o open`) |
| `esc` | Links section focused | Collapse the section, stay in preview | Yes |

`l` is chosen deliberately, not because it was free. In the list screen `h`/`l` already move between
panes, so `l` reads as "move rightward into a pane" throughout the app; using it for "open the links
pane" is consistent rather than colliding. No modifier keys. `ctrl+c` and `ctrl+q` are untouched.

### Footer budget

This is a real constraint, enforced by `tests/unit/test_footer_bindings.py`.

| State | Help text | Width |
|---|---|---|
| Preview (today) | `e edit   esc back   ↑↓/pgup/pgdn scroll   ctrl+q quit` | 53 |
| Preview (new) | `e edit   l links   esc back   ↑↓/pgup/pgdn scroll   ctrl+q quit` | 63 |
| Links section focused | `↑↓ move   enter/o open   esc close   ctrl+q quit` | ~46 |

The section swaps the help string rather than appending to it, so the footer never overflows — the
same approach `EDIT_HELP` already takes. Both strings fit 80 columns.

### Load behaviour

This is **behavioural, not an optimisation** (FR-048, FR-049):

| Direction | When computed | Cost |
|---|---|---|
| Outbound | On document open | Nothing — parsed from the document already in memory |
| Inbound | The first time the section is expanded | One workspace scan (~155 ms at 6,000 documents) |

Outbound above, inbound below (FR-047). The asymmetry is exactly why the section is expandable at
all: making inbound links free would mean scanning the workspace every time anyone opened any
document.

### Rendering

```
── Links ──────────────────────────────────────────
  Points at
    → Q3 planning                    meetings  2026-07-28
    → vendor landscape               notes     2026-07-30
    ⚠ (unresolved) meeting_20260101_deadbeef

  Points here
    ← call Terry about the renewal   tasks
    ← follow-up research             notes     2026-07-31
```

- A dead link is shown with its unresolvable id rather than hidden. The user wrote it; it stays
  visible (Principle IV).
- A record nothing points at says so plainly — an empty region reads as a bug (US7 AC3).
- Selecting a dead link and pressing `enter` reports in the status bar and does not change the view
  (US7 AC5). No dialog: nothing is being lost.
- Opening a link switches to whichever collection the target lives in, including `tasks.md`
  (FR-050).

---

## `/link` in the editor

`/link <search terms>` typed as an entire line and submitted with `enter` replaces that line with a
markdown link to the matching record.

```
before:   /link q3 planning
after:    [Q3 planning](../../../meetings/2026/07/2026-07-28-q3-planning.md#meeting_20260728_a1b2c3d4)
```

### Plumbing

Reuses what `/ai` already established, which is the reuse the spec claims:

- `EditorCommand(name="link", …)` joins `EDITOR_COMMANDS` in `core/editor_commands.py`. `parse_line`
  dispatches off that table, so registering the command *is* the parser change — and `/help` picks
  it up with no further work.
- `EditorTextArea` already intercepts `enter` and posts `EditorCommandSubmitted`; `EditScreen` gains
  a branch for `link`.

### Behaviour

| Matches | Result |
|---|---|
| Exactly one | The line is replaced with the link; path correct from this file's location (FR-043) |
| None | Line left exactly as typed; status bar names the failure |
| Several | Line left exactly as typed; status bar reports the ambiguity and names candidates |

Rules that hold in every outcome:

- **Save first, then act** (FR-045) — the same order `/ai` uses. The path is derived from this file's
  real location, so the file has to be on disk at its real path first.
- **Never leave the document** (FR-045). No dialog, no picker screen, no state change. Ambiguity is
  reported so the user can retype with better terms; a picker would contradict the editor's whole
  design, which is why the spec chose reporting over choosing.
- **A line that is not entirely the command is ordinary text** (FR-046). Leading whitespace, a
  preceding character, or an unregistered word all fall through to `parse_line` returning `None` —
  existing behaviour, unchanged.

Matching reuses `match_document`, so `/link` and the list filter agree on what "matches" means. Two
different notions of matching in one app is a bug waiting to be reported.

---

## Save-time repair, from the TUI's side

The TUI gains no binding for repair. Saving already heals (`save_buffer` takes the workspace), so a
TUI user never accumulates the staleness that `endpaper links heal` exists to clear — which is the
justification for `check`/`heal` having no TUI equivalent under Principle II.

When a save heals links, `saved_text` differs from the buffer. `EditScreen._save()` already handles
that case by reassigning the buffer — the path exists because stamping `updated` already changes text
under the user — so healing introduces no new editor state.

Dead links found during a save surface in `SaveResult.warnings` and are shown in the status bar in
the existing `⚠ …` form. The save still succeeds: a dead link is reported, never fatal (FR-025).
