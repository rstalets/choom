"""The edge between a checkbox in a document and a task in tasks.md.

A mirror is an ordinary CommonMark checklist item whose link fragment names a task
id -- content the user wanted in their note that is simultaneously a control
surface onto that task's completion state. This module owns everything about that
edge: recognising a mirror, writing one at capture time, pushing a task's state
into a document, and resolving which side wins when a mirror and its task
disagree. It does not own the link grammar (`links.py`, consumed here) or
`tasks.md` itself (`tasks.py`, consumed here) -- see plan.md's Structure Decision.

Every write into a document is a one-character splice at a recorded offset, never
a re-render and never located by line number or text match (Principle IV, FR-015).
A sync write -- from a toggle in the tasks list, or from reconcile-on-open --
never stamps `updated` (FR-029); only a user save, through `editing.save_buffer`,
does that.
"""

from __future__ import annotations

import re
from collections.abc import Container, Mapping
from datetime import datetime
from pathlib import Path

from choom.core.atomic_write import write_text_atomic
from choom.core.editing import _apply_line_ending_policy, load_for_edit
from choom.core.editor_commands import parse_reply_lines
from choom.core.errors import NotFoundError, UsageError, WorkspaceError
from choom.core.links import find_links, format_link, resolve_id
from choom.core.models import (
    EditableFile,
    LinkTarget,
    Mirror,
    MirrorDeletion,
    MirrorReport,
    MirrorResolution,
    ReplyCapture,
    SaveResult,
    ScanWarning,
    Task,
    Workspace,
)
from choom.core.tasks import add_task, delete_task, load_tasks, parse_tasks, set_task_state

_MIRROR_PREFIX = re.compile(r"^(?P<indent>[ \t]*)[-*+] \[(?P<state>[ xX])\] ")


def _split_lines(text: str) -> tuple[list[str], list[int]]:
    """`text` split on "\n", plus the character offset each line starts at.

    Shared by `find_mirrors` and `plan_mirror_deletion` so the two never
    compute a line's start offset by a slightly different rule. When `text`
    ends with "\n", the final element of both lists describes the empty tail
    after the last real line, which is what lets a removal span run cleanly
    to `len(text)`."""
    lines = text.split("\n")
    line_starts = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)
    return lines, line_starts


# --- Recognition ----------------------------------------------------------------


def find_mirrors(text: str, *, source: Path) -> tuple[Mirror, ...]:
    """Every checklist line in `text` that is a control surface onto a task.

    A line qualifies when it matches the checklist prefix *and* carries a link
    whose destination fragment is a task id. Where a line holds several such
    links the first (by document order) is the mirror and the rest are ordinary
    links.

    Delegates link-finding to `links.find_links`, so fenced code blocks, inline
    code spans, images, and URL-scheme destinations are excluded before this
    ever sees them.

    Each Mirror carries the character offset of its single state character, so a
    caller splices rather than re-renders.

    Never raises. Any input is valid input; a line this cannot make sense of is a
    line the user typed.
    """
    task_links_by_line: dict[int, list[tuple[int, int, str, str]]] = {}
    for link in find_links(text, source=source):
        if link.target_id is None or not link.target_id.startswith("task_"):
            continue
        task_links_by_line.setdefault(link.line, []).append(
            (link.start, link.end, link.target_id, link.text)
        )

    if not task_links_by_line:
        return ()

    lines, line_starts = _split_lines(text)

    mirrors: list[Mirror] = []
    for line_no, candidates in task_links_by_line.items():
        index = line_no - 1
        if index < 0 or index >= len(lines):
            continue
        content = lines[index]
        match = _MIRROR_PREFIX.match(content)
        if match is None:
            continue
        candidates.sort(key=lambda c: c[0])
        link_start, link_end, task_id, link_text = candidates[0]
        state_offset = line_starts[index] + match.start("state")
        mirrors.append(
            Mirror(
                task_id=task_id,
                done=match.group("state") in ("x", "X"),
                line=line_no,
                state_offset=state_offset,
                text=link_text,
                link_start=link_start,
                link_end=link_end,
            )
        )

    mirrors.sort(key=lambda m: m.line)
    return tuple(mirrors)


