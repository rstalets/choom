# Phase 0 Research: Read From Disk on View Load

**Feature**: 010-read-on-load | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

All measurements below were taken against `textual==8.2.8` on the repository as of `d0605fc`. The
per-read costs quoted in the spec come from issue #51 and are treated as given.

---

## R1: Where the read happens

**Decision**: Keep `ChoomApp.visible_documents()`, `visible_tasks()` and `visible_warnings()` as the entry
points, but make each one scan the workspace on every call. Delete `_ensure_month_loaded`,
`_ensure_unfiled_loaded` and the four dictionaries behind them.

**Rationale**: These three methods are already the only things `ListScreen.refresh_rows` and
`_render_status` call — the cache sits behind them, not in front. Changing what they do rather than where
they are called from is what lets the entire session snapshot come out without touching the screen's
structure. `on_screen_resume` already rebuilds unconditionally and says so in a comment; it needs no change
at all once these read from disk.

**Alternatives considered**:

- *A `read()` method on the screen instead of the app.* Rejected: `visible_documents` resolves scope,
  filter and collection, which is app state, not screen state. Moving it would relocate logic rather than
  delete it.
- *Passing freshly-scanned documents into `refresh_rows` from each caller.* Rejected: seven call sites
  would each need to know which of month / unfiled / filtered / tasks applies.

---

## R2: A view load stays scoped to what it displays

**Decision**: A list load reads only the displayed month (`scan_month`) or the unfiled set
(`scan_unfiled`) — never the whole collection. Only filtering reads every month.

**Rationale**: Spec 005 established that opening a collection reads only the current month, and
`tests/integration/test_month_scope.py::test_opening_collection_reads_only_current_month` enforces it. That
requirement is unaffected by this feature and is what keeps SC-003 reachable: a month holding 200 documents
scans in 29.4 ms, comfortably inside the 200 ms budget, whereas a full 1,000-document collection scan at
144 ms would spend most of it. The scoped read is also why removing the cache is affordable at all.

**Alternatives considered**:

- *Scan the whole collection on every load and filter in memory.* Rejected on the measurement above: 5×
  the cost for no behaviour gain, on the most frequent path in the app.

---

## R3: One read per render, not one per call

**Decision**: `refresh_rows` performs the read once and keeps the resulting warning count on the screen as
render-local state (`self._warning_count`), which `_render_status` then reads. `visible_warnings()` is no
longer called independently.

**Rationale**: `_render_status` is called from `_on_mode_changed`, which fires on **every keystroke** in the
command bar. If it called `visible_warnings()` and that scanned, typing a filter term would scan the month
once per character. The warning count is display output from the last read, in the same category as the rows
already on screen — not a source of truth, and replaced wholesale by the next read.

**Alternatives considered**:

- *Have `visible_warnings()` scan and accept the cost.* Rejected: turns a 29 ms scan into a per-keystroke
  cost, which is precisely the failure mode R6 exists to avoid.
- *Return documents and warnings together from one method.* Reasonable, and effectively what happens — but
  changing the signature would ripple into the six tests that call `visible_documents()` directly, for no
  behavioural difference.

---

## R4: Detecting "nothing changed" for the refresh timer

**Decision**: Build a comparison key from the read result — for documents, a tuple of
`(id, path, title, type, tags, created, updated)` per row; for tasks, `(id, text, type, tags, done, created)`.
Compare against the key from the previous render. Equal means skip the rebuild entirely.

**Rationale**: FR-010 requires that an unchanged workspace produces no visible change, and rebuilding a
`ListView` unconditionally every two seconds would reset scroll position and flicker. The key is derived
from the data that is actually rendered, so it changes exactly when the display would change. The read still
happens on every tick — only the render is conditional. That keeps the timer honest: it is the same read a
view load performs, with a cheap guard on the redraw.

**Alternatives considered**:

- *Compare file mtimes or a directory stat.* Rejected: introduces a second notion of freshness that can
  disagree with the parsed content (mtime granularity, editors that preserve timestamps), which is the
  "wrong while looking authoritative" failure Principle III and issue #27 both name.
- *Hash the file contents.* Rejected: reads the same bytes twice and detects changes the display does not
  show (a body edit that changes no rendered field).
- *Always rebuild and rely on `refresh_rows(select_id=…)` to hide it.* Rejected: selection survives, scroll
  position does not, and a list that visibly redraws every two seconds is its own bug report.

---

## R5: Timer lifecycle, and when the tick is skipped

