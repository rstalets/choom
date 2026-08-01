# Data Model: Local AI Assistant Invocation

**Feature**: `006-ai-assistant-invocation` | **Date**: 2026-07-30

Five entities. Four are in-memory value objects; only **AssistantSetting** is persisted, as one key
in a file endpaper already owns. No new file, no new source of truth (Principle III).

---

## EditorCommand

A command word usable from inside the editor. The table is the single source for what the parser
accepts and what the help pane lists — a command cannot exist without appearing in help (FR-004),
the same one-table-many-consumers rule the command bar's verb table already follows.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | The word after `/`. Matched lowercase. |
| `argument` | `str` | Display form of the argument, e.g. `<prompt>`. Empty when the command takes none. |
| `description` | `str` | One line, shown in the help pane. |
| `requires_argument` | `bool` | When `True`, a bare `/name` reports that an argument is required (FR-007) instead of being treated as text. |

**Table for this feature** — one entry:

| `name` | `argument` | `description` | `requires_argument` |
|---|---|---|---|
| `ai` | `<prompt>` | Ask the configured assistant; the reply replaces this line | `True` |

`/task` and other in-editor commands are named in the spec to shape the framework and are **not**
added here (spec Assumptions). Adding one is a row in this table plus a handler — no change to
parsing, dispatch, or display (FR-003).

**Frozen dataclass, module-level tuple.** Mirrors `tui/commands.py::VERB_TABLE`, but lives in
`core` because parsing must be testable without a terminal.

---

## ParsedCommand

The result of parsing one submitted line. Produced by `parse_line`, consumed by the editor.

| Field | Type | Notes |
|---|---|---|
| `command` | `EditorCommand` | The matched table entry. |
| `argument` | `str` | Everything after the command word, stripped. May be empty. |

`parse_line` returns `ParsedCommand | None`. `None` means "this line is ordinary document text" and
is the answer for every case in FR-001/FR-002: `/ai` mid-line, `/aim`, `//ai`, `/summarise`, a line
with leading whitespace, and a plain sentence. **The parser never raises** (Principle IV) — a line
it does not understand is a line the user typed, not an error.

---

## AssistantProfile

A supported assistant. The registry is a module-level tuple; adding an entry is the whole cost of
supporting a new assistant (FR-020).

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | The value the user configures: `claude`, `copilot`. |
| `display_name` | `str` | For messages, e.g. `Claude Code CLI`. |
| `binary` | `str` | Looked up with `shutil.which`; resolves `.cmd`/`.exe` on Windows via `PATHEXT`. |
| `build_args` | `Callable[[str], list[str]]` | Prompt → argument list, excluding the binary. |

**Registry**:

| `name` | `display_name` | `binary` | `build_args(prompt)` |
|---|---|---|---|
| `claude` | Claude Code CLI | `claude` | `["-p", prompt, "--allowedTools", "Read"]` |
| `copilot` | GitHub Copilot CLI | `copilot` | `["-p", prompt, "--allow-tool", "read", "-s"]` |

Both add a read-only permission flag, in each CLI's own shape — see [research.md](./research.md)
R2 and R13. Neither grants `Bash`/`Edit`/write: FR-018 ("do not edit any file") is enforced at the
permission level, not left to the prompt's instructions alone. `build_args` exists so a future
assistant with a different shape needs no change anywhere else.

`none` is **not** a profile. It is a legal value of the setting meaning "do not resolve one"
(FR-024), handled in resolution rather than by a null-object entry in the registry.

---

## AssistantSetting

The user's recorded choice. **The only persisted entity in this feature.**

| Aspect | Value |
|---|---|
| Location | `<workspace>/.endpaper/config.toml`, table `[assistant]`, key `name` |
| Legal values | `"claude"`, `"copilot"`, `"none"` |
| Absent | Means "detect" — not an error (FR-030) |
| Schema impact | None. `workspace.schema` stays `1`; see [research.md](./research.md) R9 |

```toml
[workspace]
schema = 1
created = "2026-07-30T18:01:00"

[assistant]
name = "claude"
```

**Resolution** (FR-022 → FR-024) produces a `ResolvedAssistant`:

| Field | Type | Notes |
|---|---|---|
| `profile` | `AssistantProfile \| None` | `None` when nothing is usable. |
| `source` | `str` | `configured` \| `detected` \| `none` \| `unset` \| `ambiguous` \| `missing` |
| `available` | `tuple[str, ...]` | Profile names found on this machine. |

