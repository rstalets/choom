# Phase 0 Research: UI Layout Refresh

**Feature**: `005-ui-layout-refresh` | **Date**: 2026-07-30

Everything below was resolved against the installed stack (Textual >= 8.2, Python 3.11+) and the
existing `endpaper.core` API. No NEEDS CLARIFICATION markers remain.

---

## R1. The top collection bar: a plain `Static`, not Textual's `Tabs`

**Decision**: Build `CollectionBar` as a non-focusable `Static` that renders
`Endpaper >>   Tasks   Notes   Meetings` with the active name styled, and re-renders when the
active collection changes.

**Rationale**: Textual's `Tabs` widget is focusable and binds `left`/`right` to move between tabs.
Those are the same keys FR-008 reserves for moving between the left and middle panes, so `Tabs`
would either steal them or need them disabled. `Tabs` also owns an animated underline and expects
to be the thing that has focus, whereas FR-005 requires focus to sit on the middle pane at all
times. A `Static` that renders one line of markup has none of those conflicts, and the constitution
(VI) prefers a plain widget to a framework feature that has to be fought.

**Alternatives considered**:

- `Tabs` / `TabbedContent`: rejected — `TabbedContent` also wants to own the content panes, which
  would mean three copies of the list/preview layout instead of one that re-fills.
- A `Horizontal` of `Label` widgets: rejected — same result as one `Static`, three times the DOM
  nodes and no benefit; only useful if the names needed to be individually clickable, which no
  requirement asks for.

---

## R2. Tab / shift+Tab: screen bindings without `priority`, gated by `check_action`

**Decision**: Bind `tab` → `next_collection` and `shift+tab` → `previous_collection` in
`ListScreen.BINDINGS` with `priority=False` (the default), and implement `ListScreen.check_action`
to return `False` for both while the command bar is open.

