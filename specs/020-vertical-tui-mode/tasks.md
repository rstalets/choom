---

description: "Task list for 020-vertical-tui-mode"
---

# Tasks: Vertical Layout for a Half-Width Window

**Input**: Design documents from `/specs/020-vertical-tui-mode/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Included, and **not** as a trailing phase. Every behaviour change lands with the tests that
cover it, in the same task — Constitution Principle VI and the Development Workflow gate. There is no
"write the tests afterwards" step in this list, deliberately.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different file, no dependency on an incomplete task
- **[Story]**: which user story the task serves (US1–US5); Setup, Foundational, and Polish carry none
- Every task names the file it touches and the command that verifies it

## Path Conventions

Single project: `src/choom/{core,cli,tui}` over `tests/{unit,contract,integration}`. Tests run through
`scripts/dev-tests.sh`, never a hand-rolled `pytest` invocation.

---

## The one way this feature loses the user's words

**A terminal resize must never recompose `#body` while an inline editor is open.**

The switch mechanism is `await self.query_one("#body").recompose()`, and
`src/choom/tui/list_screen.py:246` mounts the inline editor *into* `#preview-pane`:

```python
self.query_one("#preview-pane").mount(self._editor_pane)
```

`recompose()` removes every child and re-runs `compose()`. So a recompose while the editor is mounted
removes the editor **and the unsaved buffer inside it**, with no confirmation and no way back. The
user did not press a key; they resized a window.

The command path is safe for free — 014 FR-008 makes the command bar unopenable while the inline
editor is open, so `/config view` is unreachable mid-edit. That is a nice property and it is also the
trap: it means the `on_resize` guard is the **single** thing standing between a resize and lost work,
with no second line of defence behind it.

T021 owns that guard, alone, and T022 proves it is load-bearing rather than vacuously passing. Neither
is allowed to be folded into a layout task.

---

## Scope fence — `019-completed-tasks-partition` implements first

Issue #43 lands before this feature and touches `list_screen.py` for its Done view. **No task in this
list may touch** `ScopePane`, `show_categories`, `task_category`, or the task branch of
`refresh_rows`. The new geometry lives in a new `tui/layout.py` and new `-vertical` CSS variants
precisely so it cannot collide; `compose` is the one genuinely shared hunk, and T011 keeps the vertical
branch to a small contiguous block rather than restructuring the method. T032 verifies the fence held.

Expect to rebase onto `origin/release/v0.0.4` before implementing. Do not read from or coordinate with
that branch.

---

## Phase 1: Setup

**Purpose**: establish a green baseline before anything moves.

- [ ] T001 Confirm the baseline is green before changing anything: run `scripts/dev-tests.sh` from the
      repository root and record the pass count. Also run
      `uv run ruff format --check . && uv run ruff check . && uv run mypy`. Do not start T002 on a red
      tree — a pre-existing failure attributed to this feature wastes the whole gate

---

## Phase 2: Foundational

**Purpose**: the setting and the geometry. **Blocks every user story.**

**Ordering note that matters**: T002 creates the module, T003 isolates it in the test harness, and only
then does T004 write the first preference in a test. Getting that order wrong means a test suite that
writes into a developer's real `~/.config/choom` or `%LOCALAPPDATA%\choom` — the exact bug
`tests/conftest.py`'s autouse fixture exists to prevent.

- [ ] T002 Create `src/choom/core/preferences.py` with `LEGAL_VIEW_ORIENTATIONS`,
      `DEFAULT_VIEW_ORIENTATION = "horizontal"`, and **`preferences_root() -> Path`** per
      [contracts/core-api.md](./contracts/core-api.md). This is the single overridable resolver — the
      only function in the module that reads an environment variable or calls `Path.home()`; every
      other path is built from its return value, mirroring `discovery.profile_root()`. Windows:
      `%LOCALAPPDATA%` → `%APPDATA%` → `~\AppData\Local`, each `/choom`. POSIX: `$XDG_CONFIG_HOME` →
      `~/.config`, each `/choom`. **An env var that is set-but-empty or set to a relative path must be
      ignored in favour of the next candidate** — a relative base resolves against the process's
      working directory, which for choom is usually *inside a workspace*, and would drop the
      preferences file into the user's vault. That is the one bug this function must not have; test it
      explicitly. Never creates the directory, never raises. Same task: unit tests in
      `tests/unit/test_preferences.py` covering each platform branch, the precedence order, and the
      empty/relative rejection. Verify: `scripts/dev-tests.sh tests/unit/test_preferences.py`
