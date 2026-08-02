# Phase 1 Data Model: The Terminal Tab Names the Workspace

**Feature**: `016-terminal-tab-title` | **Date**: 2026-08-02

## 1. Persisted state

**None.** This feature stores nothing — not in the workspace, not in per-user local state, not in memory
across runs. It creates no file, opens no file, and adds no key to any existing file or `--json` payload
(FR-018, FR-019, FR-024).

The one piece of state that *looks* like it should be stored — the title the terminal showed before choom
started — deliberately is not. It lives in the terminal's own title stack, pushed on entry and popped on
exit (research R2). choom never learns what it is, which is what keeps this feature stateless and is why
Principle III's "no second source of truth" gate passes without an argument.

## 2. The one derived value

### `WorkspaceTitle` — the composed title text

Not a class. A `str` returned by `workspace_title(workspace: Workspace) -> str`, derived purely from
`Workspace.root`. It is written once to the terminal and never held, compared, or re-read.

**Shape**: `choom — <name>`, or `choom` alone when no name can be derived.

**Derivation, in order:**

| Step | Rule | Requirement |
|---|---|---|
| 1. Source | Take `workspace.root.name` — the final path segment. | FR-002 |
| 2. Root fallback | If that is empty (`/`, `C:\`), take `str(workspace.root)` instead. | FR-002 |
| 3. Sanitise | Keep each character where `ch.isprintable()` is true, or it is a space; drop the rest. | FR-004 |
| 4. Normalise | Collapse runs of whitespace to one space; strip leading and trailing whitespace. | FR-004 |
| 5. Empty check | If nothing survives, the title is `choom` and composition stops. | FR-002 |
| 6. Bound | If `len("choom — " + name) > 64`, replace the name with its first 55 characters plus `…`. | FR-005 |
| 7. Compose | Return `f"choom — {name}"`. | FR-001 |

**Invariants** — each one a unit test:

- **I1**: `len(result) <= 64`, always, for any input. Counted in characters, so a multi-byte name is never
  cut mid-character.
- **I2**: `result` contains no unprintable character. In particular no `\x1b`, `\x07`, `\n`, or `\r`, so
  the value can never terminate the escape sequence it is interpolated into or issue a command of its own.
- **I3**: `result` always starts with `choom`, so every choom tab is recognisable as one even when the
  name is truncated to nothing useful.
- **I4**: The function never raises, for any `Workspace`. There is no failure mode to handle at the call
  site.
- **I5**: Pure — same input, same output; no clock, no filesystem, no environment, no globals. This is
  what makes it testable with no terminal (Principle I).

**Worked examples:**

| `workspace.root` | Result | Why |
|---|---|---|
| `/Users/rs/work-notes` | `choom — work-notes` | The ordinary case. |
| `/Users/rs/Notas de reunión` | `choom — Notas de reunión` | Non-ASCII and spaces pass through (FR-006). |
| `/` | `choom — /` | No final segment; falls back to the path text (FR-002). |
| `C:\` | `choom — C:\` | Same, on Windows. |
| `/tmp/a<BEL>rm -rf` | `choom — arm -rf` | `BEL` dropped; the name can no longer close the sequence (FR-004). |
| `/tmp/<70 chars>` | `choom — <55 chars>…` | Bounded to exactly 64 (FR-005). |
| a name of only control characters | `choom` | Nothing survives sanitising (FR-002). |

## 3. Session state machine

Not stored anywhere — this is the terminal's observable state across one choom run, and it is what the
integration and unit tests assert.

```text
        (stdout is not a TTY, or Windows VT could not be enabled)
   ┌──────────────────────────── no-op ────────────────────────────┐
   │                    nothing is ever written                    │
   ▼                                                               │
UNTOUCHED ──enter: push + set──▶ TITLED ──leave run(): clear + pop──▶ RESTORED
                                   │  ▲
                                   └──┘
                        whole session: no writes (FR-009),
                        including a quit that was cancelled (FR-012)
```

**Transitions:**

| From | Trigger | To | Bytes written |
|---|---|---|---|
| UNTOUCHED | interface starts, stdout is a TTY, VT available | TITLED | `CSI 22;0t` then `OSC 0 ; <title> BEL` |
| UNTOUCHED | stdout is not a TTY **or** VT unavailable | UNTOUCHED | none, for the whole run (FR-015, FR-022) |
| TITLED | any navigation, edit, save, create, delete | TITLED | none (FR-009) |
| TITLED | `ctrl+q` raises the discard confirmation, user cancels | TITLED | none — `run()` has not returned (FR-012) |
| TITLED | `run()` returns or raises, by any route | RESTORED | `OSC 0 ; BEL` then `CSI 23;0t` |
| TITLED | process killed with no teardown | TITLED | none — accepted limit (FR-019) |

The single arrow out of TITLED for every exit route is the point: there is one restore path, not one per
exit kind, which is why `ctrl+q`, a confirmed discard, an unhandled exception and a `KeyboardInterrupt`
cannot diverge from each other.

## 4. Relationship to existing models

`Workspace` (`src/choom/core/models.py`) is read-only input and gains no field. No other core model is
involved. Nothing in `Document`, `Task`, frontmatter, the id scheme, or the file layout is touched, so
`docs/REQUIREMENTS.md` needs no amendment for this feature.