**Rationale**: Textual resolves a key by checking the focused widget's `BINDINGS` first, then walking
up the DOM to the App. A non-priority screen binding therefore loses to any widget binding — which is
what FR-007 wants for the editor (a separate screen entirely) and the help pane (a `ModalScreen`,
whose bindings take precedence over the app's). The one case the DOM walk does not solve is the
command bar: `Input` has no `tab` binding of its own, so the key would bubble to the screen and
switch collections mid-typing. `check_action` is Textual's supported hook for exactly this — it
disables the binding while a condition holds, and it also removes the key from the footer, which
keeps Principle V's "every active binding is visible in the footer" honest.

Using `priority=True` would be actively wrong here: priority bindings are checked *before* the
focused widget and cannot be disabled by a widget, which is the opposite of FR-007.

**Consequence to document**: overriding `tab` on the list screen removes Textual's default
focus-next traversal on that screen. Pane movement is already explicit (`h`/`l`, left/right), so
nothing becomes unreachable, but the footer must not advertise Tab as focus traversal.

**Alternatives considered**:

- Bind `tab` to a no-op on `CommandBar`: works, but hides the reason in a second place and leaves
  the footer claiming Tab is live while the bar is open.
- Handle `on_key` manually on the screen: rejected — bypasses the binding system, so the footer and
  `check_action` no longer describe reality.

---

## R3. The undeletable `/`: a sibling `Static`, not a guarded `Input`

**Decision**: Compose the command bar as `Horizontal(Static("/", id="bar-prefix"), Input(...))`. The
slash is a different widget from the text field, so no editing key can reach it.

**Rationale**: FR-028 is trivially and permanently satisfied — there is no code path by which
backspace deletes a character that is not in the `Input`'s value. It also removes the
`_normalize()` workaround the current bar carries (stripping a retyped leading `/` from the query),
because the user no longer needs to type the slash at all: pressing `/` opens the bar and the prefix
is already there.

**Alternatives considered**:

- Keep `/` inside the `Input` value and re-add it on every `Changed`/`backspace`: rejected — fights
  the cursor position, needs guards on backspace, delete, `ctrl+u`, `ctrl+w`, `ctrl+a`+type, and
  paste, and is one missed binding away from a bug.
- `Input(value="/")` plus a `cursor_position` clamp: rejected — same guard problem, plus the value
  then contains a character that is not part of the command, which every consumer must strip.

---

## R4. The help pane: a `ModalScreen` with a bottom-docked container

**Decision**: `HelpScreen(ModalScreen[None])` containing one container with `dock: bottom`,
`height: 60%`, over a screen background with alpha so the list shows through. Escape dismisses.

**Rationale**: `ModalScreen`'s documented behaviour is precisely FR-036 and FR-037 — its bindings
take precedence over the app's (so Tab cannot switch collections behind it), and its default styling
leaves the screen underneath visible but dimmed. Because the list screen is never popped, every bit
of its state — highlighted row, displayed month, active filter — is still there when the pane
closes, with no save/restore code to get wrong.

**Alternatives considered**:

- A container inside `ListScreen` toggled with `display`: rejected — the list screen's bindings stay
  live behind the pane, so FR-007 needs another `check_action` branch, and the pane competes with
  the command bar for the bottom dock.
- A full `Screen`: rejected — replaces the view entirely, failing FR-037.

---

## R5. Month discovery is a directory listing, not a scan

**Decision**: Add `list_months(workspace, collection) -> list[YearMonth]` to core. It globs
directories matching `<scan_dir>/**/YYYY/MM` and returns the set, most-recent-first. It opens no
files.

**Rationale**: `create_document` already writes to `<collection>/<YYYY>/<MM>/`, and
`open_daily_note` writes to `notes/daily/<YYYY>/<MM>/`. The month is therefore already encoded in
the path, so the left pane can be filled from directory names alone — no frontmatter is read to
decide which months exist. The `**` is what picks up the `daily/` subtree without special-casing it,
and it keeps working if a future collection nests deeper.

The companion `scan_month(workspace, collection, year, month)` reads `*.md` from those month
directories only, reusing `_parse_document` unchanged so warning behaviour (Principle IV) is
identical to a full scan.

**Alternatives considered**:

- Derive months from each document's `created` frontmatter: rejected — requires reading every file
  to know which months exist, which is the cost the feature exists to remove.
- Keep `scan_documents` and filter in memory: rejected — same, it reads everything.

---

## R6. Documents outside the `YYYY/MM` layout: an "Unfiled" entry

**Decision**: `list_months` also reports whether stray `*.md` files exist directly under a scan dir
(outside any `YYYY/MM` folder). When any exist, the left pane shows an **Unfiled** entry after the
months; selecting it lists them.

**Rationale**: Today `scan_documents` uses `rglob("*.md")`, so a file a user drops at `notes/idea.md`
by hand is visible in the list. Month-scoped reading would make it silently invisible — the tool
would show an empty month while the user's file sits on disk. That is close enough to Principle IV's
"never lose the user's words" to be worth the one extra entry. Detection is a directory listing, and
the files are only read if the user selects Unfiled, so the performance goal is untouched.

**This extends the spec.** FR-014 describes the month list as "every month for which the collection
holds documents, plus the current month". It does not mention stray files, because the spec was
written from the issue rather than from the current `rglob` behaviour. Flagged for the author: keep
Unfiled, or accept that hand-placed files outside `YYYY/MM` stop appearing in the TUI.

**Alternatives considered**:

- Ignore stray files: rejected — a silent regression against today's behaviour.
- Move stray files into the right month folder on sight: rejected hard — endpaper does not rearrange
  the user's directory, and a write triggered by a read is exactly the kind of surprise the
  constitution's data-loss principle exists to prevent.

---

## R7. Cross-month filter: load once per session, on a worker thread, then filter in memory

**Decision**:

1. The bar recognises the verb as soon as `filter ` / `f ` is complete; from that point the
   remaining keystrokes filter **live**, as they do today.
2. The first live keystroke of a filter triggers a full-collection load in a Textual thread worker
   (`@work(thread=True, exclusive=True)`), which fills the per-collection month cache.
3. Every later filter keystroke — and every later filter in the session — reads the cache, not the
   disk.
4. While the load is running, the middle pane shows a "searching…" row; keystrokes are still
   accepted.

**Rationale**: This is what makes FR-032, FR-035, and FR-036 hold at once. Live filtering is the one
behaviour the constitution (II) explicitly names as inherently interactive, so dropping it in favour
of submit-only filtering would be a real loss; recognising the verb before the term restores it
without reintroducing the namespace collision FR-031 removes. Doing the read on a thread keeps the
event loop free, and caching means the expensive read happens at most once per collection per
session.

The cache is `dict[(collection, year, month) -> list[Document]]` held on the app instance. **It is not
a second source of truth**: nothing is written to disk, nothing survives the process, and the app
already holds every scanned document in memory today (`self.documents`) — this change makes that
memory lazily filled instead of eagerly filled. Constitution III is aimed at on-disk indexes; see the
Constitution Check in `plan.md`.

**Alternatives considered**:

- Filter only the displayed month: rejected by the author during specification.
- Submit-only filtering: rejected — loses live filter, and the spec's own US5 wording ("types and
  submits") does not require abandoning it.
- Re-scan on every filter keystroke: rejected — a full scan per keypress is the pathology the whole
  feature is meant to avoid.

---

## R8. A Done-only view needs a core selector, and Principle II makes it a CLI flag too

**Decision**: Add `only_done: bool = False` to `TaskFilter`; `filter_tasks` returns completed tasks
only when it is set. Expose it on the command line as `endpaper task list --done`.

**Rationale**: `TaskFilter.include_done` is a two-state switch (open only / everything). The Done
category needs a third selection — completed only — which does not exist today. Doing that selection
in the TUI with a list comprehension would put behaviour in a front-end, which Principle I forbids.

The CLI flag is Principle II, not scope creep: "any behaviour available in one MUST be available in
the other, unless it is inherently interactive". Listing completed tasks is not interactive, so a
TUI-only Done view would be a constitutional violation requiring a Complexity Tracking entry. The
flag is additive — no existing flag, exit code, or `--json` key changes — so it costs one argument
and one branch.

**This extends the spec**, whose Assumptions say "the command line is unaffected". Flagged for the
author. Note that `--done` and `--all` are mutually exclusive in meaning; `--done` wins if both are
given, and that is documented rather than made an error, because the CLI must not fail on input it
can interpret.

**Alternatives considered**:

- Filter done-only in the TUI: rejected — violates Principle I.
- Replace `include_done` with a tri-state `state` field: rejected — breaks a public dataclass and
  every existing caller and test for no user-visible gain.

---

## R9. The version string: stamped at build time, `0.0.0` from source

**Decision**: The status bar reads `from endpaper import __version__` — the same import
`cli/main.py:8` uses for `--version` — and renders `v{__version__}` right-aligned in the bottom bar.
`__version__` stops being a hardcoded literal and becomes:

```python
# src/endpaper/__init__.py
try:
    from endpaper._version import __version__
except ImportError:            # running from a source checkout, not a built package
    __version__ = "0.0.0"
```

`_version.py` is written by hatch-vcs's build hook and is never committed:

```toml
[tool.hatch.version]
source = "vcs"
fallback-version = "0.0.0"          # was "0.0.1"

[tool.hatch.build.hooks.vcs]
version-file = "src/endpaper/_version.py"
```

**Rationale**: Today `endpaper/__init__.py` hardcodes `__version__ = "0.0.3"` while the built
distribution takes its version from VCS tags. The two drift the moment a tag moves, and then the TUI
and CLI agree with each other while both lie about which build is running — which is exactly what
FR-042 exists to prevent, and what makes a bug report unactionable. Stamping the version in at build
time makes the string a fact about the artifact rather than a value someone has to remember to
update.

`0.0.0` as the source-checkout value is deliberate and is now FR-043: it is not a plausible release
number, so a screenshot or a bug report from unbuilt code is self-identifying. Sharing one module
attribute between the front-ends keeps FR-042's "must match the CLI" true by construction.

**Alternatives considered**:

- `importlib.metadata.version("endpaper")` with `PackageNotFoundError` → `"0.0.0"`: rejected — for
  an editable install it reports the version recorded at install time, which goes stale as soon as
  you commit, reintroducing the drift in a subtler form.
- Keep the literal and add a CI check that it matches the tag: rejected — a lint that exists because
  a value is duplicated is worse than not duplicating the value.
- Derive at runtime from `git describe`: rejected — requires git at runtime, which the constitution's
  no-external-binaries rule forbids, and would fail in an installed package anyway.

**Open item to verify during implementation, not a design choice**: hatch-vcs documents that the
build hook runs when *building or installing*, so `uv pip install -e .` may generate `_version.py`
with a development version such as `0.0.4.dev3+g9030517` rather than leaving the fallback in place.
FR-043 asks for `0.0.0` from a source checkout. The implementation task must check what an editable
install actually produces and, if the hook fires, scope it to the wheel and sdist targets so the
editable path falls through to the fallback. Either way `_version.py` goes in `.gitignore` and the
assertion in the tests is "TUI equals CLI", never a literal version string.

---

## R9a. A release dry-run workflow, dispatched with a proposed version

**Decision**: Add `.github/workflows/release-dry-run.yml`, triggered only by `workflow_dispatch`
with a required `version` input. It runs the same test and build steps as `publish.yml`, overrides
the computed version with the proposed one, installs the built wheel into a clean environment and
asserts `endpaper --version` reports exactly that version, then uploads `dist/` as a workflow
artifact. **It has no PyPI credentials, no `id-token: write` permission, and no publish step.**

**Rationale**: Today the only way to find out whether a release builds, versions itself, and
installs correctly is to publish it, and PyPI does not allow a version number to be reused. The
dry run makes the whole pipeline rehearsable: the same steps, the same version-injection path,
ending in a downloadable artifact instead of an irreversible upload.

It also closes the loop on R9. The claim "the version is stamped in at build time" is only worth
anything if something checks the stamp on a real artifact — installing the wheel and comparing
`endpaper --version` to the dispatched input is that check, and it runs before a release rather
than after.

**How the proposed version reaches the build**: `SETUPTOOLS_SCM_PRETEND_VERSION`, which hatch-vcs
documents as taking precedence over VCS detection. No tag is created and no commit is made, so a
dry run leaves the repository exactly as it found it.

**Safety**: the absence of the `pypi` environment and of `id-token: write` is the guarantee, not a
convention — the job has no credential to publish with even if a step were added by mistake. The
input is validated against a PEP 440-shaped pattern before the build so a typo fails fast rather
than producing a strangely-named artifact.

**Noted, not changed**: `publish.yml`'s test job runs `pytest` only — not `ruff format --check`,
`ruff check`, or `mypy`. A release can therefore go out with lint or type errors that would block a
pull request, which reads as an oversight against the constitution's quality gates. The dry-run
workflow runs the full gate so a rehearsal is at least as strict as review. Bringing `publish.yml`
up to the same bar is a one-line change but belongs to whoever owns the release process, not to
this feature.

**Alternatives considered**:

- Reuse `publish.yml` with a `dry_run` boolean input: rejected — one workflow that sometimes
  publishes is exactly the shape where a wrong default or a mis-typed condition publishes something
  by accident. Two workflows, one of which structurally cannot publish, is safer than one workflow
  with a flag.
- Build on every pull request instead: rejected — useful, but it answers a different question. The
  dry run is about rehearsing a *specific proposed version*, which no PR-triggered build knows.

---

## R10. Screen flow after this feature

**Decision**:

| Trigger | Today | After |
|---|---|---|
| App start | `ListScreen`, Meetings active | `ListScreen`, **Tasks** active |
| `enter` on a document row | `PreviewScreen` | unchanged |
| `e` on a document row | nothing | **`EditScreen`** |
| `e` in preview | `EditScreen` | unchanged |
| create note/meeting/daily | `PreviewScreen` | **`EditScreen`** |
| `ctrl+x` in editor | pop to caller | unchanged (caller is now sometimes the list) |

**Rationale**: `EditScreen` already returns to whatever pushed it, so both new entry points work
without touching its save/discard logic (Principle V's list → preview → edit state machine is
preserved; this only adds two edges into `edit`). The create path stops pushing `PreviewScreen`
entirely, which is what FR-026 asks for.

### One entry point, not four

**Decision**: All routes into the editor go through a single module-level helper in
`tui/edit_screen.py`:

```python
def open_editor(app: App[None], path: Path) -> bool:
    """Push the editor for `path`. Returns False and reports the reason if the file
    cannot be read, leaving the caller's screen in place."""
```

`PreviewScreen.action_edit`, `ListScreen.action_edit`, the create handlers, and the daily-note
handler all call it. `EditScreen` itself is untouched.

**Rationale**: today there is exactly one construction site —
`preview_screen.py:64` does `load_for_edit(self.path)` then `push_screen(EditScreen(file))`. This
feature turns that into four (preview `e`, list `e`, create note/meeting, daily note). Two lines
copied four times is the kind of duplication that looks too small to bother with and then drifts:
one site gains a guard, another gains a status message, and FR-023's "behaves identically" quietly
stops being true.

It also stops a latent bug from being copied. `load_for_edit` is documented to raise `OSError`, and
nothing catches it today — pressing `e` on a document deleted out from under the tool takes down the
app. That is a pre-existing single-site bug; multiplying it by four without handling it would be a
regression in all but name. The helper is the one place to turn it into a status-bar message, which
is what the constitution's "error messages name what went wrong" requires (Principle V) and what
Principle IV expects of anything touching a file that may have changed underneath.

**Alternatives considered**:

- A mixin or shared base screen for "screens that can open the editor": rejected — a class to hold
  one function, against Principle VI's "prefer a plain function to a class".
- A method on `EndpaperApp`: reasonable, and it is where `refresh_document` lives. Rejected narrowly
  because pushing a specific screen is view routing rather than app state, and keeping it next to
  `EditScreen` means the helper and the screen it constructs are read together.
- Leave the two lines duplicated: rejected — see above; four copies of an unguarded `OSError` path
  is the concrete cost.

**Watch item**: Principle V says "reading is the default; editing is the exception. Opening an
existing note shows rendered markdown." Pressing `e` is an explicit request to edit, and creating a
document is not "opening an existing note", so neither new edge contradicts it — but `e` must not
become the *default* action for `enter`, and it does not.

---

## R11. Performance fixtures need documents spread across months

**Decision**: Extend `tests/fixtures/generate.py` with a month-spreading option and use it for the
new month-scope performance tests.

**Rationale**: `generate()` currently starts at `2026-01-01 09:00` and steps one minute per
document, so 1000 meetings all land in `2026/01`. A month-scoped test built on that fixture would
read the same 1000 files whether scoping worked or not, and would pass while proving nothing. The
new fixture must place a known, small number of documents in the current month and the bulk in
earlier months, so "reads only the current month" is observable.

**Measurement approach**: count file reads, not wall-clock. The existing perf tests assert elapsed
time (`< 2.0s`), which is the right shape for "a full scan is fast enough" but the wrong shape for
"only one month was read" — a fast machine passes a broken implementation. The month tests assert
the set of paths opened (monkeypatched `Path.read_text` or a counting wrapper), which is exact and
machine-independent.

---

## R12. What existing tests this invalidates

Not research so much as scope reality, recorded here so `/speckit-tasks` can plan for it:

| Test file | Why it breaks | Disposition |
|---|---|---|
| `tests/integration/test_collection_menu_tui.py` | Asserts `#collection-menu` `ListView`, `CollectionRow`, and Meetings-at-launch | Rewrite against `CollectionBar` and Tab |
| `tests/integration/test_partitioned_layout.py` | Asserts the three-pane layout including the menu pane | Update pane expectations |
| `tests/integration/test_list_tui.py`, `test_list_notes_tui.py` | Assume every document is listed regardless of month | Scope to the current month or seed accordingly |
| `tests/integration/test_create_tui.py`, `test_create_note_tui.py`, `test_daily_note_tui.py` | Assert `PreviewScreen` after create | Expect `EditScreen` (FR-026) |
| `tests/integration/test_task_tui.py` | Uses the `a` show-all toggle | Rewrite against the Done category |
| `tests/integration/test_command_bar_visibility.py` | Asserts bar contents without a prefix widget | Account for `#bar-prefix` |
| `tests/unit/` filter tests | Assume bare-word filtering | Rewrite against `/filter` and `/f` |
| `tests/performance/test_scan.py` | Still valid — full scan is still what the CLI does | Keep, add month-scope tests alongside |

The `tests/contract/` suite must keep passing untouched apart from the new `--done` flag: it pins
the CLI's exit codes, `--json` schema, non-blocking behaviour, and no-ANSI-on-non-TTY guarantees,
none of which this feature may change.

> Historical record, accurate as written for 005. Several of the files named above were later
> consolidated by the issue #29 test refactor: `test_list_notes_tui.py` merged into
> `test_list_tui.py`, `test_create_note_tui.py` into `test_create_tui.py`, and
> `test_command_bar_visibility.py` into `test_chrome_tui.py`.
