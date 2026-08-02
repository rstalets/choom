# Phase 0 Research: The Terminal Tab Names the Workspace

**Feature**: `016-terminal-tab-title` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

Every finding below about Textual was verified by reading the installed `textual==8.2.8` source, not
from memory. Paths are given so a reviewer can check them.

---

## R1 — Does Textual already manage the terminal title?

**Decision**: No. choom owns the title outright; there is nothing to coordinate with or defer to.

**Rationale**: Searched the installed package for title-setting sequences and helpers. The only
`\x1b]`-prefixed OSC in Textual is the **cursor shape** sequence, `f"\x1b]22;{shape}\x07"`
(`textual/_ansi_sequences.py:454` and `textual/app.py:3931`) — OSC 22 is *cursor shape*, unrelated to
the `CSI 22 t` window-title stack this feature uses, despite the coincident number. There is no
`OSC 0`, no `OSC 2`, no `set_terminal_title`, and `App.title` / `App.sub_title` are drawn into the
app's own header widget, never written to the terminal.

**Consequence**: setting `App.title` would *not* rename the tab. The feature genuinely needs its own
emitter, and no Textual behaviour will overwrite what choom sets mid-session (FR-009 is safe).

**Alternatives considered**: Relying on `App.title` — rejected, it does not do this. Asking upstream to
add it — out of scope and unnecessary.

---

## R2 — How is the previous title restored, given no terminal can be safely queried?

**Decision**: Use the terminal's own **title stack** and pair it with a clear, in this exact order.

