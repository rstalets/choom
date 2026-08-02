# Phase 1 Data Model: Vertical Layout for a Half-Width Window

**Feature**: `020-vertical-tui-mode` | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-02

This feature adds one persisted value and one derived value. No entity in `core/models.py` changes, no
document or task gains a field, and nothing in a workspace is read or written.

---

## 1. Persisted state

### 1.1 `ViewOrientation`

The setting itself. Two legal values and nothing else.

| Property | Value |
|---|---|
| Legal values | `"horizontal"`, `"vertical"` |
| Default | `"horizontal"` (FR-002, per the constitution 2.1.0 owner ruling) |
| Scope | One value **per user**, not per workspace (FR-008) |
| Lifetime | Persists across sessions and across workspaces |

Represented as a plain `str` constrained by a module-level tuple, mirroring
`config.LEGAL_ASSISTANT_VALUES` (`core/config.py:11`) rather than introducing an `Enum`. Principle VI
prefers a plain function to a class and a class to a framework; two string constants that are written
verbatim into a TOML file and typed verbatim by the user do not earn a type.

```python
LEGAL_VIEW_ORIENTATIONS = ("horizontal", "vertical")
DEFAULT_VIEW_ORIENTATION = "horizontal"
```

### 1.2 Storage location

Resolved by the single function `preferences_root()` (research R5) — the only place in the module that
reads an environment variable or calls `Path.home()`.

| Platform | Directory | Resolution order |
|---|---|---|
| Windows | `%LOCALAPPDATA%\choom\` | `LOCALAPPDATA` → `APPDATA` → `~\AppData\Local` |
| macOS, Linux | `$XDG_CONFIG_HOME/choom/` or `~/.config/choom/` | `XDG_CONFIG_HOME` (if set and absolute) → `~/.config` |

File: `preferences.toml`, created on first write. `write_text_atomic` already creates the parent
directory, so no explicit `mkdir` is needed (research R6).

### 1.3 File format

```toml
[view]
orientation = "vertical"
```

- The `[view]` table is created if absent; the `orientation` line is replaced in place if present.
- Comments, key order, and any unknown keys or tables survive a write (FR-012), using the same
  line-targeted edit `core/config.py:115-142` performs on `[assistant]`.
- CRLF is detected and preserved, as `_write_assistant_key` does (`core/config.py:106-110`), so a
  file hand-edited on Windows keeps its line endings.

### 1.4 Read semantics — every failure is the default

`get_view_orientation()` never raises. Each row below returns `"horizontal"` and choom opens normally
(FR-011), following the precedent `get_assistant` sets and documents.

| Condition | Result |
|---|---|
| File does not exist (the common case) | `"horizontal"` |
| File unreadable (`OSError`, permissions) | `"horizontal"` |
| File is not valid TOML (`tomllib.TOMLDecodeError`) | `"horizontal"` |
| `[view]` table absent, or not a table | `"horizontal"` |
| `orientation` key absent | `"horizontal"` |
| `orientation` is not a string (a number, a list, a bool) | `"horizontal"` |
| `orientation` is a string but not a legal value (`"sideways"`) | `"horizontal"` |
| `orientation = "vertical"` | `"vertical"` |

### 1.5 Write semantics

`set_view_orientation(value)`:

| Condition | Behaviour |
|---|---|
| `value` not in `LEGAL_VIEW_ORIENTATIONS` | Raises `UsageError`. **Nothing is written.** |
| Parent directory absent | Created by `write_text_atomic` |
| File absent | Created containing just the `[view]` table |
| File present | Only the `orientation` line changes; all other bytes survive |
| Write fails (permissions, full disk) | Raises `WorkspaceError`; the caller degrades per FR-013 |
| `value` already stored | Idempotent — same bytes written, no error |

The `UsageError`/`WorkspaceError` split matches `core/config.py:41-56`: an illegal value is the
caller's mistake, an I/O failure is the environment's.

---

## 2. Session state

### 2.1 `ChoomApp.view_orientation`

The stored preference, read **once** in `ChoomApp.__init__` (research R12) alongside the rest of the
session state. Nothing watches the file; a second running session is unaffected by a change here until
its own next launch.

This holds the *stored* value, not the effective one — the fallback is not baked in at startup,
because the terminal can be resized after it.

### 2.2 Effective orientation — derived, never stored

The screen never reads `view_orientation` directly. It asks for the **effective** orientation, which
resolves the stored value against the current screen height in exactly one place:

```
effective_orientation(stored, screen_height):
    if stored == "vertical" and screen_height < MIN_VERTICAL_SCREEN_HEIGHT:
        return "horizontal"          # the fallback, FR-033
    return stored
