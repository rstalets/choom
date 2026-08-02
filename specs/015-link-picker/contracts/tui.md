# Contract: TUI

**Feature**: `015-link-picker` | **Module**: `choom.tui.link_picker`, `choom.tui.edit_screen`,
`choom.tui.list_screen`, `choom.tui.rendering`, `choom.tui.status_bar`

---

## C1 — Where the picker appears

| Host | Composition | Picker position |
|------|-------------|-----------------|
| `ListScreen` (editor inline in `#preview-pane`) | `#bottom-bar` → `LinkPicker`, `CommandBar`, `StatusBar` | Above the command bar and status bar, spanning the screen |
| `EditScreen` (editor full-screen) | `#bottom-bar` → `LinkPicker`, `StatusBar` | Above the status bar, spanning the screen |

The widget is mounted with `display = False` and stays mounted for the life of the screen. `EditorPane`
finds it with `self.screen.query_one(LinkPicker)` — the same idiom as `_render_status`'s
`self.screen.query_one(StatusBar)` — so one code path serves both hosts (FR-004).

Opening the picker changes no other widget's size or position (FR-005): `#bottom-bar` is
`height: auto` and docked, and `#link-picker` carries `max-height: 8`.

---

## C2 — Keys while the picker is open

| Key | Action | Shown in footer |
|-----|--------|-----------------|
| `↑` | Highlight previous, wrapping to the last row from the first | yes |
| `↓` | Highlight next, wrapping to the first row from the last | yes |
| `enter` | Insert a link to the highlighted record, close | yes |
| `esc` | Close, leaving the typed line byte-identical | yes |
| `ctrl+q` | Quit, unchanged — never suspended (Principle V) | yes |

Every other key is inert with respect to the document. While the picker is open,
`EditorPane.check_action()` returns `False` for `save`, `save_and_close`, `close`, and
`cancel_request`, so the pane's `priority=True` bindings (`ctrl+o`, `ctrl+s`, `ctrl+x`, `ctrl+c`) do
not act underneath the list. `ctrl+c` gains no binding anywhere.

**Footer string** (`status_bar.py`):

```python
LINK_PICKER_HELP = "↑↓ move   enter insert   esc cancel   ctrl+q quit"
```

Swapped in when the picker opens and back to `EDIT_HELP` when it closes — the same way
`LINKS_SECTION_HELP` swaps against `PREVIEW_HELP`. The two never concatenate.

---

## C3 — Row format

```python
def render_candidate_row(candidate: LinkCandidate, width: int) -> str:
```

Renders `title · collection · date`, e.g.:

```text
Q3 planning · meeting · 2026-07-28
Q3 planning · note · 2026-03-14
call Terry about the renewal · task · —
```

| Rule | Behaviour |
|------|-----------|
| Undated record | `—` in the date position; the row still renders |
| Title too long for `width` | Title truncated with `…`; collection and date always survive intact |
| `width` of 0 or absurdly small | Returns the title truncated to whatever fits, without raising |
| Blank title | Renders a blank title cell rather than raising |

`width` is passed in rather than read from a widget, so the function is unit-testable without a
terminal — the same shape as `in_flight_status(breadcrumb, width)`.

---

## C4 — `/link` outcomes

| Matches | Screen height | Behaviour |
|---------|---------------|-----------|
| 0 | any | `link_no_match_status(query)`; line left as typed. **Unchanged.** |
| 1 | any | Link inserted directly, no list, no extra keystroke. **Unchanged.** |
| ≥ 2 | ≥ `MIN_PICKER_SCREEN_HEIGHT` (12) | Picker opens, first row highlighted |
| ≥ 2 | < `MIN_PICKER_SCREEN_HEIGHT` | `link_ambiguous_status(titles)`; no list; line left as typed |

The save that `/link` performs before searching is unchanged — opening the picker adds no save and
removes none.

---

## C5 — Insertion

On `enter`, `resolve_id(workspace, candidate.target.id)` runs again:

| Result | Behaviour |
|--------|-----------|
| Resolves | Line replaced with `format_link(editing_file, resolved_target, title)` — the same call the single-match path makes, so the relative path is correct from the edited file's own location |
| Does not resolve | Reported in the status bar; line left as typed; nothing written |

---

## C6 — Resize

| Condition | Behaviour |
|-----------|-----------|
| Width changes, picker open | Rows rebuilt at the new width; candidates and highlighted index preserved |
| Height drops below the threshold, picker open | Picker closes, fallback message shown, line left as typed |
| Any resize | The typed line is never modified |

---

## C7 — What does not change

- The list → preview → edit state machine gains no state. No screen is pushed or popped.
- The cursor's location in the editor, and the editor's scroll position, are untouched throughout.
- Inline, the list and scope panes keep their size and position; the editor keeps the preview pane.
- `link_ambiguous_status()` and `link_no_match_status()` both remain — the first now serves the
  too-short-terminal fallback, the second is unchanged.
