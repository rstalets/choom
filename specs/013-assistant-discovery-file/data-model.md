# Phase 1 Data Model: Assistant Discovery File

**Feature**: 013-assistant-discovery-file | **Date**: 2026-08-01

Three things hold state in this feature: the profile that knows where an assistant reads, the
generated file itself, and the one-key record that the launch offer was made. Nothing else is
persisted.

---

## AssistantProfile (extended)

`src/choom/core/models.py` — an existing frozen dataclass, gaining one field.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | existing — `"claude"`, `"copilot"` |
| `display_name` | `str` | existing — used in messages |
| `binary` | `str` | existing — resolved via `shutil.which` |
| `build_args` | `Callable[[str], list[str]]` | existing |
| `discovery_relpath` | `PurePosixPath \| None` | **new** — the file's path relative to the user's profile root, or `None` when this assistant has no user-scope location |

**Values**:

| Assistant | `discovery_relpath` |
|---|---|
| `claude` | `.claude/skills/choom/SKILL.md` |
| `copilot` | `.copilot/instructions/choom.instructions.md` |

**Rules**:

- `None` is FR-017's case: the setting is recorded, no file is written, and the caller reports that
  plainly. It is unreachable with today's two assistants and exists so a future profile cannot crash
  the install path.
- Stored profile-relative, not absolute, so the profile root stays a single seam that tests redirect
  (R13) and `Path.home()` is called in exactly one place.

## DiscoveryFile (generated artifact)

Not a dataclass — a rendered string written to disk. Modelled here because its shape is a contract.

| Element | Rule |
|---|---|
| Wrapper | Per assistant: YAML frontmatter (`name`, `description`) for the Claude skill; a plain markdown heading for the Copilot instructions file. |
| What choom is | One line. |
| Workspace path | The resolved absolute path, alone on its own line, unquoted and unwrapped, so spaces and non-ASCII characters need no escaping rules (FR-018). |
| Pointer | An instruction to read that workspace's `AGENTS.md` before creating or changing anything. |
| Generated-by marker | A fixed, greppable string naming choom and the command that rewrites the file (FR-005), which is also the safety check before deletion (R11). |
| Budget | 20 lines, hard (FR-004). Target 12–16. |
| Forbidden | Any restatement of `AGENTS.md`: layout, frontmatter schema, task line format, link syntax, command list, exit codes (FR-003). |

**Lifecycle**: written in full on every install (FR-006, never merged); deleted only when the marker
is present; never read back by choom for any decision.

**Invariant**: at most one exists across all assistants' locations at any time (FR-008).

## LaunchOfferRecord

A single boolean in the workspace's `.choom/config.toml`, in the existing `[assistant]` table.

```toml
[assistant]
name = "claude"
launch_offer_made = true
```

| Aspect | Rule |
|---|---|
| Written | Once the launch question has been answered, on either key (FR-027). Not written when the app exits with the question still up. |
| Read | Only to decide whether to ask. Never consulted by an install. |
| Cleared | By any explicit set of the assistant (FR-028), including via `init --assistant`. |
| Malformed | A missing file, missing table, absent key, or non-boolean value reads as "not offered" — never raises (Principle IV). |
| Scope | Per workspace, not per assistant. |

**Deliberately not recorded**: which key the user pressed. The shared confirmation has two options
and an `Esc` that may not write, so the answer cannot be stored without giving that key a meaning it
has nowhere else in the tool (R7).

## State transitions — the launch offer

```
                          ┌─ discovery file already installed ──────────┐
                          ├─ assistant is "none" ───────────────────────┤
  choom starts ──────────►├─ two or more assistants, none configured ───┤──► no question
                          ├─ no assistant installed ────────────────────┤
                          └─ launch_offer_made is true ─────────────────┘

  otherwise ─────────────► question shown
                             ├─ Enter ──► install + record assistant + launch_offer_made = true
                             ├─ Esc ────► nothing installed + launch_offer_made = true
                             └─ app exits first ──► nothing written; asked again next launch
```

An install that fails after `Enter` still sets `launch_offer_made` — an unwritable profile directory
must not re-raise the same question at every launch — and reports the failure.

## Relationships

```
Workspace ──1:1──► .choom/config.toml
                       ├── [assistant] name              (existing setting)
                       └── [assistant] launch_offer_made (this feature)

AssistantProfile ──0..1──► DiscoveryFile   (at most one exists across all profiles)
DiscoveryFile ──points at──► Workspace/AGENTS.md   (by absolute path, unmonitored)
```

The pointer is one-directional and unverified: choom writes the workspace path into the file and
never checks afterwards that it still resolves. A workspace that moves leaves a stale pointer until
the assistant is configured again (spec edge case, deliberately out of scope).
