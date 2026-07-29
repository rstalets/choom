# Contract: TUI states and bindings (viewing and editing)

**Baseline**: [feature 002's TUI contract](../../002-general-notes/contracts/tui.md). This page records
the third state and the bindings that reach it. Anything not mentioned is unchanged.

---

## The screen stack is the state machine

| State | Screen | Pushed by |
|---|---|---|
| list | `ListScreen` | app mount |
| preview | `PreviewScreen` | `enter` on a row, or a create |
| edit | `EditScreen` | **new** — `e` in preview |
| — | `DiscardDialog(ModalScreen[bool])` | **new** — `esc` in edit while dirty |

Three states, one keystroke per transition (FR-001). Each screen owns its own `BINDINGS` and its own
footer string, so no binding can be advertised in a state where it does nothing (FR-031).

---

## Bindings by state

### `PreviewScreen` — **changed**

| Key | Action | Shown | Note |
|---|---|---|---|
| `e` | `edit` | yes | **new** (FR-003). Lifts the restriction features 001 and 002 placed on this footer (FR-032). |
| `esc` | `close_preview` | yes | unchanged (FR-004) |
| `↑`/`↓`/`pgup`/`pgdn` | scroll | yes | unchanged |

Also gains `on_screen_resume`, which re-reads the file and re-renders, so returning from a save shows
saved content (FR-007).

### `EditScreen` — **new**

| Key | Action | Shown | Requirement |
|---|---|---|---|
| `ctrl+o` | `save` — write, stay in edit | **yes, canonical** | FR-014, FR-015 |
| `ctrl+s` | `save` — identical behaviour | **no** (alias) | FR-015 |
| `ctrl+x` | `save_and_close` — write, return to preview | yes | FR-014 |
| `esc` | `close` — discard-checked return to preview | yes | FR-005, FR-024 |

`ctrl+s` is bound but not shown, because it is XOFF on terminals with legacy flow control and cannot
be guaranteed to arrive. `ctrl+o` is what the footer promises (FR-015, §4.5).

### `DiscardDialog` — **new**

`ModalScreen[bool]`. Discard dismisses `True`, Cancel dismisses `False`. Being modal, it blocks the
parent screen's bindings while up.

---

## Reserved and forbidden

| Key | Status | Requirement |
|---|---|---|
| `ctrl+q` | app-level quit, **not rebound** by this feature | FR-033 |
| `ctrl+c` | Textual-reserved, **not rebound** | FR-033 |
| `tab` | switches focus; **must not insert a tab** into the buffer | FR-012 |
| any `cmd`/`alt`/`super` binding | **forbidden** — `ctrl` is the only portable modifier | FR-034 |

---

## Footer strings

Added to `tui/status_bar.py` alongside the existing `LIST_HELP` and `PREVIEW_HELP`:

```python
PREVIEW_HELP = "e edit   esc back   ↑↓/pgup/pgdn scroll   ctrl+q quit"   # changed: + e
EDIT_HELP    = "ctrl+o save   ctrl+x save & back   esc discard   ctrl+q quit"   # new
```

**Contract**: every key in a state's `BINDINGS` with `show=True` appears in that state's footer
string, and the footer string names no key the state does not bind (FR-030, FR-031). A test asserts
this by comparing the two, rather than by eyeballing the strings.

The warning slot already used by `PreviewScreen` (`⚠ {note}   {HELP}`) carries the
frontmatter-not-stamped warning (FR-018) and the save-failed error (FR-020).

---

## The editor widget

```python
TextArea(file.text, show_line_numbers=True, id="editor")
```

One non-default option. `soft_wrap=True` and `tab_behavior="focus"` are already the defaults and are
what FR-011 and FR-012 require; `TextArea.code_editor()` would break both. See
[R5](../research.md#r5-textarea-configuration--one-option-not-the-convenience-constructor).

| Property | Value | Requirement |
|---|---|---|
| gutter numbering | real lines only, starting at 1 on the opening `---` | FR-010 |
| wrapped continuation rows | unnumbered, no horizontal scroll | FR-011 |
| buffer content | whole file **including** frontmatter | FR-009 |

---

## Behaviours

| Trigger | Effect |
|---|---|
| `e` in preview | `load_for_edit(path)`; push `EditScreen`; `original_text = file.text` |
| `ctrl+o` / `ctrl+s` | `save_buffer(...)`; on ok, `original_text = result.saved_text`; **cursor and scroll position preserved** (FR-014); on failure, stay put and show the error |
| `ctrl+x` | same save; on ok, pop to preview; **on failure, stay in edit** — a failed save must not discard the buffer by leaving |
| `esc`, not dirty | pop immediately, no dialog (FR-025) |
| `esc`, dirty | push `DiscardDialog`; `True` pops to preview, `False` returns to the buffer untouched (FR-027, FR-028) |
| any successful save | app re-scans **only** the changed file; the list row updates on return (FR-021, FR-022) |
| document no longer matches the active filter after an edit | selection moves to the nearest remaining row (Edge Cases) |

---

## Test hooks

Headless via `App.run_test()` / `Pilot`, matching `tests/integration/test_list_tui.py`.

| Assertion target | How |
|---|---|
| edit state entered | `isinstance(app.screen, EditScreen)` |
| buffer content | `app.screen.query_one("#editor", TextArea).text` |
| gutter on | `app.screen.query_one("#editor", TextArea).show_line_numbers is True` |
| soft wrap on | `.soft_wrap is True` |
| tab does not insert | `.tab_behavior == "focus"` |
| dirty rule | `app.screen.is_dirty` |
| dialog raised | `isinstance(app.screen, DiscardDialog)` |
| footer matches bindings | compare `EDIT_HELP` against `EditScreen.BINDINGS` where `show=True` |
