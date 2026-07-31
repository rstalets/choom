# Contract: `endpaper.core` public API

**Feature**: `006-ai-assistant-invocation`

Every signature below is callable without a terminal, a TTY, or an event loop (Principle I). All
carry type hints and a docstring stating what they return and what they raise (Principle VI).

The event-loop clause is why `AssistantRequest` is synchronous `subprocess` rather than `asyncio`:
an async API would put a loop between `core` and its tests. Concurrency is the TUI's problem, solved
with a thread worker, and `core` stays plain.

---

## New — `endpaper.core.editor_commands`

### `EditorCommand` / `ParsedCommand`

```python
@dataclass(frozen=True, slots=True)
class EditorCommand:
    name: str
    argument: str
    description: str
    requires_argument: bool


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    command: EditorCommand
    argument: str


EDITOR_COMMANDS: tuple[EditorCommand, ...]
```

### `parse_line`

```python
def parse_line(line: str) -> ParsedCommand | None:
    """Parse one submitted editor line as an in-editor command.

    Returns None when the line is ordinary document text -- which is every case except a
    line whose entire content is `/<registered word>` optionally followed by a space and
    argument text. Leading whitespace, a preceding character, an unregistered word, and a
    partial match all return None.

    Never raises: a line this cannot parse is a line the user typed, not an error.
    """
```

Grammar and worked cases: [editor-commands.md](./editor-commands.md).

---

## New — `endpaper.core.assistants`

### `AssistantProfile` / `ResolvedAssistant` / `AssistantReply`

```python
@dataclass(frozen=True, slots=True)
class AssistantProfile:
    name: str
    display_name: str
    binary: str
    build_args: Callable[[str], list[str]]


@dataclass(frozen=True, slots=True)
class ResolvedAssistant:
    profile: AssistantProfile | None
    source: str                      # configured | detected | none | unset | ambiguous
    available: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssistantReply:
    ok: bool
    text: str
    message: str
    cancelled: bool


PROFILES: tuple[AssistantProfile, ...]
```

### `available_assistants`

```python
def available_assistants() -> tuple[str, ...]:
    """Return the names of supported assistants runnable on this machine, sorted.

    Uses shutil.which, so PATHEXT resolves `claude.cmd` / `claude.exe` on Windows.
    Launches nothing; cannot hang. Returns an empty tuple when none are installed.
    """
```

### `resolve_assistant`

```python
def resolve_assistant(configured: str | None) -> ResolvedAssistant:
    """Decide which assistant `/ai` should call.

    `configured` is the stored setting, or None when unset. A configured name is used as
    given. "none" resolves to nothing and does NOT fall back to detection. When unset,
    detection decides: exactly one available assistant is used; two or more is reported
    as ambiguous rather than resolved by precedence; none available is reported as unset.

    Never raises. An unrecognised `configured` value is treated as unset.
    """
```

Full decision table: [data-model.md](../data-model.md#assistantsetting).

### `compose_prompt`

```python
def compose_prompt(user_prompt: str, document: Path) -> str:
    """Build the text handed to the assistant.

    Prepends the instructions required by FR-010 -- that the reply is inserted directly
    into a working-notes editor, that it should answer directly in a form suited to that
    medium, and that it should reply rather than edit the file -- and names the saved
    document so the assistant can resolve references like "lines 15-18".
    """
```

Separate from `start_request` so the composed text is assertable in a unit test without
spawning anything.

### `start_request`

```python
def start_request(
    profile: AssistantProfile,
    prompt: str,
    *,
    cwd: Path,
) -> AssistantRequest:
    """Spawn the assistant and return a handle immediately.

    The child is launched in its own process group with stdin at DEVNULL and stdout and
    stderr captured, so an assistant that tried to prompt gets EOF and exits rather than
    hanging invisibly.

    Never raises: a binary that is missing or cannot be spawned yields a handle whose
    wait() returns a failed AssistantReply naming the problem.
    """
```

### `AssistantRequest`

```python
class AssistantRequest:
    """One in-flight assistant invocation.

    Owns the child process. wait() blocks until it exits; cancel() terminates it, which
    is what unblocks a waiting caller -- Textual thread workers cannot be interrupted
    mid-call, so killing the process is the cancellation mechanism, not an optimisation.
    """

    profile: AssistantProfile

    def wait(self) -> AssistantReply:
        """Block until the assistant exits and return what it produced.

        Never raises. Non-zero exit, empty output, a missing binary, and cancellation all
        come back as an AssistantReply with ok=False.
        """

    def cancel(self) -> None:
        """Terminate the child process group.

        Idempotent and safe after the process has already exited -- a request that
        finishes microseconds before the user presses ctrl+c must not raise.
        """
```

---

## New — `endpaper.core.config`

### `get_assistant`

```python
def get_assistant(workspace: Workspace) -> str | None:
    """Return the configured assistant name, or None when unset.

    Never raises. A missing file, a missing [assistant] table, an unreadable or malformed
    file, and a value that is not a legal setting all return None and are logged, so a
    hand-edited config cannot stop endpaper from opening.
    """
```

### `set_assistant`

```python
def set_assistant(workspace: Workspace, value: str) -> None:
    """Record the assistant, creating the [assistant] table if it is absent.

    Edits the single `name` line and no other byte, preserving comments, key order, and
    any unknown keys; writes atomically via a same-directory temp file and os.replace.

    Raises:
        UsageError: `value` is not claude, copilot, or none. Nothing is written.
        WorkspaceError: the config file cannot be written.
    """
```

Behaviour per existing-file shape: [config.md](./config.md).

---

## Modified — `endpaper.core.workspace`

### `init_workspace`

```python
def init_workspace(target: Path, *, assistant: str | None = None) -> InitResult:
    """Create a workspace. When `assistant` is given, record it in the config (FR-027).

    Unchanged in every other respect. Never prompts.

    Raises:
        WorkspaceError: the directory is already a workspace.
        UsageError: `assistant` is not claude, copilot, or none. Nothing is created.
    """
```

Keyword-only with a default, so every existing caller and test is unaffected.

---

## Modified — `endpaper.core.errors`

```python
class AssistantError(EndpaperError):
    """An assistant could not be resolved or run. exit_code = 1."""
```

Used by the command line when `endpaper config assistant` is asked about an assistant that cannot be
resolved. The TUI does not raise it — in the editor, every failure is a status-bar message and a
return of control (FR-016), never an exception that could interrupt a session.

---

## What deliberately is not here

- **No async variants.** Concurrency belongs to the TUI's worker, not to `core` (Principle I).
- **No `run_assistant(...)` convenience that blocks and returns a reply.** It would be the obvious
  thing to call and would make cancellation impossible, which is the one guarantee US2 exists to
  protect. The handle is the API.
- **No session or conversation state.** Each `/ai` is one invocation (spec Assumptions).
- **No import of `assistants` anywhere else in `core`.** FR-031 requires every other feature to work
  on a machine with no assistant installed; the module boundary is what makes that structural rather
  than a promise.
