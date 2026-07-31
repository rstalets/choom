# Contract: assistant profiles and invocation

**Feature**: `006-ai-assistant-invocation`

How endpaper reaches an assistant, what it sends, and every way that can fail. The governing
constraint is FR-020: **adding an assistant must not change `/ai`'s behaviour, its error messages,
or the command framework.** Everything below is shaped to keep the per-assistant surface down to
three fields.

---

## The profile registry

The two assistants FR-019 requires, and nothing else:

| `name` | `display_name` | `binary` | Arguments |
|---|---|---|---|
| `claude` | Claude Code CLI | `claude` | `["-p", <prompt>]` |
| `copilot` | GitHub Copilot CLI | `copilot` | `["-p", <prompt>]` |

Both assistants document `-p` as their non-interactive mode, printing the reply to stdout and
exiting non-zero on failure ([research.md](./research.md) R2). That they agree on the shape is
what makes the registry three columns instead of a capability matrix.

`build_args` is a per-profile callable defaulting to `["-p", prompt]`. It exists so an assistant
with a different shape can be added without touching invocation, error handling, or the editor.

`none` is not in this table — it is a legal *setting* value meaning "resolve nothing", handled in
[config.md](./config.md).

---

## Detection

```python
shutil.which(profile.binary) is not None
```

Standard library, and correct on Windows: it consults `PATHEXT`, so `claude.cmd` and `claude.exe`
resolve without endpaper knowing anything about extensions. Nothing is launched, so detection cannot
hang and costs nothing.

Detection runs **only when the setting is absent**. A configured `none` never triggers it (FR-024).

---

## The composed prompt

One string, built the same way for every assistant, passed as the argument to `-p`.

```text
<instructions>

The document is at: <absolute path to the saved file>

<the user's prompt text>
```

### Instructions (FR-010)

Three things the assistant must know, and one it must not do:

1. Its reply is being inserted **directly into a working-notes editor**, at the position the command
   occupied.
2. It should answer the user's request directly, in a form suited to that medium — markdown prose,
   a list, a table, a fenced diagram. No preamble, no "Here's what I found", no sign-off.
3. The document has just been saved and it may read it to resolve references like "the process
   described on lines 15-18" (FR-009).
4. It should **reply, not edit**. The file on disk is open in an editor whose buffer will win on the
   next save, so a file edit would be silently discarded (FR-018).

Point 4 also earns its keep by explaining the `/ai <prompt>` line the assistant will find in the
file: that line is the command being answered, and the reply replaces it. Without that, a careful
assistant might treat the command text as content worth preserving.

The instructions are **prepended to the prompt** rather than passed via a flag. Claude Code has
`--append-system-prompt` and Copilot has no non-interactive equivalent; using it would fork the two
profiles and re-introduce exactly the asymmetry FR-020 forbids ([research.md](./research.md) R3).

---

## Running the request

```python
request = start_request(profile, prompt=composed, cwd=workspace_root)
reply = request.wait()      # on a thread worker
request.cancel()            # from the main thread — this is what unblocks wait()
```

| Aspect | Choice | Why |
|---|---|---|
| Launch | `subprocess.Popen([binary, *build_args(prompt)])` | No shell. Arguments are passed as a list, so a prompt containing quotes, `;`, or `$()` is data, never syntax. |
| `cwd` | Workspace root | The assistant resolves relative paths and its own project config against the workspace, as it would if the user ran it there. |
| stdout / stderr | Captured separately, `text=True`, UTF-8, `errors="replace"` | Reply from stdout; stderr feeds the failure message. Never lose the reply to a decoding error (Principle IV). |
| stdin | `DEVNULL` | An assistant that tried to prompt gets EOF and exits rather than hanging invisibly (FR-021). |
| Timeout | None | Cancel is the answer to a slow assistant (spec Assumptions). |
| Process group | `start_new_session=True` (POSIX) / `CREATE_NEW_PROCESS_GROUP` (Windows) | Assistants spawn children; the group is what makes cancel complete. |

### Cancellation

`cancel()` terminates the **process group**, then `wait()` returns because the child is gone.

This is the mechanism, not an optimisation. Textual's documentation is explicit that thread workers
cannot be interrupted mid-call — a worker parked in `communicate()` on a process that never returns
would stay parked forever, and `worker.cancel()` would only set a flag
([research.md](./research.md) R4).

| Platform | Terminate |
|---|---|
| POSIX | `os.killpg(os.getpgid(pid), SIGTERM)` |
| Windows | `proc.terminate()` |

`cancel()` is idempotent and safe to call after the process has already exited — a request that
finishes microseconds before the user presses `ctrl+c` must not raise.

---

## Failure taxonomy

Every path returns an `AssistantReply`. **`wait()` never raises** — a subprocess failure is a
user-facing message, not a traceback (Principle IV).

| Condition | `ok` | `cancelled` | Message | Requirement |
|---|---|---|---|---|
| Exit 0, stdout has text | `True` | `False` | — | FR-014 |
| Exit 0, stdout empty or whitespace | `False` | `False` | `<display_name> returned an empty reply` | FR-015 |
| Exit non-zero | `False` | `False` | `<display_name> failed: <last stderr line>` | FR-016 |
| Binary not found (`FileNotFoundError`) | `False` | `False` | `<display_name> is not installed or not on your PATH` | FR-016, edge case |
| `OSError` on spawn | `False` | `False` | `could not start <display_name>: <reason>` | FR-016 |
| Cancelled | `False` | `True` | — (suppressed) | FR-013 |

Messages name the assistant by `display_name`, so "configured as claude but claude is not installed"
is distinguishable from a generic failure — the spec's edge case for a configured-but-missing
assistant.

Failure messages are truncated to one line for the status bar. Loss of network shows up as the
assistant's own non-zero exit and its stderr, which is more accurate than endpaper guessing.

---

## Boundaries

- **Nothing else in endpaper touches this module** (FR-031). No import of `assistants` from
  documents, tasks, meetings, or workspace scanning. A machine with neither binary installed runs
  every other feature unchanged, offline.
- **No credentials.** endpaper reads no API key, writes none, and stores none. Authentication is
  entirely the assistant CLI's own, already configured by the user.
- **No conversation state.** Each `/ai` is one invocation with no session carried between them
  (spec Assumptions). No session id is stored or replayed.
- **No network call from endpaper.** The assistant makes its own connections; endpaper spawns a
  local process and reads a pipe.

---

## Testing without an assistant installed

Every row of the failure table is reachable with a **stub binary** — a Python script written into
`tmp_path` and named as the profile's binary, with modes selected by argument:

| Mode | Behaviour | Covers |
|---|---|---|
| echo | prints its own argv, exit 0 | success path; proves the instructions and document path reached the command line (FR-009, FR-010) |
| reply | prints fixed multi-line text, exit 0 | insertion, ordering, line endings (FR-014) |
| empty | prints nothing, exit 0 | FR-015 |
| fail | writes to stderr, exit 1 | FR-016 |
| sleep | sleeps indefinitely | cancel (FR-013, SC-002) |

The stub keeps CI honest on machines that have neither Claude Code nor Copilot, needs no network and
no API key, and makes the cancel path deterministic rather than timing-dependent.