- [ ] T003 Extend the autouse `_isolated_profile_root` fixture in `tests/conftest.py` (currently at
      line 20) to also isolate preferences, **at both levels**, and rename it to reflect that it now
      guards two stores. Level one: `monkeypatch.setattr(preferences, "preferences_root", lambda: root)`
      for in-process tests. Level two: `monkeypatch.setenv` for `LOCALAPPDATA`, `APPDATA`, and
      `XDG_CONFIG_HOME`, alongside the `HOME` and `USERPROFILE` it already sets. **Both are required
      and the fixture's existing docstring already explains why**: several `tests/contract/` tests run
      choom as a real child process (`subprocess.run([sys.executable, "-m", "choom", ...])`), which
      gets a fresh interpreter that never sees a patched symbol. Half a fix here looks exactly like a
      whole one. Extend the docstring to cover the second store. Verify:
      `scripts/dev-tests.sh` (whole suite — this fixture is autouse and touches everything), plus
      confirm by inspection that no real `~/.config/choom` or `%LOCALAPPDATA%\choom` appears after a run
- [ ] T004 Add `get_view_orientation() -> str` to `src/choom/core/preferences.py`. **Never raises**;
      always returns a member of `LEGAL_VIEW_ORIENTATIONS`. Same task: unit tests in
      `tests/unit/test_preferences.py` covering **all eight failure modes**, each of which must return
      `"horizontal"` and must not raise — (1) file absent, (2) unreadable / `OSError`, (3) not valid
      TOML / `TOMLDecodeError`, (4) `[view]` table absent, (5) `view` present but not a table, (6)
      `orientation` key absent, (7) `orientation` present but not a string (a number, a list, a bool),
      (8) `orientation` a string but not a legal value (`"sideways"`, `"Vertical"` — matching is exact
      and case-sensitive) — plus the two happy paths. choom must always start; a hand-edited
      preferences file is a normal case, not an error (Principle IV, and the precedent
      `get_assistant` sets). Verify: `scripts/dev-tests.sh tests/unit/test_preferences.py`
- [ ] T005 Add `set_view_orientation(value: str) -> None` to `src/choom/core/preferences.py`. Raises
      `UsageError` for an illegal value with **nothing written**; raises `WorkspaceError` on an I/O
      failure. Writes through the existing `write_text_atomic` (`core/atomic_write.py:19`), which also
      creates the parent directory — do not hand-roll a fourth temp-file dance, that module exists
      because this sequence was duplicated four times before. Edits the single `orientation` line via
      the same line-targeted approach `core/config.py:115-142` uses on `[assistant]`. Same task: unit
      tests covering create-from-absent, replace-in-place, **comments / key order / unknown keys and
      unknown tables all survive**, CRLF preserved, illegal value writes nothing, and idempotence.
      Verify: `scripts/dev-tests.sh tests/unit/test_preferences.py`
- [ ] T006 [P] Export `preferences_root`, `get_view_orientation`, `set_view_orientation`,
      `LEGAL_VIEW_ORIENTATIONS`, and `DEFAULT_VIEW_ORIENTATION` from `src/choom/core/__init__.py`'s
      `__all__`, keeping it alphabetically sorted as it is today. Verify:
      `uv run ruff check . && uv run mypy`
- [ ] T007 [P] Create `src/choom/tui/layout.py` per [contracts/layout.md](./contracts/layout.md): the
      five component constants and **`MIN_VERTICAL_SCREEN_HEIGHT` written as their sum**, never as the
      literal `11` —

      ```python
      COLLECTION_BAR_ROWS  = 1   # app.tcss: CollectionBar { dock: top; height: 1 }
      STATUS_BAR_ROWS      = 1   # app.tcss: StatusBar { height: 1 }
      BAND_DIVIDER_ROWS    = 1   # border-top on the lower band
      MIN_UPPER_BAND_ROWS  = 4   # #list-header (1) + 3 record rows   (FR-032)
      MIN_LOWER_BAND_ROWS  = 4   # 4 lines of preview content         (FR-032)
      MIN_VERTICAL_SCREEN_HEIGHT = (COLLECTION_BAR_ROWS + STATUS_BAR_ROWS
                                    + BAND_DIVIDER_ROWS + MIN_UPPER_BAND_ROWS
                                    + MIN_LOWER_BAND_ROWS)
      ```

      A bare `11` becomes untouchable in six months when someone needs to know whether it can move and
      what it would break. Plus `effective_orientation(stored: str, screen_height: int) -> str`. **No
      widget imports** — pure, like `columns.py`, whose docstring records why layout arithmetic lives
      in `tui/` rather than `core/`. Same task: unit tests in `tests/unit/test_layout.py` asserting
      `MIN_VERTICAL_SCREEN_HEIGHT == 11` **and** that it equals the sum of its five components (so the
      derivation cannot silently drift from the value), and `effective_orientation` at heights 10 and
      11 for both stored values. Verify: `scripts/dev-tests.sh tests/unit/test_layout.py`
