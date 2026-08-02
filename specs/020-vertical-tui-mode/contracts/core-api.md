# Contract: `choom.core.preferences`

**Feature**: `020-vertical-tui-mode` | **Module**: `src/choom/core/preferences.py`

The whole of `core`'s contribution to this feature. Three public functions, no class, no `Workspace`
parameter. Testable with no terminal, no TTY, and no event loop (Principle I).

---

## Constants

```python
LEGAL_VIEW_ORIENTATIONS: tuple[str, ...] = ("horizontal", "vertical")
DEFAULT_VIEW_ORIENTATION: str = "horizontal"
```

`DEFAULT_VIEW_ORIENTATION` is `"horizontal"` per the constitution's 2.1.0 owner ruling. It is a named
constant rather than a literal at each use site so the default has one home.

---

## `preferences_root() -> Path`

The directory choom keeps this user's own preferences in.

**The only function in this module that reads an environment variable or calls `Path.home()`.** Every
other path is built from its return value, so patching this one function redirects the entire module
— the arrangement `discovery.profile_root()` uses and `tests/conftest.py` depends on (research R5).

| Platform | Returns | Resolution order |
|---|---|---|
| Windows | `<base>\choom` | `%LOCALAPPDATA%` → `%APPDATA%` → `~\AppData\Local` |
| macOS, Linux | `<base>/choom` | `$XDG_CONFIG_HOME` (if set and absolute) → `~/.config` |

- An environment variable that is set but empty, or set to a relative path, is ignored in favour of the
  next candidate. A relative base would resolve against the process's working directory — which for
  choom is usually *inside a workspace*, and would drop the file into the user's vault. That is the one
  bug this function must not have.
- Never creates the directory. Never raises.
- Returns a path only; whether anything exists there is the caller's problem.

---

## `get_view_orientation() -> str`

The user's stored view orientation, or the default.

**Never raises.** Returns one of `LEGAL_VIEW_ORIENTATIONS`, always. Every failure mode returns
`DEFAULT_VIEW_ORIENTATION`, because a hand-edited or damaged preferences file must not stop choom from
opening (Principle IV; the precedent and its wording come from `get_assistant`).

| Input condition | Returns |
|---|---|
| File absent | `"horizontal"` |
| `OSError` on open or read | `"horizontal"` |
| `tomllib.TOMLDecodeError` | `"horizontal"` |
| No `[view]` table, or `view` is not a table | `"horizontal"` |
| No `orientation` key | `"horizontal"` |
| `orientation` is not a `str` | `"horizontal"` |
| `orientation` is a `str` not in `LEGAL_VIEW_ORIENTATIONS` | `"horizontal"` |
| `orientation = "horizontal"` | `"horizontal"` |
| `orientation = "vertical"` | `"vertical"` |

Value matching is exact and case-sensitive: `"Vertical"` is not a legal value and reads as the default.
This mirrors `get_assistant`'s `value if value in LEGAL_ASSISTANT_VALUES else None` and keeps the
written form and the typed form the same string.

---

## `set_view_orientation(value: str) -> None`

Record the orientation, creating the file and its directory if absent.

Edits the single `orientation` line and no other byte: comments, key order, unknown keys, and unknown
tables all survive. Writes atomically via `write_text_atomic` (a same-directory temp file plus
`os.replace`), which also creates the parent directory.

**Raises**:

| Exception | When | Guarantee |
|---|---|---|
| `UsageError` | `value` is not in `LEGAL_VIEW_ORIENTATIONS` | **Nothing is written.** Message names the rejected value and lists the accepted ones. |
| `WorkspaceError` | the file cannot be read or written | The existing file, if any, is unchanged — `write_text_atomic` cleans up its temp file on any exception. |

The exception split matches `set_assistant` (`core/config.py:41-56`): an illegal value is the caller's
error, an I/O failure is the environment's. The `WorkspaceError` name is reused rather than a new
exception type added — it is the repo's existing "a file operation choom needed did not work" error,
and its `exit_code` is never consulted on this path because no CLI surface reaches it.

**Behavioural notes**:

- Idempotent. Setting the value already stored rewrites the same bytes and does not raise.
- Never reads or writes anything inside a workspace (FR-024). This function takes no `Workspace` and
  has no way to find one.
- CRLF is preserved when the existing file uses it.

---

## Exports

All three are added to `choom.core.__all__`, alongside the existing surface.

## What this module must not contain

- No `textual`, no `argparse`, no `rich` — enforced by ruff TID251 for `src/choom/core/*`.
- No pane, band, row, or height arithmetic. That is `tui/layout.py` (research R8).
- No `Workspace` parameter, and no workspace path handling of any kind.
- No message formatting for the status bar; the TUI words its own messages from these results.
