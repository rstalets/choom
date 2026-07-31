# Contract: TUI keys, panes, and focus

**Feature**: `005-ui-layout-refresh`

Principle V requires every active binding to be visible in the footer and every transition to be one
keystroke. This file is the authority for what is bound where; the footer strings in `status_bar.py`
must match it exactly.

---

## Layout

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Endpaper >>    Tasks    Notes   |Meetings|                            │  CollectionBar (top, height 1)
├──────────┬──────────────────────────┬─────────────────────────────────┤
│ 2026-07  │ 2026-07-01 standup Mon   │  <preview>                      │
│ 2026-06  │ 2026-07-02 standup Tue   │                                 │  body (1fr)
│ Unfiled  │                          │                                 │
├──────────┴──────────────────────────┴─────────────────────────────────┤
│ /filter or command                                            v0.0.3  │  bottom bar (height 1–2)
└───────────────────────────────────────────────────────────────────────┘
   scope pane          list pane              preview pane
   (width 14)          (2fr)                  (3fr)
```

The 14 columns the collection menu used are returned to the panes: the scope pane keeps a fixed 14
for `YYYY-MM` plus padding, and the freed width goes to the `2fr`/`3fr` split (FR-006). For Tasks,
the preview pane renders empty (FR-021) but is not removed, so pane widths do not jump when the
collection changes.

---

## Bindings — list screen

| Key | Action | Availability | Footer |
|---|---|---|---|
| `tab` | Next collection | Disabled while the command bar is open (`check_action`) | `tab collection` |
| `shift+tab` | Previous collection | Same | (implied by `tab collection`) |
| `j` / `down` | Move highlight down in the focused pane | Always | `↑↓/jk move` |
| `k` / `up` | Move highlight up in the focused pane | Always | (as above) |
| `h` / `left` | Focus the scope pane | Always | `h/l pane` |
| `l` / `right` | Focus the list pane | Always | (as above) |
| `enter` | Open the highlighted document in preview | Documents only | `enter open` |
| `e` | Open the highlighted document in the editor | Documents only; no-op on tasks and on the empty state | `e edit` |
| `space` | Toggle the highlighted task | Tasks only | `space toggle` |
| `/` | Open the command bar | Always | `/ filter or command` |
| `ctrl+q` | Quit | Always (app-level, priority) | `ctrl+q quit` |

**Removed**: `a` (show all) — replaced by the Done category (FR-017–FR-019). Its footer text goes
with it.

**Not bound**: `tab` no longer performs Textual's default focus traversal on this screen. Pane
movement is explicit via `h`/`l`, so nothing becomes unreachable, and the footer must not describe
Tab as focus movement.

### Focus rules

- Selecting any collection places focus on the **list pane** with row 0 highlighted (FR-005). This
  holds for Tab, shift+Tab, and the `/tasks` / `/notes` / `/meetings` verbs.
- Moving the highlight in the scope pane refills the list pane but does **not** move focus, so a user
  can walk months with `j`/`k` and watch the list change.
- Closing the command bar or the help pane returns focus to the list pane.

---

## Bindings — other screens (unchanged)

| Screen | Keys |
|---|---|
| `PreviewScreen` | `e` edit, `escape` back, `↑↓`/`pgup`/`pgdn` scroll, `ctrl+q` quit |
| `EditScreen` | `ctrl+o` save, `ctrl+x` save & back, `ctrl+s` save (alias), `escape` discard, `ctrl+q` quit |
| `HelpScreen` (new) | `escape` close, `↑↓` scroll, `ctrl+q` quit |

`tab` is deliberately unbound on all three: `EditScreen`'s `TextArea` keeps Textual's default
behaviour, and `HelpScreen` is a `ModalScreen`, whose bindings take precedence over the app's. This
is what satisfies FR-007 without extra code.

---

## Screen transitions

| From | Key/event | To |
|---|---|---|
| list | `enter` on a document | preview |
| list | `e` on a document | **edit** (new) |
| list | create verb succeeds | **edit** (new — was preview) |
| list | `/help` | help (modal) |
| preview | `e` | edit |
| preview | `escape` | list |
| edit | `ctrl+x` | caller (list or preview) |
| edit | `escape` with changes | discard dialog |
| edit | `escape` with no changes | caller |
| help | `escape` | list, state untouched |

Every transition is one keystroke, and list → preview → edit still describes the whole machine
(Principle V); this feature adds edges into `edit`, not a new state.

### One route into the editor

All four edges into `edit` — preview `e`, list `e`, create note/meeting, daily note — call the same
helper, and the `EditScreen` class is not modified:

```python
# endpaper/tui/edit_screen.py
def open_editor(app: App[None], path: Path) -> bool: ...
```

**Guarantees**:

1. The editor reached from the list is the same object, with the same bindings and the same
   unsaved-changes handling, as the one reached from preview — FR-023 holds by construction rather
   than by two implementations agreeing.
2. A file that cannot be read produces a status-bar message and leaves the caller's screen in place.
   `load_for_edit` raises `OSError`; that path is unguarded today at the single call site, and the
   helper is where it gets handled rather than copied four times (research R10).
3. Returning from the editor is `pop_screen`, so each caller lands back on the screen it left,
   with no per-caller return logic.

A test asserts that `e`-from-list and `e`-from-preview produce an `EditScreen` with identical
bindings and buffer contents for the same document.

---

## The bottom bar

Two rows, docked bottom:

1. **Command bar** — hidden until `/` is pressed. Composed as
   `Horizontal(Static("/", id="bar-prefix"), Input(id="bar-input"))`. The prefix is a separate
   widget, so no editing key can delete it (FR-027, FR-028).
2. **Status bar** — the footer text for the active collection on the left, the version on the right
   (FR-042), warnings appended when the displayed month has any (FR-016).

The version renders as `v{endpaper.__version__}` — the same attribute `endpaper --version` prints,
so the two front-ends cannot disagree.

---

## Empty and transient states

| Condition | List pane shows |
|---|---|
| Month has no documents | `No meetings in 2026-07. Press / then 'meeting <description>' to create one.` (per collection) |
| Collection has no documents at all | The existing empty-state message |
| Filter matches nothing | `No matches for '<term>'.` — distinct from an empty month (spec edge case) |
| Cross-month load in flight | `Searching…` — the pane stays responsive (FR-036) |
| Unfiled selected, none present | Unfiled is not shown at all when `has_unfiled` is `False` |
