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
| `claude` | Claude Code CLI | `claude` | `["-p", <prompt>, "--allowedTools", "Read"]` |
| `copilot` | GitHub Copilot CLI | `copilot` | `["-p", <prompt>, "--allow-tool", "read", "-s"]` |

Both assistants document `-p` as their non-interactive mode, printing the reply to stdout and
exiting non-zero on failure ([research.md](./research.md) R2). That they agree on the shape is
what makes the registry three columns instead of a capability matrix.

Each also gets a read-only tool-permission flag, in its own syntax ([research.md](./research.md)
R13). Neither CLI auto-approves tool calls — including a plain file read — in non-interactive `-p`
mode by default; without this flag the assistant's attempt to read the document that
`compose_prompt` points it at (FR-009) is silently denied, since there is no TTY to approve it.
Granting only `Read` also enforces FR-018 ("do not edit any file") at the permission level, not
just as an instruction the model could ignore.

`build_args` is a per-profile callable. It exists so an assistant with a different shape — a
different flag name, no permission model at all, or an entirely different argument order — can be
added without touching invocation, error handling, or the editor.

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

The user's document has just been saved to:
  <absolute path>

The request is on line <N> of that file. Content above that line comes before it
in the document; content below comes after.

<the user's prompt text>
```

The instructions are **prepended to the prompt** rather than passed via a flag. Claude Code has
`--append-system-prompt` and Copilot has no non-interactive equivalent; using it would fork the two
profiles and re-introduce exactly the asymmetry FR-020 forbids ([research.md](./research.md) R3).

### The line number (FR-009)

A path answers "which document"; it does not answer "which paragraph". Prompts like *generate tasks
for the above paragraph*, *tighten this section*, or *summarise everything below* are positional,
and without a position they are unanswerable — the assistant would have to guess which part of the
note the user meant, in a file that may be hundreds of lines long.

So the composed prompt carries the **1-based line number of the `/ai` line in the file as saved**.

Three details that are easy to get wrong, fixed here:

- **1-based**, matching the editor's line-number gutter and what file-reading tools report.
- **Counted over the whole file including frontmatter**, because that is what the assistant sees
  when it opens the file. Buffer and file agree: `TextArea`'s cursor row is 0-based over the whole
  document, so the number is `cursor_row + 1` with no other adjustment.
- **The `/ai` line really is at that number.** FR-008 saves the document in its current state, which
  includes the command line, so the position resolves to a line that exists on disk rather than one
  that only existed in the buffer.

### Instructions (FR-010)

The literal text. Specified here rather than left to implementation because it is the feature's
voice, and because every clause is load-bearing.

```text
You are answering a request from inside a plain-text notes editor. Your reply is
inserted directly into the user's document, replacing the line they typed. They
do not see it anywhere first.

- Answer directly. No preamble, no restating the question, no sign-off.
- Write markdown that belongs in working notes: prose, a list, a table, or a
  fenced diagram, whichever suits the answer. Do not wrap the whole reply in a
  code fence unless the entire answer is code.
- Match the length to the request. These are working notes, not a report.
- You cannot ask a question. Nothing here is interactive and there is no second
  turn. If the request is ambiguous, take the most reasonable reading, answer it,
  and note the assumption in one short line.
- The request may refer to the document by position — "the paragraph above",
  "this section", "everything below". Read the file and resolve those against the
  line number given below.
- Do not edit any file. The document is open in an editor whose unsaved buffer
  overwrites the file on the next save, so any edit you make is discarded.
```

Why each clause is there:

| Clause | Serves | Without it |
|---|---|---|
| Reply is inserted directly, replacing their line | FR-010 | The assistant writes for a chat window — preamble, restatement, a closing offer of further help |
| No preamble or sign-off | FR-010 | "Here's what I found:" and "Let me know if you'd like more detail" land in the note |
| Markdown suited to working notes | FR-010 | Report-shaped output with headings the note did not ask for |
| Don't fence the whole reply | FR-014 | Ordinary prose arrives wrapped in a code block — wrong in a markdown note and tedious to unpick |
| Match the length | FR-010 | A one-line question returns six paragraphs the user has to delete |
| **You cannot ask a question** | FR-010 | A clarifying question is inserted *as document text*. The invocation is one-shot and non-interactive, so there is no way to answer it — the user's only recovery is to delete it and retype. This is the failure the instructions most need to prevent. |
| Positional references resolve against the line number | FR-009 | "The paragraph above" is answered about the wrong paragraph, or not at all |
| Do not edit any file | FR-018 | The assistant edits the file, the buffer overwrites it on the next save, and the work vanishes with no error |

The final clause also earns its keep by explaining the `/ai <prompt>` line the assistant will find at
the given line number: that line is the request being answered, and the reply replaces it. Without
that, a careful assistant may treat the command text as content worth preserving, or try to edit the
file to remove it.

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