- [ ] T008 Read the preference once in `ChoomApp.__init__` (`src/choom/tui/app.py:84`) into
      `self.view_orientation`, alongside the existing session state. `cli/main.py` is **not** modified.
      This holds the *stored* value, not the effective one — the fallback is resolved per-render
      against the current height, because the terminal can be resized after startup. Same task: a unit
      or integration test that a fresh app reads `"horizontal"` with no preferences file and
      `"vertical"` with one. Verify: `scripts/dev-tests.sh tests/unit/test_layout.py tests/integration/test_tui_launch.py`

**Checkpoint**: the setting and the geometry exist and are tested. Nothing visible has changed yet.

---

## Phase 3 (US1, P1): Make choom fit a half-width window

**Goal**: `/config view vertical` rearranges the screen; the same record stays highlighted and
previewed.

**Independent test**: open choom in a half-width window, highlight a record, run
`/config view vertical`, confirm the arrangement and that the highlight and preview survived.

- [ ] T009 [US1] Add the five `-vertical` CSS variants to `src/choom/tui/app.tcss` per
      [contracts/layout.md](./contracts/layout.md): `#body.-vertical { layout: vertical; }` beside the
      existing `#body` rule; a new `#upper-band { height: 1fr; layout: horizontal; }`; and vertical-only
      variants for `#list-pane` (drop `border-right` — it is rightmost in the upper band),
      `#preview-pane` (full width, `height: 1fr`, `border-top` divider), and `#preview-links-section`
      (see T019). **Every change is an added variant; no base rule is edited.** That is what makes
      FR-020's "no residual difference" structural rather than something to test for. Verify: launch
      the app in both orientations and compare horizontal against the pre-change screenshot; T029
      makes it a test
- [ ] T010 [US1] Add an `effective_orientation()` accessor to `ListScreen` that combines
      `app.view_orientation` with `self.size.height` through `layout.effective_orientation`, so the
      fallback is applied in exactly **one** place and no caller reads the stored value directly.
      Verify: `uv run mypy`
- [ ] T011 [US1] Branch `ListScreen.compose` (`src/choom/tui/list_screen.py:200`) on the effective
      orientation per [data-model.md](./data-model.md) §4. Horizontal composes **exactly today's tree,
      unchanged**. Vertical composes `Vertical#body.-vertical` containing `Horizontal#upper-band`
      (scope pane + list pane) and `#preview-pane`. **Every id is identical in both trees** — that is
      what lets the inline editor's mount target and every existing `query_one` keep working untouched.
      Keep the branch to a small contiguous block: this is the one hunk that will conflict with #43.
      Verify: `scripts/dev-tests.sh tests/integration/test_list_tui.py`
- [ ] T012 [US1] Add `view` to `ChoomApp.handle_config_command` (`src/choom/tui/app.py:382`) — the set
      and get forms per [contracts/tui.md](./contracts/tui.md) C1. Error wording is T025's; this task
      is the happy path: a legal value persists via `set_view_orientation`, updates
      `app.view_orientation`, and returns the confirmation string. Same task: tests that a legal value
      is persisted and reported. Verify: `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py`
