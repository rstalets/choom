# Contract: the assistant setting

**Feature**: `006-ai-assistant-invocation`

One key, in a file endpaper already owns, reachable identically from both interfaces (Principle II).

---

## File schema

```toml
[workspace]
schema = 1
created = "2026-07-30T18:01:00"

[assistant]
name = "claude"
```

| Aspect | Value |
|---|---|
| Path | `<workspace>/.endpaper/config.toml` |
| Table | `[assistant]` |
| Key | `name` |
| Legal values | `"claude"`, `"copilot"`, `"none"` |
| Absent | Means "detect" — not an error (FR-030) |
| `workspace.schema` | Stays `1` — **not** bumped |

**Why no schema bump.** `_check_schema` reads only `workspace.schema`. A config written by this
version opens unchanged in an older build (which ignores the table it does not know), and a config
written by an older build is simply missing the table — which resolution already treats as "detect".
Adding a key is a minor change under Principle VI; the changelog records it.

---

## Reading

```python
def get_assistant(workspace: Workspace) -> str | None:
    """Return the configured assistant name, or None when unset.

    Never raises. A missing file, missing table, unreadable file, or a value that is not a
    legal setting all return None and are logged -- a hand-edited config must not stop
    endpaper from opening (Principle IV).
    """
```

`None` is returned for *every* degenerate case, so the caller has one branch, and it is the same
branch as "the user never set this": detect (FR-030).

---

## Writing

```python
def set_assistant(workspace: Workspace, value: str) -> None:
    """Record the assistant, creating the [assistant] table if absent.

    Raises:
        UsageError: `value` is not one of claude, copilot, none. Nothing is written.
        WorkspaceError: the config file cannot be written.
    """
```

**Validation precedes the write** (FR-028). An invalid value leaves the file byte-identical.

**A line-targeted edit, not a rewrite.** `tomllib` is read-only and the standard library ships no
TOML writer; adding one would be a third-party dependency for a single key, and rewriting the file
from a parsed dict would silently drop comments and any key a future version added.

So `set_assistant` does what `core.editing.stamp_updated` already does for frontmatter — changes one
line and no other byte ([research.md](./research.md) R9):

| Existing file | Action |
|---|---|
| Has `[assistant]` with a `name = "..."` line | Replace that line's value |
| Has `[assistant]` without `name` | Insert `name = "..."` as the table's first key |
| No `[assistant]` table | Append `\n[assistant]\nname = "..."\n` |

Comments, key order, and unknown keys elsewhere in the file survive every case. The write itself
reuses the atomic temp-file-plus-`os.replace` pattern already used for document saves, so an
interrupted write cannot truncate the config.

---

## Terminal interface

```text
/config assistant <claude|copilot|none>
```

`config` is a **command-bar** verb — the existing `/` bar on the list screen — not an in-editor
command. It acts on the workspace, not on a document ([research.md](./research.md) R11). It joins
`VERB_TABLE` in `tui/commands.py`, which means it also appears in `/help` automatically, and it
requires the deliberate edit to `tests/unit/test_command_parsing.py::test_existing_verbs_unchanged`
that the spec's Dependencies section already flags.

| Verb | Argument | Description (shown in `/help`) |
|---|---|---|
| `config` | `assistant <claude\|copilot\|none>` | Set which AI assistant `/ai` calls |

| Input | Result |
|---|---|
| `/config assistant claude` | Written; effective for the next `/ai` with no restart (US3 scenario 1) |
| `/config assistant` | Status bar: current value and the accepted ones |
| `/config assistant gpt` | Status bar names the accepted values; nothing written (FR-028) |
| `/config` | Status bar: `config needs a setting name` |
| `/config wallpaper blue` | Status bar: `unknown setting: 'wallpaper'` |

Errors use the existing status bar (spec Assumptions). No new surface, no dialog.

---

## Command-line interface

```text
endpaper config assistant [<value>] [--json]
```

The Principle II peer. Non-interactive, no prompt, no editor, data on stdout and errors on stderr.

| Invocation | Behaviour | Exit |
|---|---|---|
| `endpaper config assistant claude` | Writes; prints nothing | 0 |
| `endpaper config assistant` | Prints the resolved state as a table | 0 |
| `endpaper config assistant --json` | Prints the JSON below | 0 |
| `endpaper config assistant gpt` | Error on stderr listing accepted values; writes nothing | 2 |
| Run outside a workspace | Workspace error on stderr | 3 |

Exit codes follow the existing hierarchy: 0 success, 2 usage error, 3 workspace error.

### `--json` schema

Stable and documented (Principle II). Adding a key is minor; renaming or removing one is breaking.

```json
{
  "configured": "claude",
  "resolved": "claude",
  "source": "configured",
  "available": ["claude"]
}
```

| Key | Type | Meaning |
|---|---|---|
| `configured` | `string \| null` | The stored value. `null` when unset. |
| `resolved` | `string \| null` | What `/ai` would actually use. `null` when nothing is usable. |
| `source` | `string` | `configured` \| `detected` \| `none` \| `unset` \| `ambiguous` |
| `available` | `string[]` | Assistants found on this machine, sorted. Possibly empty. |

Never `null` where a list is expected — `available` is `[]`, not `null`, matching the existing
schema convention that `tags` is `[]`.

The four keys exist so an AI assistant reading this workspace can answer "is `/ai` usable here, and
if not, why not" in one call — `source` distinguishes *unset* from *ambiguous* from *deliberately
none*, which is exactly the difference that determines what to tell the user.

---

## Initialisation

```text
endpaper init [--assistant <claude|copilot|none>]
```

The flag records the choice as part of workspace creation (FR-027). Omitted, no `[assistant]` table
is written and resolution detects.

**`init` does not prompt** — the one deviation from Issue #19's text, carried forward from the spec
for confirmation. Constitution II forbids the command line from blocking on input, without
exception, because the CLI is an AI assistant's only interface and a prompt turns an automation into
a hang. An invalid value exits 2 and creates nothing.

---

## Resolution

Reading the setting and deciding what `/ai` will use are separate steps; the decision table lives in
[data-model.md](../data-model.md#assistantsetting). Two rules worth restating because they are the
ones that surprise:

- **`none` disables detection** (FR-024). It means "I do not want this", not "figure it out".
- **Two assistants installed and nothing configured is not an error state to resolve silently.**
  The user is told to choose and named the command that does it (FR-023). Picking by precedence
  would mean sometimes calling the assistant they did not mean.