The decision table — total over the inputs, which is what makes it a unit test rather than an
integration one:

| Setting | Detected | `profile` | `source` | `/ai` behaviour |
|---|---|---|---|---|
| `claude` | — | claude | `configured` | Runs. If the binary is absent, invocation fails naming it (`missing`). |
| `copilot` | — | copilot | `configured` | As above. |
| `none` | — | `None` | `none` | Reports no assistant configured; **no detection** (FR-024). |
| absent | exactly one | that one | `detected` | Runs (SC-007). |
| absent | two or more | `None` | `ambiguous` | Reports the choice and names `/config assistant` (FR-023). |
| absent | none | `None` | `unset` | Reports none installed and names `/config assistant` (FR-016). |

An unrecognised value in the file is treated as `unset` and logged, never raised — a hand-edited
config must not stop endpaper from opening (Principle IV).

---

## AssistantRequest

One in-flight invocation. A **handle**, not a value: it owns the child process and is the only thing
that can cancel it.

| Field / method | Type | Notes |
|---|---|---|
| `profile` | `AssistantProfile` | Which assistant is running. |
| `cancel()` | `None` | Terminates the child **process group**. Idempotent; safe after completion. |
| `wait()` | `AssistantReply` | Blocks until the child exits. Never raises — failures come back as a reply with `ok=False`. |

Created by `start_request(...)`, which spawns the process and returns immediately. `wait()` runs on
a Textual thread worker; `cancel()` is called from the main thread and is what unblocks `wait()` —
see [research.md](./research.md) R4 for why terminating the process *is* the cancellation mechanism.

**Lifecycle**, and where each transition is required:

```text
start_request()  →  running  ──── child exits 0 ────────→  reply(ok=True)     FR-014
                       │
                       ├──────── child exits non-zero ──→  reply(ok=False)    FR-016
                       ├──────── stdout empty ──────────→  reply(ok=False, empty)  FR-015
                       └──────── cancel() ──────────────→  reply(ok=False, cancelled)  FR-013
```

There is no timeout state: cancel is the answer to a slow assistant (spec Assumptions).

---

## AssistantReply

What a finished request produced. A plain value object — the editor decides what to do with it.

| Field | Type | Notes |
|---|---|---|
| `ok` | `bool` | `True` only when the child exited 0 **and** stdout held non-whitespace text. |
| `text` | `str` | The reply, `\n`-normalised with the trailing newline stripped. Empty unless `ok`. |
| `message` | `str` | User-facing failure text. Empty when `ok`. Names what went wrong (FR-016). |
| `cancelled` | `bool` | `True` when the request was cancelled; suppresses the error message (FR-013). |

`text` is normalised on the way out so insertion cannot corrupt the buffer's line-ending convention
(FR-014) — the buffer is `\n`-internal and `save_buffer` re-applies the file's own convention on
write, exactly as it does today.

---

## Relationships

```text
EditorCommand ──parsed into──▶ ParsedCommand
                                    │ argument
                                    ▼
AssistantSetting ──resolves to──▶ ResolvedAssistant ──.profile──▶ AssistantProfile
        │ (config.toml)                                                │
        │                                                    start_request(profile, prompt, path)
        │                                                                ▼
        └────────── read/written by `/config assistant`          AssistantRequest
                    and `endpaper config assistant`                      │ wait()
                                                                          ▼
                                                                   AssistantReply
```

## Validation rules

| Rule | Source | Enforced in |
|---|---|---|
| A command matches only when the line's entire content is `/word` optionally followed by a space and text | FR-001 | `parse_line` |
| An unregistered `/word` is document text, not an error | FR-002 | `parse_line` |
| `/ai` with no argument reports that a prompt is required | FR-007 | `requires_argument` |
| Setting must be `claude`, `copilot`, or `none` | FR-028 | `config.set_assistant`, before writing |
| An invalid value writes nothing | FR-028 | `config.set_assistant` raises `UsageError` before touching the file |
| An unreadable or unrecognised stored value degrades to "detect" | FR-030, Principle IV | `config.get_assistant` |
| Reply text never carries `\r\n` into the buffer | FR-014 | `AssistantReply` construction |
| A cancelled request's reply is discarded even if it arrives | FR-013 | Editor checks the request is still current |