- **On enter**: `CSI 22;0t` (push icon+window title onto the terminal's stack), then
  `OSC 0 ; <title> BEL` (set).
- **On exit**: `OSC 0 ; BEL` (set an empty title), then `CSI 23;0t` (pop).

**Rationale**: This satisfies both branches of FR-010 *without detecting terminal support*, which is the
whole difficulty. Querying the current title (`CSI 21 t`) is not an option — it is disabled by default in
most terminals precisely because it lets a remote process inject text into the input stream, and a tool
that asks for it is a tool that gets an empty answer or a hang.

The ordering is what makes it work, and it is worth stating plainly because reversing it breaks one case:

| Terminal | `OSC 0 ;` (clear) | `CSI 23;0t` (pop) | Result |
|---|---|---|---|
| Supports the stack | title becomes empty | restores the pushed title | **Exact restore** ✓ |
| Ignores the stack | title becomes empty | ignored silently | **Cleared, shell resumes control** ✓ |

Clear-then-pop gives the right answer in both columns. Pop-then-clear would wipe the title it just
restored on a supporting terminal, and clear alone would never restore. An unsupported `CSI` sequence is
consumed and discarded by every terminal in the target list, so the failure mode is silence, not garbage.

**Alternatives considered**:

- *Clear only.* Simple, always "not stuck on choom's title", but throws away an exact restore on every
  terminal that could have given one. Rejected — FR-010 asks for the exact title where it is available.
- *Push/pop only.* Exact where supported; leaves the tab reading `choom — …` forever where it is not.
  Rejected — that is the precise failure the issue was filed about.
- *Query the title with `CSI 21 t` and replay it.* Rejected: widely disabled, security-sensitive, and it
  turns a fire-and-forget write into a read with a timeout.
- *Guess a replacement (the shell name, the cwd).* Rejected — inventing a title is not restoring one, and
  it would be wrong in the common case where the user's shell sets something specific.

**Sequence details**: `OSC 0` sets icon name *and* window title, which is what the issue specifies and
what the widest range of terminals honours (`OSC 2` sets the window title only and is less uniformly
handled inside multiplexers). The `BEL` (`\x07`) terminator is used rather than `ST` (`\x1b\\`) for the
same reason — it is what tmux, PuTTY, and Windows Terminal all accept without qualification.

---

## R3 — The Windows path, and why ordering decides it

**Decision**: Enable `ENABLE_VIRTUAL_TERMINAL_PROCESSING` with `ctypes` **before** `ChoomApp.run()` is
called, treat failure as "emit nothing at all", and add no dependency.

**Rationale**: Three facts combine, and the third is easy to miss.

1. Windows Terminal interprets escape sequences only when the console handle has
   `ENABLE_VIRTUAL_TERMINAL_PROCESSING` (`0x0004`) set. A legacy `conhost.exe` window may refuse to set
   it — and has no tab strip anyway, so there is nothing there to name.
2. Textual's Windows driver already does this: `win32.enable_application_mode()`
   (`textual/drivers/win32.py:158`) ORs the flag into the output handle's mode when application mode
   starts.
3. **But it also restores.** `enable_application_mode` captures the mode *as it was on entry* and returns
   a `restore()` closure that writes that captured value back; `WindowsDriver.stop_application_mode()`
   (`textual/drivers/windows_driver.py:140`) calls it. So by the time `run()` returns — which is when
   choom writes its restore sequence — Textual has already put the console mode back.

Fact 3 is why choom must enable VT itself rather than lean on Textual. If choom enables it *before*
`run()`, Textual's snapshot at startup already contains the VT bit, so Textual's own restore hands back a
console that is still escape-capable, and choom's exit write lands correctly. Enable it *after*, or not at
all, and the exit write is either garbage or ignored. The call is idempotent, so choom setting a bit
Textual would also set costs nothing.

**Failure handling**: `GetConsoleMode` fails on a redirected handle and `SetConsoleMode` fails where the
host refuses the flag. Either failure means the whole feature is a no-op for that session — no push, no
set, no clear, no pop (FR-022). This is the requirement that keeps a legacy console clean: a half-enabled
path that emitted the sequences anyway would print `←]0;choom — notes` into the user's window.

**Alternatives considered**:

- **`colorama.init()`**, floated in issue #47. **Rejected outright.** It is a third-party dependency
  taken on for one `SetConsoleMode` call that `ctypes` makes in six lines, which fails Principle III's
  "justified by what it would cost to do without" on its own terms. It also does considerably more than
  asked — it wraps `sys.stdout` in a stream that strips or translates ANSI — which is an active hazard
  next to a Textual app that writes escape sequences directly to that same stream. Per the plan gate,
  proposing it would have been a BLOCKED report, not a Complexity Tracking entry.
- *Skip Windows entirely.* Rejected: Windows is a first-class target, and Windows Terminal is exactly
  where a corporate user has ten tabs open.
- *Detect Windows Terminal via `WT_SESSION`.* Rejected as unnecessary sniffing — the console-mode call
  already answers the only question that matters, and the environment variable is absent in legitimate
  cases (SSH into Windows, some launchers).

---

## R4 — Exit paths, and why `ctrl+c` must not be touched

**Decision**: Restore from **process teardown only** — the `finally` of a `with` block wrapping
`ChoomApp.run()`. Register no signal handler and, above all, **bind no key**.

**Rationale**: Constitution Principle V states `ctrl+c` is *fully reserved: it MUST NOT be bound to any
action, in any state*, so it stays a guaranteed way out if the interface is stuck. Any design that
restores the title by handling `ctrl+c` violates that, and would also be pointless. Two things settle it:

- **`ctrl+c` is not an exit path inside a running choom.** Textual binds it itself —
  `Binding("ctrl+c", "help_quit", show=False, system=True)` (`textual/app.py:463`) — and
  `action_help_quit` (`textual/app.py:3990`) merely raises a notification reading *"Press ctrl+q to quit
  the app"*. Its own docstring says "Bound to ctrl+C to alert the user that it no longer quits." So
  pressing `ctrl+c` in choom does not terminate anything, and there is no exit to restore from.
- **Where a `SIGINT` genuinely does terminate the process** — delivered before the driver enters
  application mode, or sent as `kill -INT` — it raises `KeyboardInterrupt`, a `BaseException`. Textual's
  own handler is `except Exception` (`textual/app.py:3515`), which does not catch it, so it propagates out
  of `run()` and straight through the `with` block's `finally`. Covered for free, by structure.

The same `finally` covers every other observable exit with no extra code: a clean `ctrl+q` (`App.exit()`
ends `run()`), a `ctrl+q` that went through issue #64's discard confirmation (same path, one dialog
later), and an unhandled exception (Textual catches it, tears down, and `run()` returns — or it escapes,
and `finally` still runs).

