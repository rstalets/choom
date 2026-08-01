# Contract: View Read and Refresh

**Feature**: 010-read-on-load | **Date**: 2026-08-01

choom's external contract — the CLI's `--json` schemas and exit codes — is **unchanged by this feature**.
Nothing here alters what any command emits or returns; the CLI already reads the workspace on every
invocation, and that is the behaviour the TUI is being brought into line with (Principle II).

What follows is the internal UI contract this feature establishes: when the TUI reads, when it renders, and
what it must never do. It is written as a contract because it is the thing future changes can silently
break — the previous model failed precisely because "remember to refresh" was a convention rather than a
rule.

---

## C1: Every displayed record comes from a read taken at display time

**Guarantee**: What a list shows is what the scoped read returned. There is no other source.

**Triggers a read**:

| Trigger | Scope of the read |
|---|---|
| `ListScreen.on_mount` | The displayed month, or unfiled, or the task file |
| `ListScreen.on_screen_resume` (returning from preview, edit, help, dialog) | Same |
| Collection switch (`tab`, `/meetings`, `/notes`, `/tasks`) | Same, for the new collection |
| Scope change (month row, unfiled row, task category) | Same, for the new scope |
| `action_toggle_task` (`space`) | The task file |
| Record created in-app (`/meeting`, `/note`, `/task`, daily note) | The scope the new record lands in |
| Refresh tick, subject to C4 | The currently displayed scope |
| Opening the preview, by `enter` or by `o` | The single file being opened |
| First `FilterChanged` after the command bar opens | Every month plus unfiled, on a worker thread |

**Forbidden**: retaining a parsed `Document`, `Task`, or `ScanWarning` past the render that displayed it,
for the purpose of avoiding a later read. The two exceptions are enumerated in
[data-model.md §3](../data-model.md) and justified in the plan's Complexity Tracking; both gate work, not
truth.

---

## C2: No writer announces itself

**Guarantee**: Code that writes to the workspace is not required to tell any view what it did. Correctness
does not depend on a notification.

**Forbidden**: any method whose purpose is to make a retained copy agree with disk — the shape of
`reload_tasks`, `refresh_document`, and `_refresh_document_in`, all deleted here. A new one reintroduces the
class of bug this feature removes: six writers against four hand-placed refresh calls, two of which were
added only after they had already been missed.

**Consequence for reviewers**: a PR that adds a call like `app.refresh_x()` after a write is a signal that
something is being cached again.

---

## C3: A read is scoped to what is displayed

**Guarantee**: A list load reads one month, or the unfiled set, or the task file. It does not read the whole
collection.

**Rationale**: this is what keeps SC-003 reachable (29.4 ms for a 200-document month against 144 ms for a
1,000-document collection), and it preserves the requirement established by spec 005 and enforced by
`tests/integration/test_month_scope.py::test_opening_collection_reads_only_current_month`.

**The one exception**: filtering matches across every month by definition, so it reads the collection — on a
worker thread, started when the command bar opens (C5).

---

## C4: The refresh tick reads always, renders only on change

**Guarantee**: While a list is displayed and unobstructed, the workspace is re-read every
`REFRESH_SECONDS = 2.0`. The screen is rebuilt only if a rendered field changed.

**The tick does nothing when**:

- the screen is suspended (a preview, editor, help screen or dialog is on top) — the timer is paused, so no
  tick fires at all;
- the command bar is open;
- a filter is active.

**When it does render**:

- selection is preserved by record id, not by row index (`refresh_rows(select_id=…)`);
- focus is not moved;
- no message is posted that another handler could interpret as user input.

**Forbidden**: rebuilding the list when the comparison key is unchanged; skipping the *read* because the key
was unchanged last time.

---

## C5: The filter's read is started by the bar opening and held for its session

**Guarantee**: Pressing `/` starts a full-collection read on a worker thread and returns immediately. The
first filter term typed waits for that read to finish, then matches against all of it.

**Contract details**:

- Started in `action_open_command_bar`, **not** in the `CommandBar.ModeChanged` handler — that message is
  posted on every keystroke, so starting there would restart the read per character (research R6).
- `@work(thread=True, exclusive=True)`: filesystem work does not belong on the event loop, and exclusivity
  means a second `/` supersedes rather than races.
- Held for the whole bar session, including across a non-filter verb being typed and erased (FR-018).
- Dropped when the bar closes. A filter still displayed after the bar closes is a point-in-time answer; it
  is not refreshed (C4), and clearing it restores the month scope, which reads normally.

**Forbidden**: blocking the `/` keypress on the read; matching against a partially hydrated set.

---

## C6: Malformed files degrade, never fail

**Guarantee** (restates Principle IV under a higher read frequency): a file that cannot be parsed is skipped
with a warning on **every** read. The warning count shown in the status bar describes the read that produced
the currently displayed rows.

**Forbidden**: raising out of a view load; presenting a partially failed read as an empty workspace;
accumulating warnings across reads so the count only ever grows.

---

## Verification

Each clause maps to at least one test; see [quickstart.md](./../quickstart.md) for how to run them.

| Clause | Verified by |
|---|---|
| C1 | `integration/` — out-of-process create, delete, edit, and task completion, each observed after navigation |
| C2 | `integration/` — a checkbox ticked in a document body shows as done in the Tasks list with no refresh call wired |
| C3 | `integration/test_month_scope.py::test_opening_collection_reads_only_current_month` (existing, unchanged) |
| C4 | `integration/` — tick with no change performs no rebuild; tick with a change preserves selection. `unit/` — the comparison key. Neither sleeps (research R9) |
| C5 | `performance/` — `/` returns before hydration completes; `integration/` — verb-then-backspace-then-filter still matches immediately |
| C6 | `integration/` — a malformed file added out of process is skipped and counted on the next load |
