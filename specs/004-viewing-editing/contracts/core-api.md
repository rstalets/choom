# Contract: `endpaper.core` public API (viewing and editing)

**Baseline**: [feature 002's core-api contract](../../002-general-notes/contracts/core-api.md). This
page records what this feature adds and the one thing it breaks. Anything not mentioned is unchanged.

**Hard rule, unchanged**: nothing in `core` imports `argparse`, `textual`, `rich`, or `sys.stdout`.
The existing import-walk test (`tests/unit/test_core_imports.py`) covers `core/editing.py` with no
edit.

---

## Module layout

| Module | Role |
|---|---|
| `core/editing.py` | **new** — `load_for_edit`, `save_buffer`, `stamp_updated`. The whole save path. |
| `core/models.py` | **changed** — adds `EditableFile`, `SaveResult`, `InitResult`. |
| `core/workspace.py` | **changed** — `init_workspace` writes `CLAUDE.md`, never clobbers, reports. |
| `core/frontmatter.py` | **unchanged** — `render_frontmatter` is deliberately *not* on the save path. |

`editing.py` holds no knowledge of collections, partitions, or document types. It takes a `Path` and
returns bytes-level outcomes. If it grows a branch on collection, [R10](../research.md#r10-what-this-feature-deliberately-does-not-touch) has been broken.

---

## New functions

```python
def load_for_edit(path: Path) -> EditableFile:
    """Read a file for editing: whole text including frontmatter, normalised to "\\n",
    with the line-ending convention and trailing-newline state captured for restoration.

    Raises:
        OSError: the file cannot be read.
    """


def stamp_updated(text: str, timestamp: str) -> tuple[str, bool]:
    """Replace the value on the frontmatter block's first `updated:` line, changing no
    other byte. Returns (new_text, True) when stamped, (text, False) when the block or
    the line could not be located. Never raises.
    """


def save_buffer(
    path: Path,
    text: str,
    file: EditableFile,
    *,
    now: datetime | None = None,
) -> SaveResult:
    """Stamp `updated`, restore `file`'s line endings and trailing newline, and write
    atomically to `path` via a same-directory temp file and os.replace.

    Never raises on a write failure -- returns SaveResult(ok=False) with a
    user-facing message, leaving the target byte-identical.
    """
```

### Guarantees these functions make

| Guarantee | Requirement |
|---|---|
| `save_buffer` changes only the `updated:` line of the caller's text | FR-016 |
| `created` is never read or written by any of the three | FR-017 |
| A failed write leaves the target byte-identical and unlocked | FR-020 |
| `stamp_updated` never raises, for any input including `""` | FR-018, Principle IV |
| No function here opens, reads, or writes any path but the one passed | FR-023 |
| All three are callable with no terminal, no event loop, no workspace | Principle I |

---

## Changed function — **breaking**

```python
# before (features 001-003)
def init_workspace(target: Path) -> Workspace: ...

# after (this feature)
def init_workspace(target: Path) -> InitResult: ...
```

`InitResult.workspace` carries what the old return value was. Behaviour changes:

| Before | After | Requirement |
|---|---|---|
| `AGENTS.md` written unconditionally, clobbering an existing one | written only if absent, via `O_EXCL` | FR-050 |
| no `CLAUDE.md` | written if absent, via `O_EXCL` | FR-045 |
| caller cannot tell what happened | `written` / `skipped` name each guidance file | FR-051 |
| existing workspace raises `WorkspaceError` | unchanged | — |

**Migration** — 8 call sites across 6 files, each a mechanical `.workspace` suffix:

| File | Line(s) |
|---|---|
| `src/endpaper/cli/main.py` | 110 — takes the `InitResult` and reports `skipped` on stderr |
| `tests/conftest.py` | 16 — `return init_workspace(tmp_path).workspace` |
| `tests/integration/test_unicode_paths.py` | 13, 27 |
| `tests/integration/test_note_parity.py` | 47 |
| `tests/integration/test_create_parity.py` | 47 |
| `tests/fixtures/generate.py` | 18, 37 |

`cli/main.py` is the only one that does more than append `.workspace`. `core/__init__.py:45` keeps
exporting `init_workspace` under the same name; only its return type moves.

Recorded in CHANGELOG as **0.0.3**, per Principle VI.

---

## New types

Added to `core/models.py`. Field-level rules in [data-model.md](../data-model.md).

```python
@dataclass(frozen=True, slots=True)
class EditableFile:
    path: Path
    text: str                  # normalised to "\n"
    newline: str               # "\r\n" | "\n"
    trailing_newline: bool

@dataclass(frozen=True, slots=True)
class SaveResult:
    ok: bool
    saved_text: str
    stamped: bool
    message: str

@dataclass(frozen=True, slots=True)
class InitResult:
    workspace: Workspace
    written: tuple[str, ...]
    skipped: tuple[str, ...]
```

---

## Re-exports

Added to `core/__init__.py`:

```
EditableFile, SaveResult, InitResult, load_for_edit, save_buffer, stamp_updated
```

`render_frontmatter` stays exported and stays off this feature's write path. Anyone who reaches for
it while implementing a save has taken the wrong turn — see [R1](../research.md#r1-the-updated-stamp-is-surgical-not-a-re-render).

---

## Packaged data

| File | Status | Constraint |
|---|---|---|
| `core/templates/AGENTS.md.tmpl` | unchanged | ≤ 60 lines (currently 58) |
| `core/templates/CLAUDE.md.tmpl` | **new** | ≤ 12 lines; contains `AGENTS.md`; contains no convention |

Both ship through the existing `[tool.hatch.build.targets.wheel.force-include]` entry, which already
covers the whole `templates` directory. **No `pyproject.toml` change.**