def _apply_state(text: str, mirror: Mirror, done: bool) -> str:
    """The one-character splice: `text` with `mirror`'s state character set to
    `done`. Returns `text` itself, unchanged, when `mirror.done` already equals
    `done` -- so a caller can test identity to skip a write (FR-030)."""
    if mirror.done == done:
        return text
    char = "x" if done else " "
    offset = mirror.state_offset
    return text[:offset] + char + text[offset + 1 :]


# --- Writing a mirror -------------------------------------------------------------


def mirror_line(task: Task, *, source: Path, tasks_file: Path) -> str:
    """The checklist line to leave in `source` for `task`.

    Builds the link through `links.format_link(source, target, text)` with a
    LinkTarget of kind "task", so destination escaping -- spaces, parentheses,
    angle brackets -- is decided in exactly one place and the editor, the healer,
    and `/link` can never disagree about it. The path inside comes from
    `relative_destination`, correct from any depth the layout produces.

    The link text is the task's description as stored, tags already extracted.

    Pure string arithmetic. Touches no filesystem. Never raises.
    """
    assert task.id is not None
    target = LinkTarget(id=task.id, path=tasks_file, title=task.text, kind="task", line=task.line)
    link = format_link(source, target, task.text)
    checkbox = "x" if task.done else " "
    return f"- [{checkbox}] {link}"


def capture_task(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    source: Path,
    source_id: str,
    now: datetime | None = None,
) -> tuple[Task, str]:
    """Create a task linked to the document it was captured in, and return it
    with the line to leave behind.

    Description parsing, #tag extraction, token validation, id generation, and
    line rendering all go through `tasks.add_task` -- this adds the link and the
    mirror and nothing else, so a task's shape never depends on where it was
    typed (FR-004).

    Raises:
        UsageError: the description is empty after removing #tag tokens, or a
            type or tag token is rejected. Nothing is written.
        WorkspaceError: tasks.md could not be written. Nothing is written.
    """
    task = add_task(workspace, description, type=type, links=(source_id,), now=now)
    line = mirror_line(task, source=source, tasks_file=workspace.tasks_file)
    return task, line


def _tighten_captured_runs(out_lines: list[str], captured: set[int]) -> list[str]:
    """Drop blank lines that sit between two captured task lines.

    An assistant may write its task lines as a loose list -- one blank line between
    each -- and both shapes are ordinary markdown, so which one arrives is not
    something the reply can be relied on to settle. Substituting each line for its
    mirror then leaves a gappy checklist in the user's note, which is not what a
    captured list of commitments should look like.

    Only a run of blank lines with a captured line on *both* sides is dropped. A blank
    line between prose and the first task is block separation and stays; so does one
    after the last task, and so does one beside a task line whose capture failed --
    that line is still the assistant's text, not a checklist item.
    """
    if len(captured) < 2:
        return out_lines
    drop: set[int] = set()
    ordered = sorted(captured)
    for start, end in zip(ordered, ordered[1:], strict=False):
        between = range(start + 1, end)
        if between and all(out_lines[i].strip() == "" for i in between):
            drop.update(between)
    return [line for index, line in enumerate(out_lines) if index not in drop]