**FR-012 comes free.** A *cancelled* quit must not restore the title. Because restoration is tied to
leaving `run()`, and a cancelled confirmation never leaves it, this is true by construction — there is no
condition to get wrong.

**FR-013 and FR-014 are satisfied by what the teardown does**, which is the constraint the coordinator
flagged: a teardown hook that can throw breaks both. The exit path is two buffered writes and one flush,
with every exception swallowed (see the contract in [contracts/terminal.md](./contracts/terminal.md)). It
cannot delay exit — there is no I/O to wait on beyond a flush to a terminal — and it cannot raise,
change the exit code, or write to stderr.

**Alternatives considered**:

- *`App.on_unmount` / `App.on_exit_app`.* Rejected. It runs inside the Textual lifecycle, so on Windows
  the ordering against `stop_application_mode()` becomes something to reason about per Textual release
  (R3), and it does not cover a failure during app construction or startup.
- *`atexit.register`.* Rejected as redundant and worse: `finally` already covers everything `atexit` would,
  runs at a deterministic point, and does not leave a global registration behind in a test process. It
  also would not help with the cases `atexit` misses anyway (`SIGKILL`, `os._exit`).
- *A `SIGTERM` handler.* Rejected as scope creep for a cosmetic gain; installing a signal handler around a
  running event loop is exactly the kind of complexity Principle III asks to justify, and FR-019 already
  records an un-restored title after a kill as an accepted limit.
- *Binding `ctrl+c`.* Rejected on Principle V. Not a trade-off — a prohibition.

**Noted, not actioned**: Textual's framework defaults do bind `ctrl+c` (to `action_help_quit`, and on
`Screen` to `screen.copy_text`, `textual/screen.py:272`), which sits awkwardly beside Principle V's
"never bound, in any state". That predates this feature and is untouched by it. Raising it belongs in its
own issue, not here; this plan neither depends on the binding nor changes it.

---

## R5 — Where each half lives

**Decision**: `workspace_title()` added to the existing `src/choom/core/workspace.py`; the emitter as a
new `src/choom/tui/terminal_title.py`; wiring in `_run_tui()`.

**Rationale**: The boundary is text versus bytes (spec §"Layering"). Everything with a rule worth testing
— which segment of the path is the name, what happens at a filesystem root, which characters are dropped,
where truncation lands — is string logic over a `Workspace` and belongs in core, where it runs with no
terminal. Everything that knows about `\x1b`, `isatty()`, or `kernel32` is a device concern and may not be
in core.

Core placement in `workspace.py` rather than a new module: a workspace's own display label is workspace
logic, `workspace.py` is where workspace-level functions already live, and its import list (`os`,
`tomllib`, `datetime`, `pathlib`, core siblings) stays clean because the implementation needs no new
import at all. A dedicated `core/titles.py` was considered and rejected — one function is not a domain,
and "title" already means `Document.title` throughout this codebase, so the module name would mislead.

Adapter placement in `tui/` rather than `cli/`, despite `_run_tui()` being the caller: this is what makes
the Principle II guarantee structural. No module reachable from argparse dispatch imports the emitter, so
FR-016 is a property of the import graph and not only of a test.

**Alternatives considered**: composing the string in the adapter and leaving core out entirely — rejected,
that is precisely the "logic left in an adapter" half of Principle I's two-way gate.

---

## R6 — Sanitising and bounding the name

**Decision**: Keep a character when `ch.isprintable()` or it is a space; collapse whitespace runs to a
single space; strip the ends. Then bound the finished title to 64 characters, truncating the name and
marking it with `…` (U+2026).

