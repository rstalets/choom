"""Set and restore the terminal tab title around a choom TUI session.

This module is the only code in choom that writes a terminal-title escape
sequence and the only code that calls into the Windows console API. It has
exactly one importer, `_run_tui()` in `choom.cli.main`, which `main()` reaches
only on the interactive path -- no `argparse` dispatch route pulls this module
in, which is what keeps FR-016 (no CLI subcommand ever emits a title sequence)
a property of the import graph rather than only of a test.
"""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

# Push the icon name and window title onto the terminal's title stack.
PUSH = "\x1b[22;0t"
# Set the icon name and window title to `<title>`.
SET = "\x1b]0;{title}\x07"
# Set them to empty.
CLEAR = "\x1b]0;\x07"
# Pop the saved title back off the stack.
POP = "\x1b[23;0t"

_STD_OUTPUT_HANDLE = -11
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004


def _enable_windows_vt() -> bool:
    """Ensure the console interprets escape sequences. True when it will."""
    if os.name != "nt":
        # macOS and Linux need no console-mode change (FR-023).
        return True
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        new_mode = mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
        if not kernel32.SetConsoleMode(handle, new_mode):
            return False
        return True
    except Exception:
        return False


@contextmanager
def terminal_title(title: str, *, stream: TextIO | None = None) -> Iterator[None]:
    """Name the terminal tab for the duration of the block, then put it back."""
    active_stream: TextIO = stream if stream is not None else sys.stdout
    entered = False
    try:
        if active_stream.isatty() and _enable_windows_vt():
            # One write call so PUSH and SET cannot be split across two.
            active_stream.write(PUSH + SET.format(title=title))
            active_stream.flush()
            entered = True
    except Exception:
        entered = False
    try:
        yield
    finally:
        if entered:
            try:
                # Order matters and is load-bearing: CLEAR before POP restores
                # exactly on a terminal with a title stack (the pop wins) and
                # clears on one without (the pop is ignored). Reversed, this
                # would wipe the title it just restored on every stack-capable
                # terminal.
                active_stream.write(CLEAR + POP)
                active_stream.flush()
            except Exception:
                pass