def capture_reply_tasks(
    workspace: Workspace, text: str, *, source: Path, source_id: str
) -> ReplyCapture:
    """Walk an assistant reply, capturing every eligible task line through `capture_task`.

    Classifies `text` with `parse_reply_lines`, then for each eligible line -- top to
    bottom, so tasks reach tasks.md in the reply's own order -- calls `capture_task` with
    that line's argument and type suffix and substitutes the returned mirror line for the
    text of that line. Every other line is carried through byte-identical. Writes
    tasks.md through `capture_task`, once per eligible line, and nothing else.

    The one line this does not carry through is a blank one sitting between two
    captured lines, which is dropped so a loose list of task lines becomes a tight
    checklist (`_tighten_captured_runs`, FR-010a). No line carrying any character is
    ever dropped.

    Returns `ReplyCapture(text, tasks, warnings)`. When `text` has no eligible line, the
    returned `text` is `text` itself -- the same object -- and no read or write happens
    (FR-011). No line is ever lost, under any failure: a line whose capture raises
    `UsageError` (an empty description after `#tag` removal, or a rejected type or tag
    token) or `WorkspaceError` (tasks.md could not be written) is left exactly as the
    assistant wrote it, with a `ScanWarning(reason="reply_capture_failed")` recorded for
    it, and the walk continues to the next line (FR-016, FR-017, research R10).

    Raises: nothing from the two documented failure modes above -- both are caught and
    reported as warnings. Any other exception propagates; a bug here should be loud.
    """
    lines = parse_reply_lines(text)
    if not any(line.task is not None for line in lines):
        return ReplyCapture(text=text, tasks=(), warnings=())

    tasks: list[Task] = []
    warnings: list[ScanWarning] = []
    out_lines: list[str] = []
    captured: set[int] = set()
    for line in lines:
        if line.task is None:
            out_lines.append(line.text)
            continue
        try:
            task, mirror = capture_task(
                workspace,
                line.task.argument,
                type=line.task.suffix,
                source=source,
                source_id=source_id,
            )
        except (UsageError, WorkspaceError) as exc:
            warnings.append(
                ScanWarning(
                    path=workspace.tasks_file,
                    reason="reply_capture_failed",
                    message=str(exc),
                )
            )
            out_lines.append(line.text)
            continue
        tasks.append(task)
        captured.add(len(out_lines))
        out_lines.append(mirror)

    tightened = _tighten_captured_runs(out_lines, captured)
    return ReplyCapture(text="\n".join(tightened), tasks=tuple(tasks), warnings=tuple(warnings))


# --- Deletion ---------------------------------------------------------------

#: The two `parse_tasks` warning reasons that mean a line was skipped
#: *without* producing a `Task` (src/choom/core/tasks.py, both branches
#: `continue` before `_append_task`). A task id that resolves to nothing in a
#: tasks.md carrying one of these is a task choom cannot tell "deleted" from
#: "unreadable" (research R6, FR-021). `task_invalid_value` is deliberately
#: excluded -- it still falls through to `_append_task`, so the task remains
#: findable by id and must not block a deletion that can otherwise proceed
#: (FR-022).
_UNREADABLE_TASK_REASONS = frozenset({"task_unterminated_comment", "task_malformed_comment"})

_WARNING_LINE = re.compile(r"^tasks\.md:(\d+):")


def _format_line_numbers(numbers: list[int]) -> str:
    if len(numbers) == 2:
        return f"{numbers[0]} and {numbers[1]}"
    return ", ".join(str(n) for n in numbers[:-1]) + f", and {numbers[-1]}"


def _warning_line_number(warning: ScanWarning) -> int | None:
    match = _WARNING_LINE.match(warning.message)
    return int(match.group(1)) if match else None


def _removal_span(
    text: str, lines: list[str], line_starts: list[int], index: int
) -> tuple[int, int]:
    """The character span that removes `lines[index]` and exactly its own
    line terminator (research R4, data-model.md §3).

    A line followed by another -- including the empty tail `_split_lines`
    leaves after a final "\n" -- spans from its own start to the next line's
    start, which includes the "\n" between them. The only line that cannot
    use that rule is the last line of a buffer with no trailing newline: it
    has no following start to run to, so the span instead absorbs the
    *preceding* terminator, which is what keeps removal from leaving a stray
    blank line behind. The only-line case has no preceding terminator either,
    so it spans the whole buffer.
    """
    if len(lines) == 1:
        return (0, len(text))
    if index == len(lines) - 1:
        return (line_starts[index] - 1, len(text))
    return (line_starts[index], line_starts[index + 1])


def _line_carries_extra_text(content: str, mirror: Mirror, line_start: int) -> bool:
    """FR-011: does `content` -- one line of text, already known to be
    `mirror`'s line -- hold anything besides the checklist prefix and the
    mirror's own link. Reads `mirror.link_start`/`link_end` rather than
    re-scanning for a link, so this can never disagree with `find_mirrors`
    about which link is the mirror (FR-005, FR-007)."""
    match = _MIRROR_PREFIX.match(content)
    assert match is not None  # content is mirror.line's content; the prefix matched by definition
    relative_start = mirror.link_start - line_start
    relative_end = mirror.link_end - line_start
    remainder = content[match.end() : relative_start] + content[relative_end:]
    return remainder.strip() != ""


