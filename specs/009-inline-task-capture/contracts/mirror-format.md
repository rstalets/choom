# Contract: the mirror format and its state machine

**Feature**: `009-inline-task-capture`

A mirror is a checklist line in a document that is also a link to a task. It is content the user wanted in
their note and simultaneously a control surface onto that task's state. This document fixes what counts as
one, what is written into one, and who wins when a mirror and its task disagree.

---

## The line

```markdown
- [ ] [call Terry about the renewal](../../../tasks.md#task_a1b2)
```

Nothing about it is new syntax. It is a CommonMark task-list item containing a CommonMark inline link whose
fragment is a task id — the ordinary document-to-task edge that `008-document-links` defines, written by the
editor instead of by hand. There is no HTML comment, no metadata, and no marker identifying it as
machine-written.

The destination path is computed by `links.relative_destination()` from the two real file locations, so:

| Document | Destination written |
|---|---|
| `meetings/2026/07/2026-07-28-q3-planning.md` | `../../../tasks.md#task_a1b2` |
| `notes/daily/2026/07/2026-07-31.md` | `../../../../tasks.md#task_a1b2` |
| `notes/architecture-decisions.md` | `../tasks.md#task_a1b2` |

No prefix is hardcoded anywhere in this feature. Depth correctness and repair-on-move are 008's contract,
exercised here rather than reimplemented.

---

## Recognition

A line is a mirror when **both** conditions hold.

**1. The checklist prefix matches.**

```
^[ \t]*[-*+] \[[ xX]\] 
```

Optional leading whitespace, one bullet character, one space, `[`, exactly one state character, `]`, one
space. This is the same shape `tasks.py`'s `_TASK_LINE` matches, without that regex's anchoring to column
zero — because a mirror is expected to be indented under a bullet (FR-015, spec scenario 1.7).

**2. The line carries a link whose fragment is a task id.**

Determined by `links.find_links()`, which has already excluded fenced code blocks, inline code spans,
images, and destinations carrying a URL scheme. Where several links on one line carry task-id fragments,
the first is the mirror's task and the rest are ordinary links.

### Qualifies

| Line | Why |
|---|---|
| `- [ ] [call Terry](../../../tasks.md#task_a1b2)` | the canonical form |
| `  - [x] [call Terry](../../../tasks.md#task_a1b2)` | indented under a bullet |
| `* [ ] [call Terry](#task_a1b2)` | fragment-only destination — valid input under 008, gains its path on the next save |
| `- [ ] see [Terry](../../../tasks.md#task_a1b2) before Friday` | prose around the link is fine; the checkbox and the fragment are what matter |
| `- [X] [call Terry](../../../tasks.md#task_a1b2)` | uppercase state character reads as done |

### Does not qualify

| Line | Why | Consequence |
|---|---|---|
| `As agreed, [call Terry](../../../tasks.md#task_a1b2).` | no checkbox | an ordinary link; never written to |
| `- [ ] call Terry about the renewal` | no link | an ordinary checkbox in someone's note; never touched |
| `- [ ] [call Terry](../../../tasks.md)` | no fragment | resolves as a link, but names no task |
| `- [ ] [the July meeting](../../meetings/2026/07/x.md#meeting_2026…)` | fragment is not a task id | an ordinary link on a checklist line |
| ``- [ ] `[call Terry](../../../tasks.md#task_a1b2)` `` | inside a code span | excluded by `find_links` |
| `1. [ ] [call Terry](../../../tasks.md#task_a1b2)` | numbered list | not produced by this feature; task-list rendering of it is inconsistent across viewers |
| `-[ ] [call Terry](…#task_a1b2)` | no space after the bullet | not a list item in CommonMark |

The two negative cases that matter most are the first and second. A prose link to a task must never become
a control surface, and an ordinary checkbox a person typed in their own notes must never be adopted by this
feature — that would be "scanning arbitrary files for tasks", which the spec puts out of scope.

---

## Writing into a mirror

Every write is a **one-character splice** at the recorded offset of the state character:

```
text[:state_offset] + ("x" if done else " ") + text[state_offset + 1:]
```

Consequences that are guarantees, not incidents:

- The link text is never compared to the task's description and never rewritten. The user may reword it
  (spec scenario 4.3).
- Indentation, surrounding prose, and line endings are untouched.
- An uppercase `X` becomes a lowercase `x` only if the state actually changes; a mirror already in the
  right state is not written at all.
- No line is re-rendered, so no parser round-trip can lose a byte (Principle IV).

Offsets are recomputed by a fresh `find_mirrors()` on every pass. A stored offset is never reused across
calls, because the document may have changed underneath it.

---

## Who wins

### On open — the task wins

The user has not acted on this document yet, so `tasks.md` is authoritative.

| Mirror | Task | Action |
|---|---|---|
| open | open | none |
| done | done | none |
| open | done | splice `x` |
| done | open | splice ` ` |
| any | no such task | leave byte-identical, warn `link_dead` |

The document is written only if a splice happened, and the write does not stamp `updated`.

### On save — the user's edit wins, but only where they made one

`b` is the baseline: what the mirror read when the document was opened or last reconciled.

| Baseline | Mirror now | Task now | Outcome | Effect |
|---|---|---|---|---|
| `b` | `b` | `b` | `unchanged` | nothing written |
| `b` | `¬b` | `b` | `task_written` | write `tasks.md` |
| `b` | `b` | `¬b` | `mirror_corrected` | splice the mirror to the task's state |
| `b` | `¬b` | `¬b` | `conflict` | write `tasks.md` from the mirror, **warn** |
| absent | any | any | `task_written` | a mirror added this session is the user's edit |
| — | two mirrors disagreeing | any | `ambiguous` | `tasks.md` untouched for that task, **warn** |
| — | any | no such task | `dead` | left byte-identical, **warn** |

Rows two and four write the same value. What differs is that row four reports the divergence instead of
resolving it silently — which is the only reason the baseline is carried at all.

### Propagation — from the tasks list outward

`tasks.md` is written first, always. Then, for each id in the task's `links` field:

1. Resolve it. Unresolvable → warn, continue.
2. Read the document. Unreadable → warn, continue.
3. Find mirrors for this task. None → no write.
4. Splice to the task's state. Already matching → no write.
5. Write without stamping `updated`, unless the document is open with unsaved changes — then leave it and
   let reconcile-on-save handle it.

A mirror in a document the task does not link to — a copy-paste — is not reached here, by design. It is
corrected the next time that document is opened.

---

## Invariants

1. `tasks.md` holds the state. A mirror is a view; two mirrors are two views; none of them is a record.
2. Every write into a document is one character, at an offset found by id on that same pass.
3. `tasks.md` is written before any document, and no document failure reverses it.
4. A sync write never stamps `updated`. A user save always does.
5. A document is opened for writing only when a splice actually changed something.
6. Reconciling reads at most two files: the document in hand and `tasks.md`.
7. Nothing is written that names a task which does not exist.
8. Applying a state in one direction never triggers a write in the other on the same pass.
