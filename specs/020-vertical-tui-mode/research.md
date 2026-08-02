# Phase 0 Research: Vertical Layout for a Half-Width Window

**Feature**: `020-vertical-tui-mode` | **Spec**: [spec.md](./spec.md) | **Date**: 2026-08-02

Every finding below was checked against the code in this worktree or the installed
`textual==8.2.8` source, not from memory. File and line references are to the state of
`origin/release/v0.0.4` at the time of writing.

---

## R1: A static widget tree cannot serve both orientations — the arithmetic rules it out

**Question**: Can the two layouts be one widget tree switched by CSS alone? That would be the
cheapest possible implementation and the smallest possible rebase surface.

**Finding**: No. It is arithmetically impossible to satisfy FR-020 ("no residual difference" in
horizontal) with a single tree.

Vertical requires the scope pane and the record list to be *grouped*, because the preview band spans
the full width beneath both of them (FR-016, and the issue's sketch, where the divider runs the whole
width). So the tree must contain a container holding `scope + list`. Call it `#upper-band`.

In horizontal, today's geometry (`app.tcss:16-29`) is:

```
scope   = 14 (fixed)
list    = 2fr  of the remaining width
preview = 3fr  of the remaining width
```

so with a body of width `W`: `list = (2/5)(W - 14)` and `preview = (3/5)(W - 14)`.

If the same grouped tree is reused in horizontal — `#body` horizontal, containing `#upper-band` and
`#preview-pane` — then `#upper-band` would need width `14 + (2/5)(W - 14) = (2/5)W + 8.4`. That is
not a fixed fraction of `W`: it depends on `W`. No static `fr` value can express it, and Textual CSS
has no `calc()`. Setting `#upper-band: 2fr` / `#preview-pane: 3fr` instead moves the pane boundaries
by ~8 columns at `W = 80` — a visible change to today's layout, which FR-020 forbids.

**Decision**: The widget tree differs between orientations. `#body` composes its children based on the
effective orientation.

**Consequence that makes this cheap**: in horizontal, `#body` composes *exactly the tree it composes
today*. FR-020 is then satisfied by construction rather than by matching numbers — there is no
horizontal geometry to get wrong, because none of it changes.

**Alternatives considered**:

- *Single tree, compensating widths set imperatively on every resize* (compute
  `#upper-band.styles.width = 14 + 2*(W-14)//5` in `on_resize`). Rejected: it fights the CSS engine
  for the layout it is already good at, puts geometry in an event handler where `columns.py` proves it
  does not need to be, and would leave horizontal's appearance depending on rounding code that today
  does not exist.
- *Scope pane as a sibling of a `(list, preview)` group* — one tree that does work for horizontal.
  Rejected: in vertical it renders the scope pane spanning the full height on the left with the
  preview only as wide as the list column, which is not the layout the issue asks for.

---

## R2: `recompose()` is the switch mechanism, and it is awaitable

**Question**: Given R1, how does a mounted screen change its subtree without being torn down and
re-pushed (which would violate FR-026's "no second screen" and lose the screen's state)?

**Finding**: `Widget.recompose()` exists in `textual==8.2.8`
(`site-packages/textual/widget.py:1704`) and does exactly this:

```python
async def recompose(self) -> None:
    """Recompose the widget.
    Recomposing will remove children and call `self.compose` again to remount.
    """
```

Two properties matter:

1. **It is a coroutine that can be awaited directly.** The alternative entry point,
   `refresh(recompose=True)` (`widget.py:4329,4358-4360`), only sets `_recompose_required` and defers
   via `call_next`, so the caller cannot know when the new children exist. Awaiting `recompose()`
   gives a deterministic point after which `query_one` finds the new widgets — which is what lets the
   repopulate step run immediately, and what makes the tests deterministic rather than
   `pause()`-dependent.
2. **It is scoped to the widget it is called on.** Calling it on `#body` rebuilds the panes and leaves
   `CollectionBar` and `#bottom-bar` — and therefore `CommandBar`, `StatusBar`, and `LinkPicker` —
   untouched. Recomposing the whole `ListScreen` instead would destroy the command bar while it is
   mid-dispatch of the very message that triggered the switch.

