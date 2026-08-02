# Contract: The Task Store on Disk

**Feature**: `019-completed-tasks-partition`

What a day file is, what a moved line looks like, and what is guaranteed byte-for-byte.

---

## F1 — Layout

```text
tasks.md                                  # the open list
tasks/done/YYYY/MM/YYYY-MM-DD-done.md     # records completed on that day
```

- The date in the path and the filename is the record's **completion** day.
- `YYYY/MM/` is the only partitioning, and date is the only axis inside the collection
  (Principle III).
- Created on demand by `write_text_atomic`; never pruned. An empty day file is legal.
- 40 characters below the workspace root — fixed depth, independent of record count.

## F2 — A day file

Identical in format to `tasks.md`. **No frontmatter.** A container, not a record.

```markdown
- [x] call Terry about the renewal <!-- id:task_a1b2 type:followup created:2026-07-28 completed:2026-08-02 -->
    the contract auto-renews on the 15th

- [x] send the vendor comparison <!-- id:task_c3d4 tags:procurement created:2026-07-30 completed:2026-08-02 -->
```

Read by `tasks.parse_tasks`, unmodified. Anything in the file that is not a task line is ignored on
read and preserved on write, exactly as in `tasks.md`.

## F3 — The `completed` field

- ISO `YYYY-MM-DD`. Last in field order: `id`, `type`, `tags`, `links`, `created`, `completed`.
- Omitted when absent — a completed record with no `completed:` (everything completed before this
  feature) is legal and reads as complete with no date.
- An unparseable value warns (`task_invalid_value`) and **the record is still returned**, matching
  `created`.
- **Authoritative over the path.** A record whose field says 3 May, sitting in the file for 12 June,
  lists as 3 May and is not relocated (FR-005).

## F4 — Byte guarantees on a move

Given a source line `L` and its body span `B₁…Bₙ`:

| Element | Guarantee |
|---|---|
| Indent, list marker, spacing before the description | Byte-identical |
| Description text | Byte-identical — never re-parsed and re-emitted |
| `id`, `type`, `tags`, `links`, `created` and their spacing | Byte-identical |
| State character | The one character between `[` and `]` |
| `completed:` | Inserted after the last field, or removed with its one leading space |
| `B₁…Bₙ` | Byte-identical, including relative indentation and blank lines inside the span |
| Every line outside the record, in both files | Byte-identical, in the same order |
| Line endings | The **destination file's** convention on the written block; the source file's own convention preserved on what remains |
| Trailing newline | Each file's own state preserved, per `delete_task`'s existing rule |

**The `completed:` splice, exactly.** With `B` the inner body of the last `<!-- … -->` on the line:

- insert → `B.rstrip() + " completed:<ISO>" + <B's original trailing whitespace, or " ">`
- remove → drop the first `completed:…` token and the single space preceding it

Leading spacing inside the comment, and any spacing the user typed between other fields, is
untouched.

## F5 — Lines that never move

| Line | Why |
|---|---|
| Malformed or unterminated metadata comment | Yields no `Task`, so it can never be matched by id |
| Checkbox with no comment, or a bare one | Yields `id=None`; an id is backfilled first, then it moves like any other |
| Headings, prose, blank lines, plain checklist items | Never read as records; carried through untouched |

## F6 — States choom reads but never creates

| State | Read as | Moved? |
|---|---|---|
| `- [x]` in `tasks.md` | Complete, no completion date | No — FR-037. Only a real reopen→complete cycle, or `task tidy`, moves it |
| `- [ ]` in a day file | Open | No — FR-005. choom does not relocate a record to agree with its own filing |
| Same id in both files | Ambiguous | No. Every operation refuses and names both `<file>:<line>` |

## F7 — Ordering

- Within a file: file order, preserved.
- Across the store: `tasks.md` first, then day files newest-first.
- `filter_tasks` then applies its existing sort unchanged, so no caller sees a new ordering rule.
- A completed record moves to the **end** of its day file (append), and a reopened record to the
  **end** of `tasks.md` — the same append `add_task` performs.