**Rationale**: A POSIX directory name may legally contain `\n`, `\x1b`, or a `BEL`. Interpolated into
`OSC 0 ; <name> BEL` unfiltered, a `BEL` ends the title early and everything after it is handed to the
terminal as commands — a directory name becomes an injection vector. `str.isprintable()` is the
standard-library answer and needs no import: it is `False` for every C0 and C1 control character, and
also for the `Cf` format characters (zero-width joiners, bidi overrides) that would let a name render as
something other than what it is in a tab strip. Space is added back explicitly because `isprintable()`
excludes separators.

The 64-character bound is fixed here rather than left open, per Principle V. `choom — ` is 8 characters,
so the name gets 56; past that it becomes 55 characters plus `…`, keeping the total exactly 64. The count
is in characters, not bytes, so a multi-byte name is never cut mid-character. The number is chosen to sit
comfortably under what tab strips display while leaving a long OneDrive-style folder name recognisable
from its start.

**Alternatives considered**: a regex over `unicodedata.category` — same result, an extra import and more
to read. Escaping control characters rather than dropping them — rejected, `^[` in a tab title is noise,
and the user gains nothing from seeing it. No bound at all — rejected, an unbounded title is at best
useless and at worst crowds every neighbouring tab.

---

## R7 — Encoding failures

**Decision**: Swallow them, along with every other write failure, and set no title.

**Rationale**: The separator is an em dash and workspace names may be non-ASCII, while a Windows console
under a legacy code page may not be able to encode either — `sys.stdout.write` then raises
`UnicodeEncodeError`. Other realistic failures are `OSError` on a closed or broken stream and `ValueError`
on a stream closed underneath the app at shutdown. None of them is worth a word to the user: the tab title
is a convenience, and FR-014 requires that failing to set it never raises, never touches the exit code,
and never writes to stderr. The emitter catches `Exception` around each write for exactly this reason.

**Alternatives considered**: pre-encoding the title to the stream's encoding with `errors="replace"` —
rejected as more machinery for a case the blanket catch already handles harmlessly, and it would put a tab
full of `?` in front of the user rather than leaving the terminal's own title alone. An ASCII-only
separator — rejected; the issue specifies the em dash, and FR-006 requires non-ASCII names to survive, so
the failure path is needed regardless.

---

## R8 — Test placement

**Decision**: `unit/` for both halves, `contract/` for the CLI prohibition, one `integration/` case for
the wiring. No performance test.

**Rationale**: Principle VI asks for coverage chosen by what can plausibly break, not one test per
acceptance scenario — the spec has 15 scenarios and this is far fewer tests.

- `tests/unit/test_workspace_title.py` — the composition rules, which are where the real edge cases are:
  the truncation boundary either side of 64, unprintable-character removal (including the `BEL` injection
  case), the rootless fallback, and non-ASCII passthrough. Pure function, no fixtures, no terminal.
- `tests/unit/test_terminal_title.py` — the emitter against a fake stream with a controllable `isatty()`:
  silence when not a TTY, the exact bytes on enter and on exit in order, restoration when the body raises,
  and a write that throws being swallowed. A fake stream is what lets the whole emitter be tested off a
  real terminal.
- `tests/contract/test_no_ansi.py` — already asserts `"\x1b" not in` stdout/stderr across much of the
  subcommand surface; extended to the commands it does not yet reach (`config`, `links`, `task show`,
  `task undone`, and the `delete` verbs), which is what turns FR-016 into a standing check.
- `tests/integration/test_tui_launch.py` — one case proving the launcher actually wires the two halves
  together, since a correct core function and a correct emitter that are never connected would pass every
  test above.
- **No `tests/performance/`.** That directory is for scenarios with a real budget to protect. This feature
  does two writes at startup and two at exit and nothing in between (FR-009); there is no budget to
  regress, and a timing assertion here would be a wall-clock flake waiting to happen.

Nothing added reads the clock, so the no-wall-clock rule cannot be violated.
