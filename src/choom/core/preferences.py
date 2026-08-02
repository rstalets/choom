"""The user's own view-orientation preference (020-vertical-tui-mode).

Per-user state, stored outside every workspace (spec.md "Decision: where the
orientation is remembered"; constitution Platform & Distribution Constraints).
A view orientation is a property of one person's monitor, not of a workspace --
a workspace can be a shared OneDrive folder, and storing it in
`.choom/config.toml` would relayout a colleague's screen on sync.

`preferences_root()` is the only function in this module that reads an
environment variable or resolves the user's home directory. Every other path
here is built from its return value, mirroring
`choom.core.discovery.profile_root()` -- patching this one function redirects
the whole module (research R5), which is what `tests/conftest.py`'s autouse
fixture depends on.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TypeVar

from choom.core.atomic_write import write_text_atomic
from choom.core.errors import UsageError, WorkspaceError

LEGAL_VIEW_ORIENTATIONS: tuple[str, ...] = ("horizontal", "vertical")

#: Per the constitution's 2.1.0 owner ruling (issue #81): a user who never
#: types the command gets today's behaviour, with no first-launch question.
DEFAULT_VIEW_ORIENTATION: str = "horizontal"

_VIEW_HEADER = re.compile(r"^\[view\][ \t]*$", re.MULTILINE)
_TABLE_HEADER = re.compile(r"^\[", re.MULTILINE)

_PREFERENCES_FILENAME = "preferences.toml"

_PureFlavour = TypeVar("_PureFlavour", PureWindowsPath, PurePosixPath)


def preferences_root() -> Path:
    """The directory choom keeps this user's own preferences in.

    The only function in this module that reads an environment variable or
    resolves the user's home directory -- every other path this module
    computes is built from this one's return value (research R5), the same
    arrangement `discovery.profile_root()` uses.

    | Platform     | Resolution order                                        |
    |--------------|---------------------------------------------------------|
    | Windows      | `%LOCALAPPDATA%` -> `%APPDATA%` -> `~\\AppData\\Local`  |
    | macOS, Linux | `$XDG_CONFIG_HOME` (if set and absolute) -> `~/.config` |

    An environment variable that is set but empty, or set to a relative
    path, is ignored in favour of the next candidate: a relative base would
    resolve against the process's current working directory, which for
    choom is usually *inside a workspace*, and would drop the preferences
    file into the user's vault. That is the one bug this function must not
    have.

    Reads the home directory via `os.path.expanduser("~")` rather than
    `Path.home()`: the two are equivalent in what they resolve, but
    `Path.home()` -- like `Path(...)` itself -- picks its concrete class
    (`WindowsPath`/`PosixPath`) from `os.name` at call time and raises
    `NotImplementedError` for the class that does not match the *real* host,
    which would make this function impossible to exercise for the foreign
    platform's branch from a single-OS test runner (this project's CI is
    Linux-only). `os.path.expanduser` does no such dispatch, so the
    candidate-selection logic below (`_windows_candidate`/`_posix_candidate`)
    stays pure and unit-testable from any host; only this function ever
    wraps the winning candidate in a real `Path`.

    Never creates the directory. Never raises. Returns a path only; whether
    anything exists there is the caller's problem.
    """
    home = os.path.expanduser("~")
    if os.name == "nt":
        resolved = _windows_candidate(
            os.environ.get("LOCALAPPDATA", ""), os.environ.get("APPDATA", ""), home
        )
    else:
        resolved = _posix_candidate(os.environ.get("XDG_CONFIG_HOME", ""), home)
    return Path(resolved)


def _windows_candidate(localappdata: str, appdata: str, home: str) -> str:
    """Pure candidate selection for Windows: `localappdata`, `appdata`, and
    `home` are values `preferences_root` already read, never read here.
    Returns a plain string rather than a `Path` -- see that function's
    docstring for why -- so this is directly unit-testable without needing a
    real Windows host or an `os.name` patch that would crash `pathlib` on a
    mismatched one.
    """
    for value in (localappdata, appdata):
        candidate = _valid_absolute(value, PureWindowsPath)
        if candidate is not None:
            return str(candidate / "choom")
    return str(PureWindowsPath(home) / "AppData" / "Local" / "choom")


def _posix_candidate(xdg_config_home: str, home: str) -> str:
    """Pure candidate selection for macOS/Linux; see `_windows_candidate`."""
    candidate = _valid_absolute(xdg_config_home, PurePosixPath)
    if candidate is not None:
        return str(candidate / "choom")
    return str(PurePosixPath(home) / ".config" / "choom")


def _valid_absolute(value: str, flavour: type[_PureFlavour]) -> _PureFlavour | None:
    """`value` parsed as `flavour`, or `None` when unset, empty, or not
    absolute -- the guard against a relative base resolving against the
    process's cwd (see `preferences_root`'s docstring)."""
    if not value:
        return None
    candidate = flavour(value)
    if not candidate.is_absolute():
        return None
    return candidate


def _preferences_path() -> Path:
    return preferences_root() / _PREFERENCES_FILENAME


def get_view_orientation() -> str:
    """The user's stored view orientation, or the default.

    Never raises. Returns a member of `LEGAL_VIEW_ORIENTATIONS`, always --
    every failure mode below returns `DEFAULT_VIEW_ORIENTATION`, because a
    hand-edited or damaged preferences file must not stop choom from opening
    (Principle IV; the precedent and its wording come from
    `choom.core.config.get_assistant`). Matching is exact and
    case-sensitive: `"Vertical"` is not a legal value and reads as the
    default.
    """
    try:
        with _preferences_path().open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return DEFAULT_VIEW_ORIENTATION
    table = data.get("view")
    if not isinstance(table, dict):
        return DEFAULT_VIEW_ORIENTATION
    value = table.get("orientation")
    if not isinstance(value, str):
        return DEFAULT_VIEW_ORIENTATION
    return value if value in LEGAL_VIEW_ORIENTATIONS else DEFAULT_VIEW_ORIENTATION


def set_view_orientation(value: str) -> None:
    """Record the orientation, creating the file and its directory if absent.

    Edits the single `orientation` line and no other byte: comments, key
    order, unknown keys, and unknown tables all survive. Writes atomically
    via `write_text_atomic`, which also creates the parent directory. Never
    reads or writes anything inside a workspace -- this function takes no
    `Workspace` and has no way to find one.

    Raises:
        UsageError: `value` is not in `LEGAL_VIEW_ORIENTATIONS`. Nothing is
            written.
        WorkspaceError: the file cannot be read or written. The existing
            file, if any, is left unchanged.
    """
    if value not in LEGAL_VIEW_ORIENTATIONS:
        raise UsageError(f"view must be one of {', '.join(LEGAL_VIEW_ORIENTATIONS)}; got {value!r}")

    path = _preferences_path()
    try:
        # newline="" disables universal-newline translation: plain
        # read_text() would silently collapse "\r\n" to "\n" before the CRLF
        # check below ever saw it.
        with path.open(encoding="utf-8", newline="") as f:
            raw = f.read()
    except FileNotFoundError:
        raw = ""
    except OSError as exc:
        raise WorkspaceError(f"could not read {path}: {exc}") from exc

    newline = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    new_text = _apply_orientation_key(text, value)
    if newline != "\n":
        new_text = new_text.replace("\n", newline)

    write_text_atomic(path, new_text)


def _apply_orientation_key(text: str, value: str) -> str:
    """Line-targeted edit: replace `[view]`'s `orientation` line, insert it
    as the table's first key if the table exists without one, or append the
    whole table if it is absent. Every other byte -- comments, key order,
    unknown keys and unknown tables -- survives. Mirrors
    `choom.core.config._apply_assistant_key`, generalised for `[view]`
    rather than `[assistant]`."""
    raw_value = f'"{value}"'
    if text and not text.endswith("\n"):
        text = text + "\n"

    header = _VIEW_HEADER.search(text)
    if header is None:
        return text + f"\n[view]\norientation = {raw_value}\n"

    body_start = text.index("\n", header.start()) + 1
    next_header = _TABLE_HEADER.search(text, body_start)
    body_end = next_header.start() if next_header else len(text)
    body = text[body_start:body_end]

    key_line = re.compile(r"^orientation\s*=.*$", re.MULTILINE).search(body)
    if key_line is not None:
        new_body = body[: key_line.start()] + f"orientation = {raw_value}" + body[key_line.end() :]
    else:
        new_body = f"orientation = {raw_value}\n" + body

    return text[:body_start] + new_body + text[body_end:]
