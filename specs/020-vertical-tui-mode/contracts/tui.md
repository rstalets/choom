# Contract: the TUI surface

**Feature**: `020-vertical-tui-mode` | **Files**: `tui/app.py`, `tui/list_screen.py`, `tui/commands.py`

---

## C1: The command

`/config view [<value>]`, handled by `ChoomApp.handle_config_command` (`app.py:382`), which today
recognises only `assistant`.

| Input | Result | Written? |
|---|---|---|
| `/config view vertical` | Layout switches; message confirms | Yes |
| `/config view horizontal` | Layout switches; message confirms | Yes |
| `/config view` | Reports current setting and accepted values | No |
| `/config view sideways` | Error naming the value and both accepted values | **No** |
| `/config view VERTICAL` | Error — matching is exact and case-sensitive | **No** |
| `/config layout vertical` | Error naming the unknown setting and the settings that exist | **No** |

### Message wording

Following the existing idiom in `handle_config_command` and `set_assistant`, so the two settings read
as one command rather than two:

| Case | Message |
|---|---|
| Set succeeded | `view set to vertical` |
| Set succeeded, terminal too short (FR-038) | `view set to vertical; terminal is too short — horizontal is in effect until it is at least 11 rows tall` |
| Set failed to persist (FR-013) | `view set to vertical for this session; could not save the preference: <reason>` |
| Get, no fallback | `view: vertical; accepted: horizontal, vertical` |
| Get, unset | `view: horizontal (default); accepted: horizontal, vertical` |
| Get, fallback in effect (FR-037) | `view: vertical, but horizontal is in effect — the terminal is too short; accepted: horizontal, vertical` |
| Illegal value (FR-044) | `view must be one of horizontal, vertical; got 'sideways'` |
| Unknown setting (FR-045) | `unknown setting: 'layout'; known settings: assistant, view` |

The illegal-value line matches `set_assistant`'s existing
`assistant must be one of claude, copilot, none; got 'x'` exactly in shape.

The unknown-setting line **changes an existing message**: `app.py:389` currently returns a bare
`unknown setting: 'layout'`, which names what went wrong but not what to do instead. Principle V
requires both, and a second setting is what makes the list worth printing. This is the one existing
string this feature edits.

All messages go to the status bar through the existing `_pending_error` → `_on_command_bar_closed`
path. **No dialog, no prompt, no confirmation** (FR-047) — a layout switch discards nothing, and a
confirmation with nothing to lose is the reflex-dismissal trap Principle V names.

---

## C2: Discoverability

`commands.py:24`'s verb entry currently reads:

```python
Verb("config", None, "assistant <claude|copilot|none>", "Set which AI assistant /ai calls")
```

It must cover both settings and both of `view`'s values (FR-046), since `VERB_TABLE` is what
`HelpScreen._render_body` prints. The description column is what the user reads to find the command,
so it names the settings rather than one setting's values.

No new verb is registered. `/config` already exists.

---

## C3: The switch

| Property | Requirement |
|---|---|
| Mechanism | `await self.query_one("#body").recompose()` |
| Never | `push_screen`, `pop_screen`, or a screen-level recompose (FR-026) |
| Scope | `#body` only — `CollectionBar` and `#bottom-bar` are untouched, so the command bar mid-dispatch is safe (research R2, R3) |
| Immediacy | Effective on the same keystroke; no restart, no reopen (FR-004) |
| Persistence | Written at the moment the command succeeds, not at exit (FR-005) |
| Idempotence | Setting the value already in effect rearranges nothing and reports the same confirmation |

### What survives (FR-021, FR-022, FR-023)

| State | How |
|---|---|
| Active collection | `app.active` is app state; the recompose does not touch it |
| Selected scope (month / `Unfiled` / task category) | `app.scope_selection`; restored by `_refresh_scope_pane()` |
| Filter term and matched rows | `app.filter_query`; `refresh_rows` re-derives |
| Highlighted record | captured before the recompose, passed as `refresh_rows(select_id=...)` |
| Preview contents | `_update_preview()` inside `refresh_rows` |
| Backlinks expanded | `_preview_links_expanded` is screen state; re-applied after the recompose |
| Focus | `_on_command_bar_closed` focuses `#meeting-list`, **unchanged** |

Every mechanism above already exists and runs on every return from a full-screen editor
(`on_screen_resume`, `list_screen.py:325-351`). Nothing is invented for this feature.

### Not preserved

The preview's **scroll offset**, because the `Markdown` widget is rebuilt. The spec promises the same
record (FR-022), not the same scroll position. Accepted; recorded in research R2.

---

## C4: The resize path

`ListScreen.on_resize` (`list_screen.py:288`) today only calls `_rerender_columns()`. It gains one
decision, in this order:

```
1. if self._editor_pane is not None:      → columns only, never recompose      (FR-025)
2. if effective orientation unchanged:    → columns only, as today
3. otherwise:                             → recompose + repopulate, then columns
```

**Step 1 is a data-loss guard, not defensive coding.** Recomposing `#body` while an `EditorPane` is
mounted inside `#preview-pane` would remove the editor and the user's unsaved buffer with it. This is
the one place in the feature where a mistake loses the user's words (Principle IV), and it gets its
own integration test rather than inspection.

The command path needs no equivalent guard: 014 FR-008 makes the command bar unopenable while the
inline editor is open, so `/config view` is unreachable mid-edit (research R10).

---

## C5: Bindings and footer — unchanged

| Assertion | FR |
|---|---|
| No binding added, removed, or changed | FR-027 |
| `h`/`l` still move focus between scope pane and record list | FR-027 |
| Footer text identical per state in both orientations | FR-028 |
| Orientation never appears in the footer | FR-028 |
| `ctrl+c` unbound; `ctrl+q` untouched | Principle V |

`LIST_HELP`, `TASK_LIST_HELP`, `PREVIEW_HELP`, `LINKS_SECTION_HELP`, `EDIT_HELP`, and
`LINK_PICKER_HELP` (`status_bar.py:10-26`) are **not edited by this feature**. `h/l pane` stays
accurate because the two panes stay left-and-right of each other in both arrangements.

---

## C6: Regions that ride along

| Component | Contract |
|---|---|
| Inline editor | Mounts into `#preview-pane` by id (`list_screen.py:246`) — **that line does not change**, because the id exists in both trees. All of 014 holds unchanged. |
| Editor wrapping | Already required to follow the pane's current width and re-wrap on change (014 FR-004/FR-005). Vertical makes it wider; no new requirement. |
| Link picker | Composed into `#bottom-bar`, which this feature does not touch. Position, bounds, and `MIN_PICKER_SCREEN_HEIGHT` fallback all unchanged (FR-042). |
| Backlinks section | Stays docked to the bottom of `#preview-pane`; gains a vertical bound so it cannot swallow the band (FR-043, contracts/layout.md). |
| Full-screen view / editor | Untouched. Take the whole window; return to the configured layout on exit (FR-029). |

---

## C7: Startup

`ChoomApp.__init__` reads the preference once into `self.view_orientation` (research R12).
`cli/main.py:_run_tui` is **not modified**.

The screen asks for the *effective* orientation rather than reading the stored value, so the fallback
is applied in exactly one place and the stored value stays intact for the `/config view` report and
for the next launch.

---

## C8: Out of contract

- **No CLI surface.** `cli/main.py` is not modified; no subparser, no `--json` key, no exit code
  (gate II, FR-030).
- **No new message type**, no new `CommandBar` message class. `ConfigRequested` already carries the
  full argument string.
- **No watcher.** One read at startup; a second running session is unaffected until its next launch.