- [ ] T013 [US1] Make `_on_config_requested` (`src/choom/tui/list_screen.py:953`) `async` and perform
      the switch per [data-model.md](./data-model.md) §5.1: capture the highlighted record's id, then
      `await self.query_one("#body").recompose()`, then `await self._refresh_scope_pane()`, then
      `await self.refresh_rows(select_id=...)`. **Recompose `#body`, never the screen** — a
      screen-level recompose would destroy the command bar mid-dispatch of the very message being
      handled. Do not add a focus call: `_on_command_bar_closed` already focuses `#meeting-list`
      afterwards and that existing rule is what FR-023 requires. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py`
- [ ] T014 [US1] Restore the backlinks-expanded state after a recompose (FR-021): if
      `self._preview_links_expanded` was set, re-show `#preview-links-section` and repopulate it. The
      recompose builds a fresh section that defaults to hidden, so without this the section silently
      collapses on every switch. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k backlinks`
- [ ] T015 [US1] Integration tests in a new `tests/integration/test_vertical_layout_tui.py` at
      `size=(120, 40)`: the vertical tree has `#upper-band` with the scope pane and list pane as its
      children and `#preview-pane` as a sibling below; the horizontal tree has all three as siblings of
      `#body`; the same record is highlighted and previewed across a switch (FR-022); collection,
      scope, and filter term all survive (FR-021); focus lands on `#meeting-list` (FR-023); `h`/`l`
      still move between the scope pane and the list; and the record list is **wider** in vertical than
      in horizontal at the same terminal size (FR-019). Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py`

**Checkpoint**: US1 is deliverable — the layout switches and preserves state.

---

## Phase 4 (US2, P1): The choice is remembered, and it is mine

**Goal**: the preference survives a relaunch, follows the user across workspaces, and touches nothing
inside any workspace.

**Independent test**: set vertical, relaunch, confirm; open a second workspace, confirm; inspect the
workspace tree and find nothing changed.

- [ ] T016 [US2] Integration tests in `tests/integration/test_vertical_layout_tui.py`: a fresh app with
      a stored `"vertical"` opens vertical with no command typed; an app with **no** preferences file
      opens horizontal (FR-002 — the default needs no configuration); the same stored preference
      applies in a **second, unrelated workspace** (FR-008, one value per user, not keyed by
      workspace). Verify: `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k persist`
- [ ] T017 [US2] Test that a switch writes **nothing** inside the workspace (FR-024, SC-005): snapshot
      every file under the workspace root before the switch and assert byte-identical afterwards, and
      assert specifically that `.choom/config.toml` gains no `[view]` table. This is the constitutional
      requirement from spec.md §"Decision" made executable — the whole storage argument is worthless if
      a stray write lands in a shared OneDrive folder anyway. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k workspace_untouched`

**Checkpoint**: US2 is deliverable — persistence works and is provably per-user.

---

## Phase 5 (US3, P1): Everything still works the way it did

**Goal**: no binding, no footer text, and no editor behaviour differs between orientations.

**Independent test**: run the same scripted interaction in both orientations; every outcome except
pane geometry is identical.

- [ ] T018 [US3] Test that the inline editor opens in the lower band in vertical with the list and
      scope pane still visible above, saves and discards identically, and returns the preview with the
      same record highlighted (FR-040). **`list_screen.py:246`'s mount line must not change** — the id
      exists in both trees, so if this task needs to edit that line, T011 got the ids wrong. Verify:
      `scripts/dev-tests.sh tests/integration/test_inline_editor_tui.py tests/integration/test_vertical_layout_tui.py -k editor`
- [ ] T019 [US3] Bound `#preview-links-section` in vertical (FR-043) as a fraction of its container
      rather than the fixed `max-height: 12` it carries today (`app.tcss:50-60`). **This is a real
      regression, not a precaution**: in horizontal the preview pane is full body height so 12 rows is
      a slice, but in vertical at 80x24 the lower band is ~10 rows and the existing constant would
      consume the *entire band*, leaving no preview visible. Invisible in the issue's sketch; findable
      only by reading the stylesheet against the new band height. Same task: a test at `(80, 24)` in
      vertical that with the backlinks section expanded, **preview content is still visible above it**.
      Verify: `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k backlinks`
