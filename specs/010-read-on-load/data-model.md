# Phase 1 Data Model: Read From Disk on View Load

**Feature**: 010-read-on-load | **Date**: 2026-08-01 | **Plan**: [plan.md](./plan.md)

This feature adds no entity. Its data model is a ledger of state: what comes out, what stays, and the two
short-lived structures that go in. Entity definitions themselves (`Document`, `Task`, `ScanWarning`,
`YearMonth`) are unchanged in `choom.core.models`.

---

## 1. State removed

All of it lives on `ChoomApp` (`src/choom/tui/app.py`) or is called from `EditScreen`.

| State | Type | Lifetime today | Why it goes |
|---|---|---|---|
| `month_cache` | `dict[tuple[str, YearMonth], list[Document]]` | App session | The snapshot itself. Populated once per month, invalidated nowhere |
| `month_warnings` | `dict[tuple[str, YearMonth], list[ScanWarning]]` | App session | Warnings frozen at first read; FR-007 requires them current |
| `unfiled_cache` | `dict[str, list[Document]]` | App session | Same as `month_cache` for the unfiled set |
| `unfiled_warnings` | `dict[str, list[ScanWarning]]` | App session | Same as `month_warnings` |
| `fully_loaded` | `set[str]` | App session | Records that a filter has loaded every month. Only meaningful with a cache |
| `tasks` | `list[Task]` | App session | Parsed once at mount, patched in place by three writers |
| `task_warnings` | `list[ScanWarning]` | App session | Same as `tasks` |
| `filter_loading` | `bool` | App session | Declared at `app.py:83`, read nowhere. Dead on arrival |
| `_ensure_month_loaded` | method | — | Lazy-load guard; a read that always reads needs no guard |
| `_ensure_unfiled_loaded` | method | — | Same |
| `reload_tasks` | method | — | Re-parses `tasks.md` into the cache. Four call sites, two added only after they were missed |
| `refresh_document` | method | — | Re-parses one file into the cache. Two call sites |
| `_refresh_document_in` | method | — | Insert/replace/delete inside one cached list |

**Behavioural consequences of the removals**

- `_track_created` no longer inserts the new document into `month_cache`. It keeps its other job: setting
  the active collection, clearing the filter, and selecting the created record's month.
- `add_task_and_track` no longer appends to `self.tasks`; the caller's `refresh_rows` shows the new task.
- `toggle_task_and_track` no longer patches `self.tasks` or calls `refresh_document` on propagated files. It
  reads the task's current state with `core.tasks.get_task`, writes, propagates, and lets the caller
  re-render.

---

## 2. State retained

Everything here is **user intent**, not workspace content. None of it is derived from a file, so none of it
can be stale.

| State | Type | Meaning |
|---|---|---|
| `workspace` | `Workspace` | Which vault is open |
| `active` | `str` | Which collection is showing: `meetings`, `notes`, `tasks` |
| `month_scope` | `dict[str, YearMonth]` | Which month each collection is scoped to |
| `scope_selection` | `dict[str, ScopeSelection]` | Month or `"unfiled"`, per collection |
| `task_category` | `str` | `todo` or `done` |
| `filter_query` | `str` | The active filter term |
| `pre_filter_scope` | `YearMonth \| None` | Month to restore when the filter clears |
| `last_create_error`, `last_task_error` | `str \| None` | Message for the status bar from the last action |

`ListScreen._pending_select_id` and `_pending_error` likewise stay: they carry an intention across a screen
transition, not a copy of a file.

---

## 3. State introduced

Two structures, both justified in the plan's Complexity Tracking table.

### 3.1 Filter hydration snapshot

| Property | Value |
|---|---|
| Where | `ListScreen`, as a `Worker[list[Document]]` handle |
| Created | `action_open_command_bar` — the moment `/` opens the bar |
| Read | `_on_filter_changed`, via `await worker.wait()` before matching |
| Destroyed | `_on_command_bar_closed` |
| Contents | Every document in the active collection: all months plus unfiled |
| Staleness ceiling | One command-bar session |

**Invariants**

- Never consulted when the command bar is closed. A filter that survives the bar closing re-reads normally.
- Never partially consumed: `_on_filter_changed` waits for completion rather than matching a partial set
  (FR-017).
- Not cancelled when a non-filter verb is typed (FR-018).
- `exclusive=True` in the worker group, so a second `/` while one is in flight replaces it rather than
  racing it.

### 3.2 Last-render comparison key

| Property | Value |
|---|---|
| Where | `ListScreen`, alongside the rendered rows |
| Created | End of every `refresh_rows` |
| Read | `_refresh_tick`, compared against the key built from the tick's read |
| Destroyed | Replaced on each render; dropped with the screen |
| Contents (documents) | Per row: `(id, path, title, type, tags, created, updated)` |
| Contents (tasks) | Per row: `(id, text, type, tags, done, created)` |

**Invariants**

- Derived from a read that has already happened; never consulted instead of reading.
- Covers exactly the fields `DocumentRow._row_text` / `TaskRow._row_text` render, plus `updated` and `path`
  so that an edit which changes no visible field still counts as a change for the preview pane.
- Equality means "skip the redraw", never "skip the read".

### 3.3 Render-local warning count

Not state so much as render output, but worth naming because `_render_status` currently recomputes it:
`ListScreen` keeps the warning count from the last read so that `_render_status` — called on every command-bar
keystroke via `ModeChanged` — does not trigger a scan per character (research R3). It is replaced wholesale
by the next read.

---

## 4. Read paths after the change

| View | Read performed | Core call | Cost at target scale |
|---|---|---|---|
| Meetings/Notes, month scope | That month only | `scan_month` | 29.4 ms / 200 docs |
| Meetings/Notes, unfiled | Unfiled set only | `scan_unfiled` | Proportional to unfiled count |
| Tasks | Whole task file | `load_tasks` | 2.95 ms / 1,000 tasks |
| Filter (any collection) | The whole collection, one walk | `scan_documents` | 147 ms / 1,000 docs — on a worker thread |
| Preview open | One file | `_read_document` | Single file parse |
| Scope pane | Directory listing only | `list_months` | Directory walk, no file reads |

---

## 5. State transitions

The refresh tick is the only new state machine, and it has no persistent state of its own:

```text
                 ┌──────────────────────────────────────────┐
                 │ ListScreen mounted                       │
                 │ set_interval(2.0s, _refresh_tick)        │
                 └───────────────┬──────────────────────────┘
                                 │
                    ScreenSuspend│  ScreenResume
                  (preview/edit  │  (return to list)
                   pushed over)  │
                                 ▼
              ┌────────── timer.pause() ◄──► timer.resume() ──────────┐
              │                                                       │
              ▼                                                       ▼
        (no ticks fire)                                     _refresh_tick()
                                                                      │
                            ┌─────────────────────────────────────────┤
                            │ command bar open?  ──────── yes ────────► return
                            │ filter active?     ──────── yes ────────► return
                            ▼ no
                        read from disk (scoped)
                            │
                            ▼
                   key == last render key?
                        │           │
                       yes          no
                        │           │
                        ▼           ▼
                    return    refresh_rows(select_id=current)
```

`ScreenResume` already calls `refresh_rows` independently of the timer, so returning to the list reads
immediately rather than waiting up to 2 seconds.
