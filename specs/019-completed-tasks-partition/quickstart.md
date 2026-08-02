# Quickstart: Verifying Completed Tasks Leave the Open List

**Feature**: `019-completed-tasks-partition` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Runnable checks that prove the feature works and that neither regression it could introduce is
present. Details live in [contracts/](./contracts/) and [data-model.md](./data-model.md).

## Prerequisites

```bash
uv sync
scripts/dev-tests.sh            # baseline: green before you start
```

Scratch workspace:

```bash
cd "$(mktemp -d)" && choom init
```

---

## 1. The move (US1, US2)

```bash
choom task add "call Terry" --type followup --tag vendor
choom task list --json | python3 -m json.tool          # note the id
choom task done <id>

cat tasks.md                                            # the line is gone
find tasks/done -name '*-done.md' -exec cat {} +        # it is here, with completed:
choom task list                                         # not listed
choom task list --done                                  # listed
```

**Expect**: `tasks/done/<YYYY>/<MM>/<YYYY-MM-DD>-done.md` exists; the line is byte-identical to what
was in `tasks.md` apart from `[x]` and a trailing `completed:<today>`; `task list` shows nothing.

Round-trip it:

```bash
choom task undone <id>
cat tasks.md                                            # back, with no completed: field
find tasks/done -name '*-done.md' -exec cat {} +        # day file present but empty
```

**Expect**: the record is back in `tasks.md`; the empty day file is left in place (partitions are
never pruned).

## 2. A body travels intact (US1)

```bash
printf '\n    the contract auto-renews on the 15th\n' >> tasks.md
choom task show <id>          # body prints
choom task done <id>
choom task show <id>          # same body, same indentation
```

## 3. Mirrors are not rewritten (US3) — the load-bearing check

```bash
choom meeting new "vendor sync"
# open the note in the TUI, run /task chase the renewal, save, quit
MIRROR_BEFORE=$(grep -rn 'tasks.md#task_' meetings/)
choom task done <that task id>
grep -rn 'tasks.md#task_' meetings/                     # identical to MIRROR_BEFORE
choom links check                                       # no output
```

**Expect**: the mirror's bytes are unchanged, `links check` reports nothing, and no file under
`meetings/` was written by the completion.

## 4. Regression — reconcile ticks a completed mirror (bug 2)

Continuing from §3, with the note **closed** when the task was completed:

```bash
# open the note in the TUI
```

**Expect**: the checkbox reads `[x]`, and the status bar shows **zero** warnings. A dead-link warning
here, or a box still reading `[ ]`, is the regression — `reconcile_on_open` failed to escalate to the
store (contracts/core-api.md C8).

## 5. Regression — `ctrl+t` removes both halves of a completed task (bug 1)

With the note open and the cursor on the mirror of a **completed** task:

```text
press ctrl+t → confirmation names the task → Enter
```

**Expect**: the line leaves the note **and** the record leaves the day file. If the line goes and the
record survives, `plan_mirror_deletion` took the `line_only` branch — the regression
(contracts/core-api.md C9).

## 6. Partial failure loses nothing (Principle IV)

```bash
choom task add "will not move"
chmod -w tasks              # make the store unwritable (after one completion has created it)
choom task done <id>; echo "exit=$?"
cat tasks.md                # unchanged, task still open
chmod +w tasks
```

**Expect**: exit `3`, `tasks.md` byte-identical, the task still open. Nothing moved.

The reverse ordering (destination written, source write fails) is covered in
`tests/unit/test_task_move_failure.py` rather than by hand — it needs the source made unwritable
between two writes.

## 7. An existing workspace is not swept (US5)

```bash
cat >> tasks.md <<'EOF'
- [x] something finished long ago <!-- id:task_old1 created:2026-01-05 -->
EOF
cp tasks.md /tmp/before.md
choom task list; choom task list --done; choom links check
diff /tmp/before.md tasks.md && echo "UNCHANGED"
```

**Expect**: `UNCHANGED`, and the old record appears in `--done` with no completion date.

## 8. Malformed lines never move

```bash
cat >> tasks.md <<'EOF'
- [x] broken metadata <!-- id:task_x nonsense -->
EOF
choom task list --all       # warning on stderr, line not listed as a record
grep -c 'broken metadata' tasks.md   # still 1
```

## 9. Automated suite

```bash
scripts/dev-tests.sh
scripts/dev-tests.sh tests/unit/test_task_store.py tests/unit/test_task_move_failure.py
scripts/dev-tests.sh tests/integration/test_completed_task_partition.py
scripts/dev-tests.sh -m performance tests/performance/test_task_store_scan.py
```

**Expect**: green. The performance file carries `@pytest.mark.performance`, which selects the
separate CI job added by issue #84.

| Check | Success criterion |
|---|---|
| `task list` opens exactly one file with 365 day files present | SC-003 (counted, not timed) |
| Opening a document whose mirrors are all open tasks costs one read | SC-004 |
| Whole-store read under 500 ms at 1,000 files / 5,000 records | SC-005 |
| No write outside the store and the linked documents | SC-006 |
| Both partial-failure orderings | SC-007 |
| 300 completed lines in `tasks.md` survive byte-identical | SC-008 |
| `links check` clean across a fully-completed workspace | SC-009 |
| Every pre-existing `--json` key unchanged | SC-010 |

## 10. TUI verification before release

On the terminals in `docs/REQUIREMENTS.md` §4.3:

- Space toggles a task; the row leaves Todo and appears in Done, with no visible pause.
- With several hundred completed records, the Done view scrolls and refreshes without stutter — the
  refresh tick's fingerprint precheck (plan.md, Complexity Tracking) is what this is checking. Visible
  jank every two seconds means SC-005 is breached and the named remedy is month-scoping the Done view,
  not an index.