```

| Property | Value |
|---|---|
| Inputs | the stored orientation, and the screen's total height |
| Explicitly **not** an input | terminal width (FR-035, FR-039), available body height, whether the command bar / link picker / backlinks section is open |
| Purity | no I/O, no widget access — a function of two arguments |
| Home | `src/choom/tui/layout.py` (research R8) |

The fallback **never writes** (FR-034). `view_orientation` still reads `"vertical"` throughout, which
is why a relaunch in a taller terminal comes up vertical and why the `/config view` report can state
both facts at once (FR-037).

---

## 3. Geometry constants

Derived in research R7; stated here as the values the implementation must use.

| Constant | Value | Composition |
|---|---|---|
| `COLLECTION_BAR_ROWS` | 1 | `app.tcss:5-9` |
| `STATUS_BAR_ROWS` | 1 | `app.tcss:99-102` |
| `BAND_DIVIDER_ROWS` | 1 | `border-top` on the lower band |
| `MIN_UPPER_BAND_ROWS` | 4 | `#list-header` (1) + 3 record rows (FR-032) |
| `MIN_LOWER_BAND_ROWS` | 4 | 4 lines of preview content (FR-032) |
| **`MIN_VERTICAL_SCREEN_HEIGHT`** | **11** | the sum of the five above |

The constant is written as that sum in source, not as the literal `11`, so the derivation cannot drift
away from the value.

**Band split**: both bands take `height: 1fr`; Textual divides the remainder. At exactly 11 rows this
yields 4 and 4 — both minimums exactly met, which is what makes 11 the threshold rather than an
independent choice (research R7).

| Screen height | Upper band | Lower band | State |
|---|---|---|---|
| 40 | ~19 | ~18 | comfortable |
| 24 | ~11 | ~10 | required usable (FR-031) |
| 11 | 4 | 4 | exactly at the minimum |
| 10 | — | — | fallback to horizontal (FR-033) |

---

## 4. Widget tree

The one structure that differs between orientations (research R1). Ids are identical in both, which
is what lets the inline editor's mount target (`list_screen.py:246`) and every existing `query_one`
call keep working unchanged (research R10).

**Horizontal** — byte-for-byte today's tree, so FR-020 holds by construction:

```
Screen
├── CollectionBar #collection-bar     (dock: top)
├── Horizontal #body
│   ├── ScopePane #scope-pane
│   ├── Vertical  #list-pane          → #list-header, #meeting-list
│   └── Vertical  #preview-pane       → #preview, #preview-links-section
└── Vertical #bottom-bar              (dock: bottom) → LinkPicker, CommandBar, StatusBar
```

**Vertical** — `#body` gains the `-vertical` class and one intermediate container:

```
Screen
├── CollectionBar #collection-bar     (dock: top)
├── Vertical #body.-vertical
│   ├── Horizontal #upper-band                    ← NEW, vertical only
│   │   ├── ScopePane #scope-pane
│   │   └── Vertical  #list-pane      → #list-header, #meeting-list
│   └── Vertical #preview-pane        → #preview, #preview-links-section
└── Vertical #bottom-bar              (dock: bottom) → LinkPicker, CommandBar, StatusBar
```

Unchanged in both: every id, `CollectionBar`, `#bottom-bar` and all three of its children, and the
contents of every pane.

---

## 5. State transitions

### 5.1 Orientation switch (command path)

Trigger: `/config view <value>` with a legal value that differs from the effective orientation.

| Step | Action | Source |
|---|---|---|
| 1 | Validate; illegal values stop here with a message (FR-044) | new |
| 2 | `set_view_orientation(value)`; a `WorkspaceError` is caught and folded into the status message, and the switch continues (FR-013) | new |
| 3 | Update `app.view_orientation` | new |
| 4 | Capture the highlighted record's id | existing pattern, `refresh_rows:374-379` |
| 5 | `await self.query_one("#body").recompose()` | research R2 |
| 6 | `await self._refresh_scope_pane()` | existing, `list_screen.py:353` |
| 7 | `await self.refresh_rows(select_id=...)` | existing, `list_screen.py:367` |
| 8 | Restore the backlinks section if it was expanded (FR-021) | existing `_populate_preview_links` |
| 9 | `CommandBar.Closed` renders the status and focuses `#meeting-list` | existing, unchanged (research R3) |

Steps 6, 7, and 9 are the path `on_screen_resume` already runs on every return from a full-screen
editor. Nothing new is invented for state preservation.

### 5.2 Orientation switch (resize path)

Trigger: a resize changes `effective_orientation(...)`'s answer.

| Guard | Behaviour |
|---|---|
| An editor pane is open (`self._editor_pane is not None`) | **No recompose.** FR-025. Recomposing would destroy the editor and its unsaved buffer — the one data-loss risk in this feature (research R10). |
| Effective orientation unchanged | No recompose. Only the existing `_rerender_columns()` runs, as today. |
| Otherwise | Steps 4–8 above. |

### 5.3 What is *not* a transition

| Event | Effect on orientation |
|---|---|
| Opening the command bar or the link picker | None — the threshold reads screen height, not available height (FR-035) |
| Expanding the backlinks section | None |
| Switching collection, month, or filter | None |
| Entering or leaving a full-screen view or editor | None — it returns to the configured layout (FR-029) |
| The fallback engaging or reversing | None to the **stored** value (FR-034) |
| A resize that does not cross the threshold | None |

---

## 6. What this feature does not model

- No per-workspace orientation (FR-008).
- No pane sizes, split ratios, or scope-pane width — all fixed by CSS, none configurable.
- No window geometry, last collection, last scope, or last highlighted record.
- No migration: nothing existing moves into the new store.
- No new `core/models.py` entity, and no change to `Workspace`, `Document`, `Task`, or `YearMonth`.