def plan_mirror_deletion(
    workspace: Workspace,
    text: str,
    line: int,
    *,
    source: Path,
    body_task_id: str | None = None,
) -> MirrorDeletion | None:
    """Decide what deleting the task line at `line` (1-based) would do,
    without doing any of it (research R3, contracts/core-api.md §1).

    Returns `None` when `line` carries no task line -- FR-008's no-op,
    covering prose, a heading, a blank line, frontmatter, a checklist item
    with no task link, and anything inside a fenced code block or inline
    code span, all for free from `find_mirrors`/`find_links`. There is no
    second definition of what a task line is here (FR-005).

    Otherwise returns a `MirrorDeletion` whose `outcome` is decided in this
    order: `self_referential` when `body_task_id` names the same task as this
    line (FR-024); `deletable` when exactly one task record carries the id;
    `ambiguous_id` when more than one does (FR-023); `unreadable_tasks` when
    none does and tasks.md contains a line `parse_tasks` could not read
    (FR-021); `line_only` when none does and tasks.md parsed cleanly
    (FR-012).

    Reads tasks.md with `parse_tasks`, never `load_tasks` -- the latter
    backfills missing ids and writes the file, which a step running before
    the user has confirmed anything must not do (FR-014, research R6).

    Never raises. A missing tasks.md is `line_only` -- no record exists,
    nothing unparseable. An unreadable tasks.md is `unreadable_tasks` with
    the OS error folded into `message`.
    """
    mirrors = find_mirrors(text, source=source)
    mirror = next((m for m in mirrors if m.line == line), None)
    if mirror is None:
        return None

    lines, line_starts = _split_lines(text)
    index = line - 1
    content = lines[index]
    span = _removal_span(text, lines, line_starts, index)
    extra_text = _line_carries_extra_text(content, mirror, line_starts[index])
    removed_text = text[: span[0]] + text[span[1] :]

    if body_task_id is not None and body_task_id == mirror.task_id:
        return MirrorDeletion(
            outcome="self_referential",
            task_id=mirror.task_id,
            description=mirror.text,
            text="",
            span=(0, 0),
            extra_text=extra_text,
            message=(
                "this line is the task you are editing; close this editor "
                "and delete it from the tasks list"
            ),
        )

    tasks_path = workspace.tasks_file
    if not tasks_path.exists():
        return MirrorDeletion(
            outcome="line_only",
            task_id=mirror.task_id,
            description=mirror.text,
            text=removed_text,
            span=span,
            extra_text=extra_text,
        )

    try:
        raw = tasks_path.read_text(encoding="utf-8")
    except OSError as exc:
        return MirrorDeletion(
            outcome="unreadable_tasks",
            task_id=mirror.task_id,
            description=mirror.text,
            text="",
            span=(0, 0),
            extra_text=extra_text,
            message=f"tasks.md could not be read: {exc}; nothing was deleted",
        )

    parsed = parse_tasks(raw)
    matches = [t for t in parsed.tasks if t.id == mirror.task_id]

    if len(matches) > 1:
        line_numbers = _format_line_numbers(sorted(t.line for t in matches))
        return MirrorDeletion(
            outcome="ambiguous_id",
            task_id=mirror.task_id,
            description=mirror.text,
            text="",
            span=(0, 0),
            extra_text=extra_text,
            message=(
                f"id {mirror.task_id!r} appears on lines {line_numbers}; "
                "edit tasks.md to give one of them a different id"
            ),
        )

    if len(matches) == 1:
        return MirrorDeletion(
            outcome="deletable",
            task_id=mirror.task_id,
            description=mirror.text,
            text=removed_text,
            span=span,
            extra_text=extra_text,
        )

    unreadable = next((w for w in parsed.warnings if w.reason in _UNREADABLE_TASK_REASONS), None)
    if unreadable is not None:
        line_no = _warning_line_number(unreadable)
        location = f"tasks.md:{line_no}" if line_no is not None else "tasks.md"
        return MirrorDeletion(
            outcome="unreadable_tasks",
            task_id=mirror.task_id,
            description=mirror.text,
            text="",
            span=(0, 0),
            extra_text=extra_text,
            message=(
                f"{location} could not be read; fix that line, then try again "
                "-- nothing was deleted"
            ),
        )

    return MirrorDeletion(
        outcome="line_only",
        task_id=mirror.task_id,
        description=mirror.text,
        text=removed_text,
        span=span,
        extra_text=extra_text,
    )