**Decision**: `await self.query_one("#body").recompose()`, never a screen-level recompose, never a
`push_screen`.

**Consequence**: the panes are new widget instances after a switch, so their contents must be
repopulated. This is not new machinery: `on_screen_resume` (`list_screen.py:325-351`) already
rebuilds exactly this state when returning from a full-screen editor, using
`_refresh_scope_pane()` + `refresh_rows(select_id=...)`. The switch reuses that path.

**Accepted limitation**: the preview's *scroll position* is not preserved across a switch, because
the `Markdown` widget is rebuilt. The spec promises the same record is shown (FR-022), not the same
scroll offset. Recording it here so it is a known accepted cost rather than a bug report later.

---

## R3: Where the switch is performed in the message sequence

**Question**: `/config view vertical` arrives as a message. At what point is it safe to rebuild the
panes?

**Finding**: `CommandBar._on_submitted` (`command_bar.py:104-109`) posts the verb's message and *then*
calls `self.close()`, which posts `Closed`. So the ordering on the screen is:

1. `ConfigRequested` → `_on_config_requested` (`list_screen.py:953-955`), which today stores the
   returned status string in `self._pending_error`.
2. `Closed` → `_on_command_bar_closed` (`list_screen.py:966-973`), which renders that status and
   focuses `#meeting-list`.

Because the command bar lives in `#bottom-bar` and the recompose is scoped to `#body` (R2),
performing the switch in step 1 does not touch the bar that is still closing. Step 2 then runs
against the rebuilt tree: its `query_one("#meeting-list", ListView).focus()` resolves to the new list
view, which satisfies FR-023 (focus lands on the record list, by the existing rule, with no new focus
logic).

**Decision**: perform the switch in `_on_config_requested`, which becomes `async`. No reordering of
messages, no new message type, and the existing `Closed` handler needs no change.

**Alternatives considered**: a deferred `_pending_orientation` flag consumed by
`_on_command_bar_closed`. Rejected as strictly more state for no benefit — it exists only to solve an
ordering problem that scoping the recompose to `#body` already removes.

---

## R4: The per-user preferences location

**Question**: FR-007 through FR-011 require a per-user store outside every workspace. Where exactly,
on each platform?

**Decision**:

| Platform | Directory | Resolution order |
|---|---|---|
| Windows | `%LOCALAPPDATA%\choom\` | `LOCALAPPDATA`, then `APPDATA`, then `~\AppData\Local` |
| macOS, Linux | `$XDG_CONFIG_HOME/choom/` or `~/.config/choom/` | `XDG_CONFIG_HOME` if set and absolute, else `~/.config` |

File: `preferences.toml`. Key: `[view] orientation = "vertical" | "horizontal"`.

**Rationale, Windows — Local, not Roaming.** `%APPDATA%` roams: on a managed corporate machine it
syncs to every other machine the user signs into. The preference being stored is shaped by *one
monitor* — that is the entire premise of the issue. Roaming it would carry an ultrawide user's
vertical layout onto their 13" laptop, which is a smaller replay of the cross-user problem the spec's
"Decision" section exists to prevent. `%LOCALAPPDATA%` is per-user *and* per-machine, which is the
correct scope for a display preference.

**Rationale, POSIX — one path for both.** `~/Library/Application Support/choom/` is the strict macOS
convention, but it buys nothing here and costs a longer path containing a space. `~/.config/choom/`
is what the terminal tools this user already runs use, keeps macOS and Linux on a single code path
(Principle III), and honouring `XDG_CONFIG_HOME` is free. This is a preference, not derived state, so
`XDG_CONFIG_HOME` is the right XDG variable rather than `XDG_STATE_HOME`.

**Platform constraints checked** (constitution, Platform & Distribution Constraints):

- *Windows path length*: `C:\Users\<user>\AppData\Local\choom\preferences.toml` is ~52 characters for
  a typical username. The workspace-root 260-character worry does not apply — this path is not built
  from the workspace root, which is the long OneDrive path the constraint is about.
- *No admin rights*: both locations are inside the user's own profile. No elevation, no installer, no
  registry.
- *No network*: a local file read and write.
- *Spaces and non-ASCII in the path*: the profile directory may contain both (`C:\Users\José García`).
  Everything goes through `pathlib` and `write_text_atomic`, which already handle this; the existing
  `tests/integration/test_unicode_paths.py` is the established home for proving it.

**Alternatives considered**:

- *`platformdirs`*. Rejected: Principle III requires every third-party dependency to be justified by
  what it costs to do without, and doing without is roughly eight lines of `os.environ.get` with a
  fallback. The repo currently has no runtime dependency beyond `textual`.
- *`~/.choom/preferences.toml`*. Rejected: a dotfile in the home root is the convention this repo has
  already declined to follow, and it ignores the Windows profile layout entirely.
- *Reusing `discovery.profile_root()`*. Rejected: that function means "the user's profile directory,
  where an assistant keeps its own config", and its every caller is about assistant discovery files.
  Overloading it would couple two unrelated features to one seam and make the autouse test fixture's
  intent ambiguous.

---

## R5: The single overridable resolver, and how tests are kept off a real profile

**Question**: How is the store redirected in tests so no test can write into a developer's real
profile (FR-009)?

**Finding**: the pattern already exists and is documented in `tests/conftest.py:20-52`. The autouse
`_isolated_profile_root` fixture does *two* things, and the docstring explains why both are needed:

- `monkeypatch.setattr(discovery, "profile_root", lambda: root)` — covers in-process tests.
- `monkeypatch.setenv("HOME", ...)` and `setenv("USERPROFILE", ...)` — covers the `tests/contract/`
  tests that run choom as a real child process (`subprocess.run([sys.executable, "-m", "choom", ...])`),
  which get a fresh interpreter that never sees the patched symbol.

**Decision**: mirror it exactly. `src/choom/core/preferences.py` gets **one** function,
`preferences_root() -> Path`, which is the only place in the module that reads an environment variable
or calls `Path.home()`. Every other path in the module is built from its return value.

The autouse fixture is extended to redirect it on both levels:

- `monkeypatch.setattr(preferences, "preferences_root", lambda: root)`, and
- `monkeypatch.setenv` for `LOCALAPPDATA`, `APPDATA`, and `XDG_CONFIG_HOME`, alongside the `HOME` and
  `USERPROFILE` it already sets — so a subprocess cannot reach a real profile either.

This is a change to a shared autouse fixture, so it is called out as a task in its own right rather
than folded into another one.

---

## R6: Reading and writing the preference — never fatal, never destructive

**Question**: What is the read/write contract, given FR-011 (tolerate anything) and FR-012 (do not
destroy other content)?

**Finding**: `core/config.py` already solves this problem for the workspace config and its solution
transfers directly.

- **Reading**: `get_assistant` (`config.py:21-38`) catches `OSError` and `tomllib.TOMLDecodeError`,
  checks the table is a `dict`, and returns `None` for any value that is not a legal setting — the
  docstring states outright that "a hand-edited config must not stop choom from opening (Principle
  IV)". `get_view_orientation` follows the same shape, returning `"horizontal"` for every failure
  mode.
- **Writing**: `_write_assistant_key`/`_apply_assistant_key` (`config.py:89-142`) do a line-targeted
  edit that preserves comments, key order, and unknown keys, and detect CRLF so a Windows-edited file
  keeps its line endings. FR-012 asks for the same guarantee.
- **Atomicity and directory creation**: `write_text_atomic` (`core/atomic_write.py:19-46`) writes via
  a same-directory temp file plus `os.replace`, and — usefully — already does
  `path.parent.mkdir(parents=True, exist_ok=True)`. FR-010's "create whatever per-user directory it
  needs" therefore requires no new code.

**Decision**: `preferences.py` reuses `write_text_atomic` and mirrors `config.py`'s read-edit-write
shape.

**Deliberately not done**: generalising `config.py`'s `_apply_assistant_key` into a shared
"edit one key in one TOML table" helper used by both modules. It is tempting and it is the wrong call
right now — the two modules write different files with different failure semantics (a workspace
config failure is a `WorkspaceError` the caller surfaces; a preferences failure must be swallowed into
a status line per FR-013), and issue #43 is in flight over adjacent code. A shared helper is a
sensible follow-up once both callers are settled, not a thing to introduce underneath a parallel
feature. Noted rather than done.

---

## R7: The fallback threshold — height-only, and derived rather than picked

**Question**: FR-031 through FR-036 require a short-terminal fallback with a written-down threshold.
What is the number, and where does it come from?

**Finding**: the number falls out of the minimums the spec already states, once the chrome is counted
from `app.tcss`.

Vertical mode's fixed overhead, at rest:

| Row cost | Source |
|---|---|
| 1 | `CollectionBar { dock: top; height: 1 }` (`app.tcss:5-9`) |
| 1 | `StatusBar { height: 1 }` inside the docked `#bottom-bar` (`app.tcss:45-48, 99-102`) |
| 1 | the divider between the two bands (`border-top` on the preview band, matching the existing `border-right: solid $accent` idiom) |