**Decision**: `ListScreen.on_mount` registers `self.set_interval(REFRESH_SECONDS, self._refresh_tick)` with
`REFRESH_SECONDS = 2.0`. The timer is paused on `ScreenSuspend` and resumed on `ScreenResume`. The tick
additionally returns early when the command bar is open, or when a filter is active.

**On the interval.** Issue #51 proposed ~10 s. Two seconds is used instead, on the grounds that the read is
not what constrains the choice: a scoped month read is 29.4 ms at 200 documents and the task read is 2.95 ms
at 1,000 tasks, so a 2-second cadence spends under 2% of one core in the worst case and a small fraction of
that on a typical month. Workspaces are expected to be pinned to local disk, and the change-detection guard
in R4 means a quiet workspace costs a scan and no render at all.

The binding constraint is not the disk but the thread: the tick runs on Textual's main thread, so on a month
large enough to scan slowly, a tick landing during a held movement key is a stutter rather than a background
cost. At 2 s a 200-document month occupies roughly 1.5% of the frame budget between ticks; at 1 s it is
3%, for a difference no user perceives as "more live". If a real workspace ever makes this felt, moving the
tick's read to a thread worker and applying the result on the main thread is a contained follow-on that
introduces no new state — deliberately not done now, because it adds result-ordering concerns for a cost
that is currently hypothetical.

**Rationale**: Textual pushes `ScreenSuspend` to a screen when another is pushed over it, so pausing there
gives FR-012 (no refresh while previewing or editing) for free, with no knowledge of which screen is on top.
`Timer.pause()`/`resume()` are the documented controls and exist in 8.2.8.

Two guards on top of that:

- **Command bar open** (FR-013): the user is typing into a widget that lives on this screen, so the screen
  is *not* suspended. Rebuilding the list underneath would fight the filter's own rendering.
- **Filter active** (refines the spec): a filtered view is a full-collection read at 144 ms, and the tick
  runs on the main thread — a 144 ms hitch every two seconds, on a view the user reached by asking a
  point-in-time question. Filtering therefore behaves like the preview: it answers as of when it was asked,
  and reconciles when the filter is cleared, which restores the month scope and takes a normal scoped read.
  **The spec's edge case has been amended to match this**; it previously said the refresh applies to the
  filtered set.

**Alternatives considered**:

- *Run the filtered refresh on a worker thread to avoid the hitch.* Rejected for this feature: it needs
  cancellation, result-ordering against the user's typing, and a rule for what happens when a refresh lands
  mid-term. Real complexity for a view that is by nature a point-in-time query.
- *Stop and recreate the timer instead of pausing.* Rejected: `pause`/`resume` is the supported idiom and
  keeps one Timer object to reason about.

---

## R6: Hydrating the filter set without stalling the keypress

**Decision**: Start a `@work(thread=True, exclusive=True, group="filter-hydrate")` worker from
`ListScreen.action_open_command_bar`, holding the `Worker` on the screen. `_on_filter_changed` — already
`async` — awaits `worker.wait()` before matching. The handle is dropped in `_on_command_bar_closed`.

**Rationale**: Issue #51 proposes starting the scan in the `ModeChanged` handler, but `ModeChanged` is
posted by `CommandBar._on_changed` on **every keystroke**, not only on open — starting it there would
restart the scan per character (`exclusive=True` would cancel and restart, which is worse than not caching).
`action_open_command_bar` is the one place that corresponds exactly to "the bar opened", needs no new
message, and is where `bar.open()` is already called.

A thread worker rather than an async one because `scan_month` is synchronous filesystem work; this matches
the existing precedent at `src/choom/tui/edit_screen.py:479`, the only other worker in the codebase.

Holding the result for the whole bar session (rather than cancelling when a non-filter verb is typed)
satisfies FR-018 and preserves the backspace-and-retype case the issue calls out.

**Alternatives considered**:

- *Read per keystroke with no hydration.* Rejected: 144 ms per character at 1,000 documents.
- *Start hydration lazily on the first `FilterChanged`.* Rejected: that is the keystroke that needs the
  answer, so the wait would be the full 144 ms instead of near-zero — `/f ` gives three keystrokes of
  runway, which is the entire point of starting at open.
- *Keep `app.filter_loading`.* Rejected: the flag is declared at `app.py:83` and read nowhere. With the
  wait handled by `Worker.wait()`, nothing needs it. Deleted rather than wired up.

---

## R7: The preview's two entry paths disagree today

**Decision**: `ListScreen._on_selected` must construct `PreviewScreen(path, _read_document(path))` instead
of passing the row's `Document`.