def commit_mirror_deletion(workspace: Workspace, plan: MirrorDeletion) -> MirrorDeletion:
    """Carry out the tasks.md half of a `plan` the user has confirmed
    (contracts/core-api.md §2). Never touches the document -- the caller
    owns the buffer and applies `plan.span` itself.

    `deletable` calls the existing `tasks.delete_task`, which re-reads,
    re-parses, and locates by id before writing, so a plan gone stale between
    the confirmation and this call cannot splice into a moved line. `line_only`
    returns `plan` unchanged, having opened nothing -- there is no record to
    remove. Any refusing outcome raises `UsageError`: reaching here with one
    is a caller bug, not a user error, since the adapter is required to stop
    at the plan step (contracts/tui.md C4).

    Raises:
        NotFoundError: the record disappeared between plan and commit.
        UsageError: the id became ambiguous between plan and commit, or
            `plan.outcome` was a refusing outcome.
        WorkspaceError: tasks.md could not be written.
    """
    if plan.outcome == "deletable":
        delete_task(workspace, plan.task_id)
        return plan
    if plan.outcome == "line_only":
        return plan
    raise UsageError(f"cannot commit a refused deletion (outcome={plan.outcome!r})")


# --- The non-stamping write -------------------------------------------------------


def write_document(path: Path, text: str, file: EditableFile) -> SaveResult:
    """Write `text` to `path` atomically, restoring `file`'s line endings and
    trailing newline, without stamping `updated`.

    This is the sync path. A user save goes through `editing.save_buffer`, which
    stamps. The distinction is the whole of FR-029: ticking a box in the tasks
    list is not an edit to the meeting note.

    Writes through `core.atomic_write.write_text_atomic` -- the shared primitive
    008 landed -- rather than repeating the temp-file sequence a fifth time.
    That function raises WorkspaceError; this catches it and returns
    SaveResult(ok=False) with a user-facing message, leaving the target
    byte-identical, because every caller here is a propagation path that must
    warn and continue rather than raise.
    """
    out_text = _apply_line_ending_policy(text, file.newline, file.trailing_newline)
    try:
        write_text_atomic(path, out_text)
    except WorkspaceError as exc:
        return SaveResult(ok=False, saved_text="", stamped=False, message=str(exc))
    return SaveResult(ok=True, saved_text=text, stamped=False, message="")


# --- Reconciliation ---------------------------------------------------------------


def _dead_mirror_warning(source: Path, mirror: Mirror) -> ScanWarning:
    return ScanWarning(
        path=source,
        reason="link_dead",
        message=f"{source.name}:{mirror.line}: link {mirror.task_id!r} does not resolve",
    )


def _load_tasks_or_warning(
    workspace: Workspace, source: Path
) -> tuple[dict[str, Task], ScanWarning | None]:
    """`load_tasks`, but never raising: an unreadable tasks.md becomes one
    warning naming `source` rather than propagating WorkspaceError, so every
    caller in this module stays true to its own "never raises" contract."""
    try:
        tasks, _load_warnings = load_tasks(workspace)
    except WorkspaceError as exc:
        return {}, ScanWarning(
            path=source,
            reason="link_dead",
            message=f"{source.name}: could not read tasks.md to reconcile: {exc}",
        )
    return {t.id: t for t in tasks if t.id is not None}, None


