# Contract: Terminal emission

**Feature**: `016-terminal-tab-title` | **Date**: 2026-08-02

The adapter half. This is the only code in choom that writes a terminal-title escape sequence, and the
only code that calls into the Windows console API.

**Module**: `src/choom/tui/terminal_title.py`

---

## T1 — The sequences

| Name | Bytes | Meaning |
|---|---|---|
| `PUSH` | `\x1b[22;0t` | Push the icon name and window title onto the terminal's title stack. |
| `SET` | `\x1b]0;<title>\x07` | Set the icon name and window title to `<title>`. |
| `CLEAR` | `\x1b]0;\x07` | Set them to empty. |
| `POP` | `\x1b[23;0t` | Pop the saved title back off the stack. |

`<title>` is the string returned by `workspace_title()` and is interpolated verbatim — it is guaranteed
free of control characters by that function's G2, which is what makes this interpolation safe.

`BEL` (`\x07`) is the OSC terminator rather than `ST` (`\x1b\\`); `OSC 0` is used rather than `OSC 2`.
Both choices are for breadth of support across the target terminals — see research R2.

---

## T2 — `terminal_title`

```python
@contextmanager
def terminal_title(title: str, *, stream: TextIO | None = None) -> Iterator[None]:
    """Name the terminal tab for the duration of the block, then put it back."""
```

`stream` defaults to `sys.stdout` and exists so tests can pass a fake with a controllable `isatty()`;
production has exactly one caller and never passes it.

**On enter, in order:**

1. If `not stream.isatty()` → write nothing, now or on exit, and yield. (FR-015)
2. If `os.name == "nt"` and Windows VT cannot be enabled (T3) → write nothing, now or on exit, and yield.
   (FR-022)
3. Otherwise write `PUSH + SET`, flush, and yield. One write call, so the two sequences cannot be split.

**On exit — in a `finally`, so it runs however the block is left:**

4. If enter wrote nothing, write nothing. Otherwise write `CLEAR + POP` and flush.

Order matters and is asserted: `CLEAR` before `POP` restores exactly on a terminal with a title stack and
clears on one without, from a single sequence with no detection. Reversing them loses the restore.

**Guarantees** (each a unit test in `tests/unit/test_terminal_title.py`):

| # | Guarantee | Requirement |
|---|---|---|
| E1 | Nothing is written at all when `stream.isatty()` is `False`. | FR-015 |
| E2 | Enter writes exactly `PUSH + SET`; exit writes exactly `CLEAR + POP`. Nothing else, ever. | FR-008, FR-010 |
| E3 | Exit sequences are written when the block raises, and the exception still propagates unchanged. | FR-011 |
| E4 | Nothing is written between enter and exit. | FR-009 |
| E5 | A `stream.write` or `stream.flush` that raises any `Exception` is swallowed: no traceback, no stderr output, no change to what the block returns or raises. | FR-014 |
| E6 | Enabling Windows VT is attempted only when `os.name == "nt"`. | FR-023 |

**Failure policy**: every write and flush is wrapped so that `OSError`, `ValueError` (closed stream), and
`UnicodeEncodeError` (a console code page that cannot encode the em dash or a non-ASCII name) are caught
and discarded. Nothing in this module can raise into its caller, and nothing it does can change an exit
code (FR-014).

**Timing**: the exit path is one buffered write and one flush, performed after `run()` has already
returned. It cannot add a perceptible delay, a keystroke, or a prompt (FR-013).

---

## T3 — Windows console mode

```python
def _enable_windows_vt() -> bool:
    """Ensure the console interprets escape sequences. True when it will."""
```

- `os.name != "nt"` → return `True` immediately, having called nothing. macOS and Linux need no
  console-mode change (FR-023).
- On Windows: `ctypes.windll.kernel32`, `GetStdHandle(-11)` for `STD_OUTPUT_HANDLE`, `GetConsoleMode`,
  then `SetConsoleMode` with `ENABLE_VIRTUAL_TERMINAL_PROCESSING` (`0x0004`) ORed into the current mode.
- Any failure — `GetConsoleMode` returning false on a redirected handle, `SetConsoleMode` refused by a
  legacy console host, or any exception from `ctypes` — returns `False`, and the caller then emits
  nothing for the whole session (FR-022). A legacy console never sees a literal `←]0;…`.
- Standard library only. `ctypes` ships with Python; no third-party package is added (research R3 records
  why `colorama` is rejected).
- No elevation and no network are involved: the call operates on the process's own stdout handle.

**Ordering, which is the part that is easy to get wrong.** `_enable_windows_vt()` must run **before**
`ChoomApp.run()`. Textual's Windows driver snapshots the console mode when it starts application mode and
writes that snapshot back when it stops (`textual/drivers/win32.py:158`,
`textual/drivers/windows_driver.py:140`). Enabling VT first means the snapshot already carries the VT bit,
so the console is still escape-capable when the exit sequences are written after `run()` returns. Enabling
it later, or relying on Textual to do it, leaves the exit write landing on a console that has just had VT
turned back off.

---

## T4 — Wiring

`src/choom/cli/main.py::_run_tui()`, after the existing TTY refusal and workspace resolution:

```python
with terminal_title(workspace_title(workspace)):
    ChoomApp(workspace).run()
```

**What this placement buys, and why it is not `on_mount`/`on_unmount`:**

- The `finally` covers a clean `ctrl+q`, a `ctrl+q` that went through the discard confirmation, an
  unhandled exception, and a `KeyboardInterrupt` — with **no key binding**, which Principle V requires for
  `ctrl+c` (research R4).
- FR-012 is true by construction: a cancelled quit never leaves `run()`, so `finally` never fires.
- It also covers a failure during app construction or first paint, which an in-app hook would not.
- On Windows it puts the VT enable before Textual's snapshot and the restore after Textual's teardown,
  which is the ordering T3 requires.

**Principle II**: `terminal_title` lives in `choom/tui/` and its only importer is `_run_tui()`, which
`main()` reaches solely when `argv` is empty. No module on the argparse dispatch path imports it, so
FR-016 holds as a property of the import graph and not only of a test.
`tests/contract/test_no_ansi.py` asserts it anyway, extended here to the subcommands it does not yet
reach.