- [ ] T020 [US3] Test binding and footer parity (FR-027, FR-028, SC-007): capture the active binding
      set and the footer string in each state — list, task list, preview, backlinks-focused, editor,
      link-picker — in **both** orientations and assert they are identical. Orientation must never
      appear in the footer. `status_bar.py:10-26`'s help strings must not be edited by this feature;
      `h/l pane` stays accurate because the two panes stay left-and-right of each other in both
      arrangements. Also assert the full-screen reading view and full-screen editor take the whole
      window in vertical and return to it on exit (FR-029). Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k parity`

**Checkpoint**: US3 is deliverable — the feature is safe to ship.

---

## Phase 6 (US4, P2): A short terminal is still a working terminal

**Goal**: vertical is usable at 80x24, degrades to horizontal below the threshold, reverses on growth,
and never rewrites the stored preference.

**Independent test**: run at 80x24 and confirm both bands are usable; shrink past the threshold and
confirm the fallback; grow back and confirm the reversal; confirm the stored value is unchanged.

- [ ] T021 [US4] Wire the resize path in `ListScreen.on_resize` (`src/choom/tui/list_screen.py:288`)
      per [contracts/tui.md](./contracts/tui.md) C4, with the branches in **this order**:

      1. `if self._editor_pane is not None:` → columns only, **never recompose** (FR-025)
      2. effective orientation unchanged → columns only, exactly as today
      3. otherwise → recompose + repopulate, then columns

      **The guard is branch one from the first line this code exists — never a follow-up commit.** See
      "The one way this feature loses the user's words" above. Same task: tests that a resize crossing
      the threshold with **no** editor open does flip the layout, and that a resize not crossing it
      does not. The dirty-editor case is T022's, deliberately separate. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k resize`
- [ ] T022 [US4] **The data-loss regression test, and proof that the guard is load-bearing.** Its own
      task because this is the only path in the feature that can destroy the user's words, and a guard
      whose test would pass without it is not a guard. In
      `tests/integration/test_vertical_layout_tui.py`: open the inline editor in vertical, type text
      **without saving**, resize the terminal below `MIN_VERTICAL_SCREEN_HEIGHT` and back, then assert
      the editor is still mounted, still focused, and still holds the typed text byte-for-byte. Then
      **prove the test bites**: temporarily comment out branch one of T021's guard, run the test,
      confirm it **fails**, restore the guard, confirm it passes. Record the observed failure mode in
      the test's docstring so the next reader knows what it is protecting. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k dirty_editor`
- [ ] T023 [US4] The threshold boundary, in **both** directions — the part a single "it degrades" test
      would miss and the part most likely to rot if the constant is ever edited. In
      `tests/integration/test_vertical_layout_tui.py`: `(80, 11)` renders vertical with both bands at
      their minimum (column header + 3 rows above, 4 content lines below); `(80, 10)` renders
      horizontal; a `10 → 11` resize restores vertical **with nothing typed** (FR-033); and a
      `24 → 10 → 24` round trip leaves the **stored** preference reading `"vertical"` throughout
      (FR-034) — degrading must never rewrite it. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k boundary`
- [ ] T024 [US4] The required 80x24 case (FR-031, SC-008). **This is genuinely new coverage, not a
      re-run**: every existing narrow-terminal test varies *width* at a fixed 24 rows
      (`tests/integration/test_narrow_terminal_tui.py` uses `(20,24)`, `(10,24)`, `(40,24)`), so no
      test in the repo currently exercises height at all. Assert that at `(80, 24)` in vertical the
      record list shows its column header plus at least three record rows and the preview band shows at
      least four lines, and that neither band is reduced to a single row. Add `(120, 40)` as the
      comfortable companion — the two sizes the TUI is smoke-tested at. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k terminal_size`
- [ ] T025 [US4] Extend `tests/integration/test_narrow_terminal_tui.py` with a vertical case at
      `(20, 24)` proving width degradation is **identical** in both orientations (FR-039): the
      lower-priority labelled columns drop, the collection bar compacts, and the workspace path elides
      exactly as they do in horizontal. Also assert width **never** triggers the fallback — a terminal
      1000 rows tall and 10 columns wide stays vertical. Verify:
      `scripts/dev-tests.sh tests/integration/test_narrow_terminal_tui.py`

**Checkpoint**: US4 is deliverable — short terminals are safe, and so is an open editor.

---

## Phase 7 (US5, P2): The command tells you when you get it wrong

**Goal**: every malformed input names what went wrong and what to do instead; the command is
discoverable without guessing.

**Independent test**: enter each malformed form and confirm the message, that the layout is unchanged,
and that the help pane lists the command.