The two bands' minimums, from FR-032:

| Band | Minimum | Composition |
|---|---|---|
| upper | 4 | `#list-header` (1) + 3 record rows |
| lower | 4 | 4 lines of preview content |

**Therefore**:

```
MIN_VERTICAL_SCREEN_HEIGHT = 1 (collection bar)
                           + 1 (status bar)
                           + 1 (divider)
                           + 4 (upper band: header + 3 rows)
                           + 4 (lower band: 4 content lines)
                           = 11
```

**The split itself needs no arithmetic.** Give both bands `height: 1fr` and Textual divides what is
left. This is self-consistent with the threshold rather than a second, independent rule: at exactly
11 rows, `1fr`/`1fr` over the 8 remaining rows yields 4 and 4 — precisely both minimums. One row
shorter and one of them is violated, which is the definition of the threshold. So the constant is
*derived from* the split rule, not bolted beside it.

Sanity check at the required size, 80x24: `24 - 3 = 21` to divide, giving bands of 11 and 10. The
record list shows its header plus 10 rows, the preview shows 10 lines. FR-031 is met with room to
spare.

**Height only, deliberately.** The threshold reads `screen.size.height` and nothing else:

- not width — FR-035, and because width degradation is already handled independently and identically
  in both orientations by `column_widths` (`columns.py:54`), `CollectionBar._render_bar`
  (`collection_bar.py:87`), and `shorten_workspace_path`;
- not the *currently available* body height — because `CommandBar` (1 row when shown), `LinkPicker`
  (up to 8, `app.tcss:73-77`), and the backlinks section all shrink the body when they open. Reading
  available height instead of screen height would let opening the command bar flip the whole layout
  underneath the user mid-keystroke. This is the concrete failure FR-035 exists to prevent, and
  reading `screen.size.height` is what prevents it.

**Decision**: `MIN_VERTICAL_SCREEN_HEIGHT = 11` in a new `src/choom/tui/layout.py`, with the
derivation above written into its comment as component constants that add up, not as a bare literal.
Precedent for the constant's placement and style: `MIN_PICKER_SCREEN_HEIGHT = 12`
(`edit_screen.py:74`), which is likewise a screen-height gate for a bottom-region widget.

---

## R8: Where the geometry logic lives (Principle I)

**Question**: Does the threshold logic belong in `choom.core`?

**Finding**: No, and `columns.py` is the precedent that settles it. Its module docstring states the
rule this repo already follows:

> Pure functions of a width, with no widget imports, so the layout math -- which of the four columns
> fit, how wide each is, where truncation kicks in -- is unit-testable without a terminal (research R8).

So the repo's established position is that *layout arithmetic is interface code that happens to be
pure*, and it earns its testability by having no widget imports rather than by living in `core`.
`core` holds no pane, no row, and no notion of a screen, and putting a function about band heights
there would make `core` know about a terminal — the exact inversion Principle I forbids.