**Rationale**: `action_open_preview` (`list_screen.py:442`) already reads from disk; `_on_selected`
(`list_screen.py:451`) passes the cached row object. Two ways to open the same screen, one fresh and one
stale. With rows themselves now coming from a fresh scan the gap narrows to at most one refresh interval,
but FR-003 asks for the document as of open, and making both paths identical costs one call.

`PreviewScreen.on_screen_resume` already re-reads via `_read_document` and needs no change.

---

## R8: What replaces the six refresh call sites

**Decision**: Delete `reload_tasks`, `refresh_document`, `_refresh_document_in` and their call sites in
`edit_screen.py` (4) and `app.py` (1, inside `toggle_task_and_track`). In-process freshness comes from two
places instead:

- Returning from the editor or preview fires `ScreenResume` on the list, which already re-reads (FR-002).
- Toggling a task with `space` stays on the list, so `action_toggle_task` calls `refresh_rows()` after the
  write — a read-on-load triggered by an action rather than by navigation.

`toggle_task_and_track` also stops patching `self.tasks` in memory; it reads the task's current state with
the existing `core.tasks.get_task` before writing, and the subsequent `refresh_rows` shows the result.

**Rationale**: FR-006 requires that no writer has to announce what it did. Every deletion here removes a
place where forgetting the call reintroduces the #21 bug — which happened twice on that branch, fixed in
`3db7598`.

**Alternatives considered**:

- *Keep `reload_tasks` as a convenience.* Rejected: a method whose only purpose is to make a stale copy
  fresh is the cache in miniature, and its existence invites new call sites.

---

## R9: Testing a timer without touching the wall clock

**Decision**: Tests call `screen._refresh_tick()` directly and assert on the outcome. One separate test
asserts the interval is registered at `REFRESH_SECONDS`. No test sleeps, and no test waits for a tick to
fire on its own.

**Rationale**: Principle VI forbids tests that depend on the wall clock, and a test that waits for a tick
for a refresh would be both slow and flaky under load. Textual offers no virtual clock for timers in 8.2.8,
so driving the callback directly is the only approach that is neither. The registration test and the
behaviour tests together cover "it is wired up" and "it does the right thing", which is what the interval
actually promises.

**Alternatives considered**:

- *Shorten the interval in tests via monkeypatch and await it.* Rejected: still a real wait, still timing
  dependent, and it tests Textual's scheduler rather than this feature.

---

## R10: Tests that encode the cache as a requirement

Three existing tests assert cache behaviour directly and must change with it:

| Test | Today | After |
|---|---|---|
| `test_month_scope.py::test_filter_reads_each_month_at_most_once_per_session` | Asserts a second filter term re-reads nothing, for the life of the app session | Narrows to the **command-bar session** — the hydration snapshot still makes a second term free; a new bar opening reads again |
| `test_daily_note_tui.py` (helper at line 16) | Reaches into `app.month_cache[…]` to find the created note | Reads through `app.visible_documents()` |
| `test_mirror_reconcile_save.py::test_saving_without_touching_a_mirror_does_not_reload_tasks` | Counts `reload_tasks` calls to prove a save did not rescan | Asserts the user-visible outcome — the mirror is not rewritten — since the method it counts is being deleted |

`test_mirror_propagation.py` (lines 195–206) reads `cached_before`/`cached_after` through
`visible_documents()`; the names become inaccurate but the assertions hold and get renamed rather than
rewritten.

**Rationale**: These encode *how* freshness was achieved rather than *that* the user sees the right thing.
Spec 005's FR-035 ("at most once per session") is narrowed deliberately, not dropped — the property it
protects, that filtering does not re-read per keystroke, is preserved by R6.

---

## Resolved unknowns

| Unknown | Resolution |
|---|---|
| Does Textual 8.2.8 support pausing a screen-owned interval? | Yes — `set_interval(interval, callback, pause=…)` returns a `Timer` with `pause()`, `resume()`, `stop()`, `reset()`. Verified against the installed package. |
| How does a message handler await a thread worker's result? | `await worker.wait()`; `Worker.result` holds it afterwards. `_on_filter_changed` is already a coroutine. |
| Is there an existing worker precedent in this codebase? | Yes — `edit_screen.py:479`, `@work(thread=True)` with `call_from_thread`. |
| Which event fires when the list is covered by preview/edit? | `ScreenSuspend`, with `ScreenResume` on return. Both already used by this codebase. |
| Do any core changes fall out of this? | No. Every read this feature performs already exists in `choom.core` (`scan_month`, `scan_unfiled`, `load_tasks`, `get_task`, `_read_document`). The feature is entirely within `tui/`. |