- [ ] T026 [US5] Error messages per [contracts/tui.md](./contracts/tui.md) C1. `/config view sideways`
      → `view must be one of horizontal, vertical; got 'sideways'`, matching `set_assistant`'s existing
      shape exactly; the layout does not change and **nothing is written** (FR-044). Also change the
      existing bare `unknown setting: {name!r}` at `src/choom/tui/app.py:389` to name the settings that
      do exist — `unknown setting: 'layout'; known settings: assistant, view` (FR-045). **This is the
      one existing string this feature edits**: Principle V requires an error to say what to do
      instead, and a second setting is what makes the list worth printing. Same task: tests for both
      messages and for the no-write guarantee. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k error`
- [ ] T027 [US5] The get form and the fallback report. `/config view` with no value reports the current
      setting and the accepted values; when the fallback is in effect it reports **both** facts — that
      the setting is vertical and that horizontal is in effect because the terminal is too short
      (FR-037). Setting `vertical` on a too-short terminal still saves and says so (FR-038). Same task:
      tests for the unset, set, and fallback-in-effect wordings. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k report`
- [ ] T028 [US5] Update the `/config` verb entry in `src/choom/tui/commands.py:24` so its argument and
      description cover **both** settings and both of `view`'s accepted values (FR-046) —
      `VERB_TABLE` is what `HelpScreen._render_body` prints, so this is the whole of discoverability.
      No new verb is registered; `/config` already exists. Same task: extend
      `tests/integration/test_help_pane_tui.py` to assert the help pane names `view` and both values.
      Verify: `scripts/dev-tests.sh tests/integration/test_help_pane_tui.py`
- [ ] T029 [US5] Degrade gracefully when the store cannot be written (FR-013): catch `WorkspaceError`
      from `set_view_orientation`, **still apply the layout for this session**, and report
      `view set to vertical for this session; could not save the preference: <reason>`. A failed write
      must not abort the interface. Same task: a test with an unwritable preferences directory
      asserting the layout still switched and the message named the failure. Verify:
      `scripts/dev-tests.sh tests/integration/test_vertical_layout_tui.py -k unwritable`

**Checkpoint**: US5 is deliverable — the whole feature is complete.

---

## Phase 8: Polish & cross-cutting

- [ ] T030 Lock horizontal's geometry with a test, turning
      [contracts/layout.md](./contracts/layout.md)'s must-not-change list from advice into
      enforcement. In a new `tests/unit/test_app_tcss_scope.py`: parse `src/choom/tui/app.tcss` into
      selector → declarations and assert that the base rules for `#body`, `#scope-pane`, `#list-pane`,
      and `#preview-pane`, plus the 20 protected selectors (`Screen`, `CollectionBar`, `#scope-list`,
      `#list-header`, `#meeting-list`, `#bottom-bar`, `CommandBar` and its three child rules,
      `StatusBar`, `#link-picker`, `#links-section`, `#links-list`, `#preview-links-list`, `#editor`,
      `EditorPane`, `#confirm-dialog`, `ConfirmDialog`, `HelpScreen`, `#help-pane`, `#help-body`), are
      **exactly** what they are today. Frame it as what it is: FR-020's "no residual difference" made
      executable, which also protects the horizontal layout from accidental regression by every future
      feature. Docstring must say that a failure means either scope creep or a deliberate change that
      has to be re-recorded here on purpose. Verify:
      `scripts/dev-tests.sh tests/unit/test_app_tcss_scope.py`
- [ ] T031 [P] Cross-platform paths: extend `tests/integration/test_unicode_paths.py` with a profile
      directory containing spaces and non-ASCII characters, confirming the preferences file is written
      and read back verbatim. Also assert the resolved path stays well under the Windows 260-character
      limit and that no admin rights or network access are involved. Verify:
      `scripts/dev-tests.sh tests/integration/test_unicode_paths.py`
- [ ] T032 [P] Verify the scope fence held (see "Scope fence" above): `git diff` must show **no**
      change to `ScopePane`, `show_categories`, `task_category`, or the task branch of `refresh_rows` —
      those belong to #43, which implements first. Also confirm `src/choom/cli/` has **no diff at all**
      (gate II, FR-030): no subparser, no `--json` key, no exit code, and `_run_tui` untouched. Verify:
      `git diff origin/release/v0.0.4 -- src/choom/cli/` is empty, and inspect the `list_screen.py`
      diff against the four named symbols
- [ ] T033 [P] Confirm no other documentation needs amending: `docs/REQUIREMENTS.md` is unchanged
      because this feature adds no exit code, no frontmatter key, no id-scheme change, and no directory
      layout change; `AGENTS.md.tmpl` is unchanged because a pane arrangement is not something an
      assistant reads, writes, or needs told about, and the file's content rule bites well before its
      ~100-line backstop does