**Decision**: `src/choom/tui/layout.py`, pure, no widget imports, unit-tested directly. `core` gets
the setting's storage and validation and nothing else.

---

## R9: What the stylesheet must and must not touch

**Question**: This feature rewrites pane geometry, and the diff will be easy to over-reach in. Which
selectors are in scope?

**Finding**: `app.tcss` is 144 lines covering the list screen, the editor, the link picker, dialogs,
and the help screen. Only the body's own selectors are in range.

**May change** (all by *adding* a `#body.-vertical …` variant; base rules are left alone so horizontal
is untouched per FR-020):

| Selector | Change |
|---|---|
| `#body` | new `#body.-vertical { layout: vertical; }` variant beside the existing rule |
| `#upper-band` | **new** — `height: 1fr; layout: horizontal` |
| `#list-pane` | vertical variant drops `border-right` (it is the rightmost pane in the upper band) |
| `#preview-pane` | vertical variant: full width, `height: 1fr`, `border-top` instead of participating in the `fr` row |
| `#preview-links-section` | vertical variant bounding it relative to the band, per FR-043 |

**Must not change** — anything here appearing in the diff is scope creep:

`Screen`, `CollectionBar`, `#scope-pane`'s base width and border, `#scope-list`, `#list-header`,
`#meeting-list`, `#bottom-bar`, `CommandBar` and its three child rules, `StatusBar`, `#link-picker`,
`#links-section`, `#links-list`, `#preview-links-list`, `#editor`, `EditorPane`, `#confirm-dialog`,
`ConfirmDialog`, `HelpScreen`, `#help-pane`, `#help-body`.

**Note on `#preview-links-section`.** Its current bound is `max-height: 12` (`app.tcss:50-55`) with
the inner list at `max-height: 10`. In horizontal the preview pane is full body height, so 12 rows is
a modest slice. In vertical at 80x24 the lower band is ~10 rows — so the *existing* constant would
consume the entire band and leave no preview visible. This is the regression FR-043 exists to prevent
and it is invisible from the issue's sketch; it is only findable by reading the stylesheet against
the new band height. The vertical variant bounds the section as a fraction of its container instead
of as a fixed row count.

---

## R10: Interaction with the inline editor and the link picker

**Question**: Both render in the region this feature relocates. What actually changes for them?

**Finding**: less than it appears, and the reason is structural.

- **The inline editor** is mounted into `#preview-pane` by id
  (`list_screen.py:246`: `self.query_one("#preview-pane").mount(self._editor_pane)`). Because the id
  survives into the vertical tree, that line needs no change at all — the editor lands in whichever
  region currently carries that id. Everything 014 specifies (list and scope stay visible, the footer
  swaps, `#preview` is hidden and restored) is expressed in terms of the same ids and holds unchanged.
- **Wrapping** (014 FR-004/FR-005) is already required to follow the pane's current width and to
  re-wrap on resize. Vertical makes the region wider; the requirement is unchanged and already
  covered.
- **The link picker** is composed into `#bottom-bar` (`list_screen.py:215-218`), which this feature
  does not touch. Its position, its bounds, and its `MIN_PICKER_SCREEN_HEIGHT` screen-height fallback
  (`edit_screen.py:74,745`; `link_picker.py:136`) are all unchanged. FR-035's height-only threshold is
  what guarantees opening it cannot flip the orientation.
- **FR-025** (no orientation change while an editor is open) is *already true for the command path*
  and needs no new guard there: 014 FR-008 makes the command bar unopenable while the inline editor is
  open, so `/config view` is unreachable mid-edit. The guard is needed only on the **resize** path,
  where a terminal resize could otherwise cross the threshold while an editor pane is mounted. That is
  one condition — `self._editor_pane is not None` — in the resize handler, and it is a real
  requirement rather than a defensive one: recomposing `#body` while the editor is a child of
  `#preview-pane` would destroy the editor and the user's unsaved buffer with it. **This is the
  data-loss risk in the feature**, and the guard is what closes it.