def reconcile_on_open(workspace: Workspace, text: str, *, source: Path) -> MirrorReport:
    """Bring every mirror in `text` into agreement with tasks.md.

    The task is authoritative: the user has not acted on this document yet. A
    mirror whose id resolves to no task is left byte-identical and warned about
    (FR-028).

    Returns `text` itself -- the same object -- when nothing needed correcting,
    so a caller can test identity and skip the write entirely (FR-030).

    Reads tasks.md only when `text` actually contains a mirror; a document with
    none costs one scan of a string already in memory and no file read at all
    (SC-007).

    Never raises. An unreadable tasks.md yields the text unchanged plus a
    warning.
    """
    mirrors = find_mirrors(text, source=source)
    if not mirrors:
        return MirrorReport(text=text, resolutions=(), warnings=())

    tasks_by_id, load_warning = _load_tasks_or_warning(workspace, source)
    if load_warning is not None:
        return MirrorReport(text=text, resolutions=(), warnings=(load_warning,))

    new_text = text
    resolutions: list[MirrorResolution] = []
    warnings: list[ScanWarning] = []

    for mirror in mirrors:
        task = tasks_by_id.get(mirror.task_id)
        if task is None:
            warnings.append(_dead_mirror_warning(source, mirror))
            resolutions.append(MirrorResolution(task_id=mirror.task_id, outcome="dead", done=None))
            continue
        if task.done == mirror.done:
            resolutions.append(
                MirrorResolution(task_id=mirror.task_id, outcome="unchanged", done=mirror.done)
            )
            continue
        new_text = _apply_state(new_text, mirror, task.done)
        resolutions.append(
            MirrorResolution(task_id=mirror.task_id, outcome="mirror_corrected", done=task.done)
        )

    return MirrorReport(text=new_text, resolutions=tuple(resolutions), warnings=tuple(warnings))


def reconcile_on_save(
    workspace: Workspace,
    text: str,
    *,
    source: Path,
    baseline: Mapping[str, bool],
) -> MirrorReport:
    """Reconcile at save time, writing tasks.md where the user's edit should win.

    `baseline` is what each mirror read when the document was opened or last
    reconciled. It is what distinguishes "the user ticked this box" from "this
    box is stale", and so what makes the both-sides-changed warning possible
    (FR-024). A task id absent from `baseline` is a mirror that appeared during
    this session and counts as the user's edit.

    Writes tasks.md through `tasks.set_task_state`, one character on one line
    located by id. Corrections that should flow the other way are applied to the
    returned text in the same pass, so nothing cascades (FR-027).

    The full outcome matrix is in contracts/mirror-format.md.

    Never raises. A task that cannot be written is reported in `warnings`, and
    every other task in the document is still reconciled.
    """
    mirrors = find_mirrors(text, source=source)
    if not mirrors:
        return MirrorReport(text=text, resolutions=(), warnings=())

    tasks_by_id, load_warning = _load_tasks_or_warning(workspace, source)
    if load_warning is not None:
        return MirrorReport(text=text, resolutions=(), warnings=(load_warning,))

    by_task: dict[str, list[Mirror]] = {}
    for mirror in mirrors:
        by_task.setdefault(mirror.task_id, []).append(mirror)

    new_text = text
    resolutions: list[MirrorResolution] = []
    warnings: list[ScanWarning] = []

    for task_id, group in by_task.items():
        task = tasks_by_id.get(task_id)
        if task is None:
            for mirror in group:
                warnings.append(_dead_mirror_warning(source, mirror))
            resolutions.append(MirrorResolution(task_id=task_id, outcome="dead", done=None))
            continue

        states = {m.done for m in group}
        if len(states) > 1:
            warnings.append(
                ScanWarning(
                    path=source,
                    reason="mirror_ambiguous",
                    message=(
                        f"{source.name}: two mirrors for {task_id!r} disagree; "
                        "tasks.md left unchanged for it"
                    ),
                )
            )
            resolutions.append(MirrorResolution(task_id=task_id, outcome="ambiguous", done=None))
            continue

        mirror_done = group[0].done
        baseline_state = baseline.get(task_id)

        if baseline_state is None:
            task = _write_task_state(workspace, task_id, mirror_done, task, warnings)
            resolutions.append(
                MirrorResolution(task_id=task_id, outcome="task_written", done=mirror_done)
            )
            continue

        mirror_changed = mirror_done != baseline_state
        task_changed = task.done != baseline_state

        if not mirror_changed and not task_changed:
            resolutions.append(
                MirrorResolution(task_id=task_id, outcome="unchanged", done=baseline_state)
            )
            continue

        if mirror_changed and not task_changed:
            _write_task_state(workspace, task_id, mirror_done, task, warnings)
            resolutions.append(
                MirrorResolution(task_id=task_id, outcome="task_written", done=mirror_done)
            )
            continue

        if not mirror_changed and task_changed:
            for mirror in group:
                new_text = _apply_state(new_text, mirror, task.done)
            resolutions.append(
                MirrorResolution(task_id=task_id, outcome="mirror_corrected", done=task.done)
            )
            continue

        # both changed since the baseline -- the save wins, and it is reported.
        _write_task_state(workspace, task_id, mirror_done, task, warnings)
        warnings.append(
            ScanWarning(
                path=source,
                reason="mirror_conflict",
                message=(
                    f"{source.name}: task {task_id!r} and its mirror both changed; "
                    "the mirror's state won"
                ),
            )
        )
        resolutions.append(MirrorResolution(task_id=task_id, outcome="conflict", done=mirror_done))

    return MirrorReport(text=new_text, resolutions=tuple(resolutions), warnings=tuple(warnings))