- [ ] T034 **Leave README.md alone — this is a deliberate skip, not an oversight.** Per CLAUDE.md the
      README feature list describes the *released* version and closes with "Everything above has landed
      on `main` as of vX.Y.Z"; `/release` folds a version's user-visible changes in when it cuts that
      version. Adding or extending a bullet for this unreleased work — including appending a sentence
      to the existing layout or interface bullet, which is the same error in a harder-to-spot form —
      would promise behaviour a reader installing from PyPI does not get. The feature is recorded in
      this feature's own `specs/020-vertical-tui-mode/` artifacts instead, which is what a
      "document it" task is actually for at implementation time. Verify: no `README.md` edit appears in
      `git diff`
- [ ] T035 Run the gates: `scripts/dev-tests.sh` (whole suite green, count no lower than T001's
      baseline plus the new tests) and
      `uv run ruff format --check . && uv run ruff check . && uv run mypy`
- [ ] T036 Run [quickstart.md](./quickstart.md) end to end by hand against a scratch workspace under
      `/tmp`, particularly §3 (the backlinks bound in the lower band), §4 (the size table, including
      80x11 and 80x10), and **§5 (the data-loss guard — the one that matters most)**. TUI changes are
      verified before release on the terminals in `docs/REQUIREMENTS.md` §4.3; do this at 120x40 and
      80x24 at minimum

---

## Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks every user story**. Internal order is
  load-bearing: T002 (module) → T003 (fixture isolation) → T004/T005 (the first tests that write a
  preference). Do not reorder.
- **US1 (Phase 3)**: depends on Phase 2
- **US2 (Phase 4)**: depends on US1 — the switch has to exist before persistence across it means
  anything
- **US3 (Phase 5)**: depends on US1
- **US4 (Phase 6)**: depends on US1. **T022 depends on T021** — the guard must exist before its proof
  can be run against it
- **US5 (Phase 7)**: depends on T012 (the command's happy path)
- **Polish (Phase 8)**: depends on all of the above. T030 depends on T009 having settled the stylesheet

### Parallel opportunities

- Phase 2: T006 and T007 together — different files, no shared state. **T002–T005 are strictly
  sequential** (same module, and the fixture ordering above)
- Phase 8: T031, T032, T033 together

### Suggested MVP

Phases 1–3. US1 alone delivers the issue's actual request — the layout switches and keeps your place.
It is **not shippable without US4's T021 and T022**, though: US1 introduces the recompose, and the
moment a resize can trigger one, the editor guard is load-bearing. Treat Phase 6's first two tasks as
part of the MVP even though the rest of US4 can follow.

---

## Notes

- **No README task exists, deliberately.** The tasks template would generate one; it is omitted per
  CLAUDE.md and the reason is recorded as T034 so a reviewer sees the decision rather than a gap.
  `/release` owns the README.
- **No trailing test phase, deliberately.** Every behaviour task above carries its own tests, per
  Principle VI and the Development Workflow gate. There is nothing to "add tests for" at the end.
- **No `contract/` test task.** This feature adds no CLI command, flag, `--json` key, or exit code —
  the carve-out is argued in spec.md §"Interface parity" and gate II. T032 checks `src/choom/cli/` has
  no diff at all, which is a stronger statement than any assertion about argparse would be.
- **No `performance/` test task.** No budget to protect: one small file read at startup, and a switch
  bounded by the refresh the app already runs on every return from a full-screen editor.
- **Three mistakes to watch for, each called out in the task text where it would be made**:
  recomposing the *screen* instead of `#body` (T013 — it destroys the command bar mid-dispatch);
  letting a resize recompose while an editor is open (T021/T022 — it destroys an unsaved buffer, and
  it is the only way this feature loses data); and leaving `#preview-links-section` at `max-height: 12`
  in vertical (T019 — it eats the entire lower band at 80x24).
- **One thing deliberately not done**, argued in research R6: `config.py`'s `_apply_assistant_key` is
  **not** generalised into a shared "edit one key in one TOML table" helper for both modules. The two
  write different files with different failure semantics — a workspace config failure surfaces as a
  `WorkspaceError`, a preferences failure is swallowed into a status line per FR-013 — and #43 is in
  flight over adjacent code. A sensible follow-up once both callers have settled, not a thing to
  introduce underneath a parallel feature.
- **One accepted limitation**, recorded in research R2: the preview's scroll offset is not preserved
  across a switch, because the `Markdown` widget is rebuilt. The spec promises the same record
  (FR-022), not the same scroll position.