---

## R11: Test sizing and the boundary cases

**Question**: How are terminal sizes exercised, and what must be covered?

**Finding**: `App.run_test(size=(cols, rows))` is the established mechanism;
`tests/integration/test_narrow_terminal_tui.py` already uses `size=(20, 24)`, `(10, 24)`, and
`(40, 24)`, and 014's research names it as "the established home" for narrow-terminal cases. Note
that every existing size is a *width* variation at a fixed 24 rows — this feature is the first to
care about height, so the boundary cases below are genuinely new coverage rather than a re-run.

**Decision** — required sizes, driven by what can break rather than by scenario count:

| Size | What it proves |
|---|---|
| `(80, 24)` | FR-031, the coordinator's smoke-test size: vertical is usable, header + ≥3 rows, ≥4 preview lines |
| `(120, 40)` | the comfortable case, and the second size the coordinator smoke-tests |
| `(80, 11)` | exactly `MIN_VERTICAL_SCREEN_HEIGHT` — vertical still renders, both minimums exactly met |
| `(80, 10)` | one row below the threshold — the fallback engages |
| `10 → 11` | resize upward reverses the fallback with no command typed (FR-033) |
| `24 → 10 → 24` | round trip, and the stored preference is unchanged afterwards (FR-034) |
| `(20, 24)` vertical | width degradation is identical to horizontal (FR-039) |

The `(80, 11)` / `(80, 10)` pair is the boundary in both directions, which is the part that a single
"it degrades" test would miss and the part most likely to rot if the constant is ever edited.

---

## R12: Reading the preference at startup

**Question**: Where does the orientation enter the application?

**Finding**: `_run_tui` (`cli/main.py:233-250`) resolves the workspace, then constructs
`ChoomApp(workspace)` inside the `terminal_title` context manager. `ChoomApp.__init__`
(`app.py:84-113`) already establishes every other piece of session state (`self.active`,
`self.month_scope`, `self.task_category`, …).

**Decision**: `ChoomApp.__init__` reads the preference once into `self.view_orientation`, alongside
the rest of the session state. `_run_tui` needs no change. This satisfies the spec's "nothing watches
the file" assumption by construction — there is one read, at startup.

The screen asks the app for the *effective* orientation (the stored value, resolved against the
current screen height per R7), rather than reading the stored value directly, so the fallback is
applied in exactly one place.

---

## R13: Rebase posture against `019-completed-tasks-partition`

**Question**: Issue #43 is in flight in parallel and will touch `list_screen.py`. How is the conflict
surface kept small?

**Finding**: 019 changes what the **scope pane offers for Tasks** (a Done partition). Its edits
concentrate in `ScopePane.show_categories`, `app.task_category`, and `refresh_rows`' task branch.
This feature touches `compose`, `_on_config_requested`, `on_resize`, and adds a switch helper — and
changes no line concerning what the scope pane *contains*.

**Decision**: keep it that way deliberately.

- The new geometry lives in a new file (`tui/layout.py`) and new CSS rules, neither of which 019 can
  touch.
- `compose` is the one genuinely shared hunk. Keeping the vertical branch to a small, contiguous block
  — rather than restructuring the whole method — keeps that conflict to a few lines.
- No task in this feature edits `ScopePane`, `show_categories`, `task_category`, or the task branch of
  `refresh_rows`.
- The switch reuses `_refresh_scope_pane()` and `refresh_rows(select_id=...)` **through their existing
  signatures**, so whatever 019 changes inside them is inherited rather than conflicted with.

No coordination with that branch, and nothing read from it, per the scheduling note.

---

## Resolved unknowns

Every `NEEDS CLARIFICATION` from the Technical Context is resolved above: the storage location (R4),
the resolver and its test seam (R5), the read/write semantics (R6), the threshold and its derivation
(R7), the layer each piece belongs to (R8), the stylesheet's blast radius (R9), and the switch
mechanism (R1, R2, R3). No open questions remain for Phase 1.
