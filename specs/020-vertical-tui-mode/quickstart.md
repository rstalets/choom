# Quickstart: validating the vertical layout

**Feature**: `020-vertical-tui-mode` | **Plan**: [plan.md](./plan.md)

How to prove this feature works, end to end. Automated coverage first, then the manual checks that
only a real terminal can settle.

---

## Prerequisites

```bash
uv sync
```

A scratch workspace to poke at (the `demo` skill builds a richer one, but this is enough):

```bash
mkdir -p /tmp/choom-vertical && cd /tmp/choom-vertical
uv run choom init
uv run choom meeting "quarterly planning"
uv run choom note "thoughts on the renewal"
uv run choom task "call Terry"
```

---

## Automated

Everything, the way CI runs it:

```bash
scripts/dev-tests.sh
```

The feature's own suites:

```bash
scripts/dev-tests.sh tests/unit/test_preferences.py
scripts/dev-tests.sh tests/unit/test_layout.py
scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py
scripts/dev-tests.sh tests/integration/test_narrow_terminal_tui.py
```

The threshold in both directions — the pair most likely to rot if the constant is ever edited:

```bash
scripts/dev-tests.sh tests/unit/test_layout.py -k boundary
```

Gates:

```bash
uv run ruff format --check . && uv run ruff check . && uv run mypy
```

### What the automated tests must establish

| Area | Assertion |
|---|---|
| Preference read | All eight rows of the read table in [contracts/core-api.md](./contracts/core-api.md) return a legal value and never raise |
| Preference write | Comments, key order, unknown keys and unknown tables survive; CRLF preserved; illegal value writes nothing |
| Resolver | A relative or empty env var is ignored rather than resolving inside the workspace |
| Threshold | `effective_orientation` at heights 10 and 11, for both stored values |
| Derivation | `MIN_VERTICAL_SCREEN_HEIGHT == 11` **and** equals the sum of its five components |
| Switch | Collection, scope, filter, highlighted record, preview contents, backlinks-expanded all survive |
| Focus | Lands on `#meeting-list` after the switch |
| Resize guard | A resize crossing the threshold with a **dirty** editor open does not recompose and does not lose the buffer |
| Sizes | `(80,24)`, `(120,40)`, `(80,11)`, `(80,10)`, and the `10→11` and `24→10→24` transitions |
| Workspace untouched | No file under the workspace changes across a switch |

---

## Manual — the interactive checks

`scripts/dev-tests.sh` cannot see a terminal's shape. Constitution: TUI changes are verified before
release on the terminals in `docs/REQUIREMENTS.md` §4.3.

### 1. The switch (US1)

```bash
cd /tmp/choom-vertical && uv run choom
```

- Highlight a record and read its preview.
- Type `/config view vertical`, press enter.
- **Expect**: collection bar across the top; scope list and record list side by side in the upper
  band; preview full width beneath them; status bar across the bottom. **Same record still
  highlighted, same preview showing.**
- Move with `↑`/`↓` — the preview follows.
- Press `h` then `l` — focus moves between the scope list and the record list.
- Type `/config view horizontal` — today's three panes are back, with no residual difference.

### 2. It is remembered, and it is yours (US2)

- With vertical set, `ctrl+q`, then relaunch. **Expect** vertical, no command typed.
- `cd` to a *different* workspace and launch. **Expect** vertical there too — the preference follows
  the person, not the vault.
- Confirm the workspace is untouched:

  ```bash
  cd /tmp/choom-vertical && git status --porcelain 2>/dev/null; ls -la .choom/
  cat .choom/config.toml     # must contain NO [view] table
  ```

- Confirm where it actually went:

  ```bash
  cat "${XDG_CONFIG_HOME:-$HOME/.config}/choom/preferences.toml"   # macOS / Linux
  # Windows: type %LOCALAPPDATA%\choom\preferences.toml
  ```

### 3. Nothing else changed (US3)

In vertical:

- `enter` on a document → full-screen reading view takes the whole window; `esc` returns to vertical
  with the same record highlighted.
- `e` → editor appears **in the lower band**, list and scope still visible above; footer swaps to the
  editor's bindings. Save; the preview returns and the row is still highlighted.
- `e` from inside the full-screen view → full-screen editor; leaving returns to vertical.
- `b` on a record with backlinks → the list appears at the bottom of the lower band **and some
  preview is still visible above it**. This is the regression FR-043 exists for; if the backlinks
  section fills the whole band, the vertical bound is wrong.
- Read the footer in each state and compare against horizontal — the text must be identical.

### 4. Short terminals (US4)

Resize the window rather than trusting the tests:

| Size | Expect |
|---|---|
| 120x40 | comfortable; both bands generous |
| 80x24 | usable: column header + several rows above, several preview lines below |
| 80x11 | still vertical, bands at their minimum (header + 3 rows / 4 lines) |
| 80x10 | **horizontal**, no error, no dialog, highlight intact |
| back to 80x24 | vertical returns with nothing typed |

Then: with the terminal short and the fallback in effect, run `/config view` — the report must say the
setting is vertical **and** that horizontal is in effect because the terminal is too short. Quit,
enlarge the terminal, relaunch: vertical. The fallback must never have rewritten the setting.

Also: `/config view vertical` while the terminal is too short must still save, and say so.

Narrow rather than short — 20 columns in vertical: labelled columns drop, the collection bar compacts,
the path elides, exactly as in horizontal. Width must not trigger the fallback.

### 5. The data-loss guard (US3 / FR-025)

The one that matters most:

- In vertical, press `e` on a record and **type something without saving**.
- Now resize the terminal below 11 rows and back.
- **Expect**: the editor is still open and still holds the typed text. The layout must **not** have
  flipped while the editor was open.

### 6. Errors (US5)

| Type | Expect |
|---|---|
| `/config view sideways` | names `sideways` and both accepted values; layout unchanged |
| `/config view` | current setting and accepted values |
| `/config layout vertical` | names `layout` as unknown **and** lists `assistant, view` |
| `/help` | the `/config` entry covers both settings and both of `view`'s values |

Unwritable-store case:

```bash
chmod -w "${XDG_CONFIG_HOME:-$HOME/.config}/choom"
```

`/config view vertical` must still switch the layout for the session and report that the preference
could not be saved. Restore with `chmod +w` afterwards.

---

## Cross-platform

| Check | Where |
|---|---|
| `%LOCALAPPDATA%\choom\preferences.toml` is the location, and roaming `%APPDATA%` is **not** used | Windows Terminal |
| Path with spaces and non-ASCII in the profile directory | any; `tests/integration/test_unicode_paths.py` is the automated home |
| No admin rights, no network needed | Windows managed machine |
| Vertical renders correctly | Windows Terminal, iTerm2, macOS Terminal, PuTTY, tmux |

---

## Teardown

```bash
rm -rf /tmp/choom-vertical
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/choom/preferences.toml"
```