def _write_task_state(
    workspace: Workspace,
    task_id: str,
    done: bool,
    task: Task,
    warnings: list[ScanWarning],
) -> Task:
    """`set_task_state`, but reporting a failure as a warning rather than
    propagating it -- every caller in `reconcile_on_save` must keep reconciling
    the rest of the document even if one task's write fails."""
    try:
        return set_task_state(workspace, task_id, done=done)
    except (NotFoundError, UsageError, WorkspaceError) as exc:
        warnings.append(
            ScanWarning(
                path=workspace.tasks_file,
                reason="link_dead",
                message=f"could not write task {task_id!r}: {exc}",
            )
        )
        return task


# --- Propagation --------------------------------------------------------------


def propagate_to_documents(
    workspace: Workspace,
    task: Task,
    *,
    skip: Container[Path] = (),
) -> tuple[tuple[Path, ...], tuple[ScanWarning, ...]]:
    """Write `task`'s state into the mirrors of every document it links to.

    Called after tasks.md has already been written -- never before, and never
    conditionally. A document that is missing, unreadable, unwritable, or whose
    link is dead produces a warning and does not stop the others (FR-032).

    `skip` names documents the caller knows are open with unsaved changes; they
    are left alone and reconciled at the user's next save (FR-033).

    Documents are written without stamping `updated` (FR-029), and only when a
    splice actually changed something.

    Returns `(documents_updated, warnings)`. `documents_updated` lists only the
    documents actually opened for writing -- one whose mirror already read
    correctly is not written and does not appear (FR-030), which is what lets
    `choom task done --json` report it accurately.

    Never raises. Every failure is a warning.
    """
    if not task.links or task.id is None:
        return (), ()

    written: list[Path] = []
    warnings: list[ScanWarning] = []

    for link_id in task.links:
        target, resolve_warnings = resolve_id(workspace, link_id)
        warnings.extend(resolve_warnings)
        if target is None:
            warnings.append(
                ScanWarning(
                    path=workspace.tasks_file,
                    reason="link_dead",
                    message=f"link {link_id!r} does not resolve",
                )
            )
            continue

        path = target.path
        if path in skip:
            continue

        try:
            file = load_for_edit(path)
        except OSError as exc:
            warnings.append(
                ScanWarning(
                    path=path,
                    reason="link_dead",
                    message=f"could not read {path.name}: {exc}",
                )
            )
            continue

        relevant = [m for m in find_mirrors(file.text, source=path) if m.task_id == task.id]
        if not relevant:
            continue

        new_text = file.text
        for mirror in relevant:
            new_text = _apply_state(new_text, mirror, task.done)

        if new_text is file.text:
            continue

        result = write_document(path, new_text, file)
        if not result.ok:
            warnings.append(
                ScanWarning(
                    path=path,
                    reason="link_dead",
                    message=f"could not write {path.name}: {result.message}",
                )
            )
        else:
            written.append(path)

    return tuple(written), tuple(warnings)
