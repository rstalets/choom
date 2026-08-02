# Contract: layout geometry

**Feature**: `020-vertical-tui-mode` | **Module**: `src/choom/tui/layout.py`

Pure functions and constants, **no widget imports**, so the geometry is unit-testable without a
terminal — the arrangement `columns.py` established and research R8 confirms. This module is
interface code that happens to be pure; it does not belong in `core`, which has no notion of a screen.

---

## Constants

```python
COLLECTION_BAR_ROWS  = 1   # app.tcss: CollectionBar { dock: top; height: 1 }
STATUS_BAR_ROWS      = 1   # app.tcss: StatusBar { height: 1 }
BAND_DIVIDER_ROWS    = 1   # border-top on the lower band
MIN_UPPER_BAND_ROWS  = 4   # #list-header (1) + 3 record rows        (FR-032)
MIN_LOWER_BAND_ROWS  = 4   # 4 lines of preview content              (FR-032)

MIN_VERTICAL_SCREEN_HEIGHT = (
    COLLECTION_BAR_ROWS
    + STATUS_BAR_ROWS
    + BAND_DIVIDER_ROWS
    + MIN_UPPER_BAND_ROWS
    + MIN_LOWER_BAND_ROWS
)  # == 11
```

**The constant MUST be written as this sum, not as the literal `11`.** The number is a consequence of
five stated minimums; writing it as a literal is how it becomes untouchable in six months when someone
needs to know whether it can move and what it would break.

Precedent for the shape and placement: `MIN_PICKER_SCREEN_HEIGHT = 12` (`tui/edit_screen.py:74`), the
existing screen-height gate for a bottom-region widget.

---

## `effective_orientation(stored: str, screen_height: int) -> str`

The orientation actually rendered, resolving the stored preference against the terminal.

```
if stored == "vertical" and screen_height < MIN_VERTICAL_SCREEN_HEIGHT:
    return "horizontal"
return stored
```

| Property | Value |
|---|---|
| Inputs | the stored orientation; the screen's **total** height |
| Returns | one of `"horizontal"`, `"vertical"` |
| Raises | nothing. An unrecognised `stored` value returns `"horizontal"`. |
| Purity | no I/O, no clock, no widget access |

**Not inputs, deliberately** — each of these would be a bug:

| Excluded input | Why |
|---|---|
| Terminal **width** | FR-035, FR-039. Width degradation is already handled identically in both orientations by `column_widths`, `CollectionBar._render_bar`, and `shorten_workspace_path`. Vertical is a *height* trade, and a width term would flip the layout for the wrong reason. |
| **Available** body height | FR-035. `CommandBar` (1 row), `LinkPicker` (up to 8), and the backlinks section all shrink the body when opened. Reading available height would let pressing `/` flip the whole layout underneath the user mid-keystroke. |
| Whether an editor is open | The editor must not *change* the answer; it suppresses *acting* on it. That guard belongs in the resize handler, not here — see below. |

### Boundary

| `screen_height` | `stored="vertical"` returns | `stored="horizontal"` returns |
|---|---|---|
| 10 | `"horizontal"` (fallback) | `"horizontal"` |
| 11 | `"vertical"` | `"horizontal"` |
| 24 | `"vertical"` | `"horizontal"` |

The `10`/`11` pair is the required unit test in both directions. A test that only asserts "it falls
back somewhere" does not pin the constant.

---

## Band split

Both bands take `height: 1fr`; Textual divides the remainder. No arithmetic in Python.

This is self-consistent with the threshold rather than a second rule: at exactly
`MIN_VERTICAL_SCREEN_HEIGHT`, `1fr`/`1fr` over the 8 remaining rows yields 4 and 4 — precisely
`MIN_UPPER_BAND_ROWS` and `MIN_LOWER_BAND_ROWS`. One row shorter violates one of them, which is the
definition of the threshold.

| Screen height | Upper | Lower |
|---|---|---|
| 40 | ~19 | ~18 |
| 24 | ~11 | ~10 |
| 11 | 4 | 4 |

---

## Stylesheet contract (`app.tcss`)

The blast radius, stated so the diff can be checked against it (research R9). Every change is an
**added** vertical variant; no base rule is edited, which is what makes FR-020 ("no residual
difference" in horizontal) structural.

### May change

| Selector | Change |
|---|---|
| `#body` | add `#body.-vertical { layout: vertical; }` beside the existing rule |
| `#upper-band` | **new** — `height: 1fr; layout: horizontal` |
| `#list-pane` | vertical variant only: drop `border-right` (it is rightmost in the upper band) |
| `#preview-pane` | vertical variant only: full width, `height: 1fr`, `border-top` divider |
| `#preview-links-section` | vertical variant only: bound relative to the band, not the fixed `max-height: 12` |

### Must not change

Anything below appearing in the diff is scope creep:

`Screen`, `CollectionBar`, `#scope-pane` (base width and border), `#scope-list`, `#list-header`,
`#meeting-list`, `#bottom-bar`, `CommandBar` and its three child rules, `StatusBar`, `#link-picker`,
`#links-section`, `#links-list`, `#preview-links-list`, `#editor`, `EditorPane`, `#confirm-dialog`,
`ConfirmDialog`, `HelpScreen`, `#help-pane`, `#help-body`.

### The backlinks bound (FR-043)

`#preview-links-section` is currently `max-height: 12` with its inner list at `max-height: 10`
(`app.tcss:50-60`). In horizontal the preview pane is full body height, so 12 rows is a slice. In
vertical at 80x24 the lower band is ~10 rows — the existing constant would consume the **entire band**
and leave no preview visible.

The vertical variant therefore bounds the section as a fraction of its container rather than as a
fixed row count, so preview content above it stays visible at every height down to the threshold.

This regression is invisible in the issue's sketch and findable only by reading the stylesheet against
the new band height.
