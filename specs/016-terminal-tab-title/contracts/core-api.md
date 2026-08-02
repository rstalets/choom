# Contract: `choom.core` API

**Feature**: `016-terminal-tab-title` | **Date**: 2026-08-02

One function is added to `choom.core`. Nothing existing changes signature or behaviour.

---

## C1 — `workspace_title`

**Module**: `src/choom/core/workspace.py`
**Exported**: yes — added to `choom.core.__all__`, importable as `from choom.core import workspace_title`

```python
def workspace_title(workspace: Workspace) -> str:
    """The terminal title identifying a choom session on `workspace`.

    Returns `"choom — <name>"`, where `<name>` is the workspace root's final path
    segment (falling back to the root's full path text when it has no final
    segment, as at a filesystem or drive root). Unprintable characters are
    dropped, whitespace runs are collapsed, and the result is bounded to 64
    characters with a trailing `…` when the name is longer. Returns `"choom"`
    alone when no usable name survives.

    Pure: no I/O, no clock, no environment. Never raises.
    """
```

**Guarantees** (each is a unit test in `tests/unit/test_workspace_title.py`):

| # | Guarantee |
|---|---|
| G1 | `len(workspace_title(w)) <= 64` for every `w`. |
| G2 | The result contains no unprintable character — in particular no `\x1b`, `\x07`, `\n`, `\r`. |
| G3 | The result always begins with `choom`. |
| G4 | Never raises, for any `Workspace`, including roots that are empty, adversarial, or non-existent on disk. |
| G5 | Pure — repeated calls with the same input return the same string, with no filesystem access. |
| G6 | Spaces and non-ASCII characters in the name survive verbatim, subject only to G1 and G2. |

**Boundary cases the tests pin:**

- Name of exactly 56 characters → title is exactly 64, not truncated.
- Name of 57 characters → truncated to 55 plus `…`, title exactly 64.
- Root `/` and root `C:\` → `choom — /` and `choom — C:\`.
- Name containing `\x07` → the `\x07` is absent from the result.
- Name of only control characters → exactly `choom`.

**Non-guarantees, stated so no caller assumes them:**

- The string is *not* an escape sequence and contains no terminator. Wrapping it for a device is the
  adapter's job (see [terminal.md](./terminal.md)).
- No claim is made that the result is encodable in any particular character set. A caller that cannot
  encode it must handle that itself; the contract for the one caller that exists is to swallow it (FR-014).

**Principle I compliance**: the function takes an in-memory `Workspace` and returns a `str`. It touches no
stream, no TTY, no event loop, and adds no import to `workspace.py`. `choom.core` remains free of
`argparse`, `textual`, and `rich` (ruff TID251) and free of any `sys.stdout` reference
(`tests/unit/test_core_imports.py`).

---

## C2 — Unchanged surfaces

Stated explicitly because the gate asks:

- No existing `core` function changes signature, return type, or behaviour.
- No `--json` payload gains, loses, or renames a key.
- No exit code is added, removed, or repurposed. The registry in `docs/REQUIREMENTS.md` is unchanged.
- No CLI subcommand, flag, or help text changes.
- No workspace setting is added, so `.choom/config.toml` keeps its current shape and schema version.
