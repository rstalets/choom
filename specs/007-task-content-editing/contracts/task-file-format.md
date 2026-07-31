# Contract: the task line format, extended with bodies

`tasks.md` is a public interface — users hand-edit it, AI assistants read and write it, and other
markdown tools render it. This contract is the normative statement of what a body looks like on
disk. Changes to it are changelog entries (Principle VI).

## Shape

```markdown
- [ ] call the vendor <!-- id:t_a1b2 type:followup tags:procurement created:2026-07-30 -->

  Need the Q3 comparison before the renewal meeting.

  - 07-28 called, left voicemail
  - 07-30 emailed Dana

- [x] send the invoice <!-- id:t_c3d4 created:2026-07-29 -->
```

The checkbox line is unchanged from v0.0.1 — same marker, same metadata comment, same field order.
A body is indented continuation content belonging to that list item.

## Reading

A task's body span starts on the line after its checkbox line and ends after the last indented,
non-blank line before a terminator.

**Terminators** — the span ends *before* the first line that is either:

1. a checkbox line at any indentation (`- [ ] …`, `  - [x] …`), or
2. non-blank with no leading whitespace.

**Blank lines** are included in the span when more indented content follows, and excluded when they
trail. The blank line separating two tasks therefore belongs to neither.

**Dedent** — the body text is the span's lines with the longest common leading-whitespace prefix
removed, leading and trailing blank lines dropped. Relative indentation inside the body is preserved,
so nested bullets and fenced blocks keep their shape.

**Tolerance** — reading never raises and never rewrites. Irregular indent depth, tabs, whitespace-only
lines, fenced code blocks, and non-ASCII text are read verbatim. A body under a checkbox line whose
metadata comment is malformed stays where it is: that line is skipped with a warning, as it is today,
and its indented lines are never re-attached to the preceding task.

## Writing

- The span is replaced; every line outside it is byte-identical.
- One blank line is written between the checkbox line and the first body line, so the body renders
  as its own block rather than as a lazy continuation of the task's paragraph.
- Body lines are indented by the prefix observed when the span was read, or two spaces when there was
  none. Blank lines inside a body are written empty, with no trailing whitespace.
- An empty body removes the span entirely, leaving a lone checkbox line with no residual blank or
  indented lines.
- A body identical to the one on disk is not written at all.
- The file's line-ending convention and trailing-newline state are preserved.
- The write is atomic: a same-directory temp file replaced into position, so an interruption leaves
  the previous file intact.

## Guarantees

1. `tasks.md` with bodies is valid CommonMark and renders as a checklist whose items carry nested
   content.
2. No read or write loses, reorders, or truncates a line.
3. A file written before this feature parses identically, with every task listed as it was and no
   rewrite on first read.
4. A checkbox line inside a body is a task, not body text — the rule for what is a task is unchanged.
5. A `<!-- id:… -->` comment inside a body is text; it neither creates nor renames a task.
