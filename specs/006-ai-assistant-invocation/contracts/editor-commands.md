# Contract: in-editor commands

**Feature**: `006-ai-assistant-invocation`

This is the **second** command surface in endpaper. The existing `/` verbs are typed into a command
bar on the list screen and act on the workspace; these are typed into the document itself and act on
the document. They share the `/` sigil and nothing else — separate tables, separate parsers,
separate dispatch.

The rule that makes this safe to put inside a prose editor: **a line is a command only when it is
entirely a command.** Everything else is what the user typed.

---

## The command table

| Command | Argument | Description (shown in help) | Argument required |
|---|---|---|---|
| `ai` | `<prompt>` | Ask the configured assistant; the reply replaces this line | yes |

One table, two consumers: the parser and the help pane (FR-004). Adding a command is a row plus a
handler — parsing, dispatch, and display do not change (FR-003).

---

## Grammar

A submitted line is a command when **all** of these hold:

1. The line's entire content, after stripping trailing whitespace, starts with `/`.
2. There is **no leading whitespace**. `  /ai hello` is text.
3. The word between `/` and the first space (or end of line) matches a table entry exactly, compared
   lowercase.
4. What follows the command word is either nothing, or a single space then argument text.

Anything else is ordinary document text. The parser returns `None` and **never raises** (FR-002,
Principle IV).

### Worked cases

| Line submitted | Result | Why |
|---|---|---|
| `/ai summarise the bullets above` | command, argument `summarise the bullets above` | matches |
| `/ai   spaced   out  ` | command, argument `spaced   out` | argument is stripped at both ends; interior spacing kept |
| `/AI summarise` | command | command word compared lowercase |
| `/ai` | command, empty argument → "needs a prompt" (FR-007) | `requires_argument` |
| `/ai ` | as above | argument strips to empty |
| `Did you know you can type /ai in endnotes?` | text | not at line start (FR-001, SC-004) |
| `- /ai do the thing` | text | list marker precedes it |
| `  /ai indented` | text | leading whitespace |
| `/aim high` | text | `aim` is not a table entry |
| `//ai x` | text | word is `/ai`, not a table entry |
| `/summarise this` | text | unregistered word — **no error, no warning** (FR-002) |
| `/ai` inside a fenced code block | command | fences are not modelled (spec Assumptions) |

The fenced-code case is a deliberate accepted cost. Tracking fence state to decide whether Enter
runs a command is more machinery than the case is worth, and the workaround — indent the line, or
put any character before it — is immediate.

---

## The Enter contract

Enter is intercepted by a `TextArea` subclass overriding `_on_key`, the documented Textual extension
point ([research.md](./research.md) R5).

```text
Enter pressed
   │
   ├─ line parses as a command ──▶ event.prevent_default()   # no newline inserted
   │                               post EditorCommandSubmitted(command, argument, line_index)
   │
   └─ anything else ────────────▶ fall through to TextArea's own handling  # newline inserted
```

Two guarantees:

- **The 99% case is untouched.** On any ordinary line, Enter does exactly what it does today. The
  hook adds a check, not a reimplementation of newline insertion.
- **Cursor column is irrelevant.** The whole line is matched, wherever the cursor sits within it.
  Simpler to explain and to test than a rule keyed on cursor position.

Parsing lives in `core.editor_commands.parse_line`. The widget asks "is this a command?" and never
owns the grammar — the grammar is unit-testable with no terminal (Principle I).

---

## Inserted text is never a command

Text placed into the document by a command is inserted as text and is not re-parsed (FR-005,
FR-010). A reply containing a line beginning with `/ai` lands as those literal characters.

This is structural, not defensive: parsing happens only in the Enter hook, in response to a
keystroke. Programmatic insertion never passes through it, so there is no path by which a reply
could execute.

---

## `/ai` state machine

The states the editor moves through, and the requirement each transition serves.

```text
                    ┌──────────────────────────────────────────────┐
                    │                   editing                    │◀────────────┐
                    └───────────────────┬──────────────────────────┘             │
                          Enter on `/ai <prompt>`                                │
                                        ▼                                        │
                              save document (FR-008)                             │
                                   │        │                                    │
                       save failed │        │ saved                              │
                    report error ──┘        ▼                                    │
                    (FR-016)          resolve assistant                          │
                                           │        │                            │
                    none / ambiguous /     │        │ resolved                    │
                    unset ──▶ report ──────┘        ▼                            │
                    (FR-016, FR-023, FR-024)   in flight                         │
                                    ┌───────────────┴───────────────┐            │
                                    │ line shows `⋯`                │            │
                                    │ status: `⋯ working — ctrl+c   │            │
                                    │          to cancel`  (FR-011) │            │
                                    │ TextArea.read_only  (FR-012)  │            │
                                    └───────────────┬───────────────┘            │
                    ┌───────────────┬───────────────┼───────────────┐            │
              ctrl+c │        exit≠0 │         empty │           ok  │            │
                    ▼               ▼               ▼               ▼            │
            restore line     restore line    restore line    insert reply         │
            silently         + message       + message       at the line          │
            (FR-013)         (FR-016)        (FR-015)        (FR-014)             │
                    └───────────────┴───────────────┴───────────────┴────────────┘
                                         unlock, return control
```

**Invariant across every terminal branch**: the document contains either the user's original
`/ai <prompt>` line or the assistant's reply — never the `⋯` placeholder, never a partial insert,
never a lost line (FR-017, SC-003).

---

## The in-flight state

| Aspect | Behaviour | Requirement |
|---|---|---|
| Command line | Replaced by `⋯` in the buffer only; never saved | FR-011 |
| Status bar | `⋯ working — ctrl+c to cancel`, for the whole wait | FR-011, Principle V |
| Editing | `TextArea.read_only = True`; keystrokes do not alter the buffer | FR-012 |
| `ctrl+c` | Cancels; returns control immediately | FR-013, SC-002 |
| Other keys | No effect on the buffer | FR-012 |
| Time limit | None | spec Assumptions |
| Late reply after cancel | Discarded — the editor checks the request is still current | FR-013 |

Leaving the editor while a request is in flight is not possible: `escape`, `ctrl+o`, and `ctrl+x`
are inert until control returns. Cancel first, which is one keystroke and always available.

---

## Reply insertion

1. Normalise: `\r\n` → `\n`, strip the trailing newline. The buffer is `\n`-internal; `save_buffer`
   re-applies the file's own convention on write, unchanged from today (FR-014).
2. Replace the placeholder line with the reply's lines, in order.
3. Leave the buffer dirty and the cursor at the end of the inserted text. The user saves with the
   existing binding — the reply is treated exactly as if they had typed it (spec Assumptions).

Surrounding lines are never touched. A reply of `n` lines turns one line into `n`; every other line
keeps its content and relative order (FR-014, US1 scenario 2).

---

## Discoverability

`/ai` appears in the help pane with its argument shape and description, generated from the table
(FR-004, US1 scenario 7). The editor footer gains no entry: `/ai` is typed text, not a key binding,
and Principle V's footer rule governs bindings. `ctrl+c` — which *is* a binding — is stated on
screen for the entire in-flight state, which is the only state in which it is bound.
