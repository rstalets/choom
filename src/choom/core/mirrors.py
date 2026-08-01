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
    MirrorReport,
    MirrorResolution,
    ReplyCapture,
    SaveResult,
    ScanWarning,
    Task,
    Workspace,
)
from choom.core.tasks import add_task, load_tasks, set_task_state

_MIRROR_PREFIX = re.compile(r"^(?P<indent>[ \t]*)[-*+] \[(?P<state>[ xX])\] ")


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
    task_links_by_line: dict[int, list[tuple[int, str, str]]] = {}
    for link in find_links(text, source=source):
        if link.target_id is None or not link.target_id.startswith("task_"):
            continue
        task_links_by_line.setdefault(link.line, []).append((link.start, link.target_id, link.text))

    if not task_links_by_line:
        return ()

    lines = text.split("\n")
    line_starts: list[int] = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)

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
        _start, task_id, link_text = candidates[0]
        state_offset = line_starts[index] + match.start("state")
        mirrors.append(
            Mirror(
                task_id=task_id,
                done=match.group("state") in ("x", "X"),
                line=line_no,
                state_offset=state_offset,
                text=link_text,
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


def capture_reply_tasks(
    workspace: Workspace, text: str, *, source: Path, source_id: str
) -> ReplyCapture:
    """Walk an assistant reply, capturing every eligible task line through `capture_task`.

    Classifies `text` with `parse_reply_lines`, then for each eligible line -- top to
    bottom, so tasks reach tasks.md in the reply's own order -- calls `capture_task` with
    that line's argument and type suffix and substitutes the returned mirror line for the
    text of that line. Every other line is carried through byte-identical. Writes
    tasks.md through `capture_task`, once per eligible line, and nothing else.

    Returns `ReplyCapture(text, tasks, warnings)`. When `text` has no eligible line, the
    returned `text` is `text` itself -- the same object -- and no read or write happens
    (FR-011).

    Raises: UsageError or WorkspaceError, propagated from `capture_task`, on the first
    line that cannot be captured -- this is the success-path implementation; per-line
    failure recovery lands separately.
    """
    lines = parse_reply_lines(text)
    if not any(line.task is not None for line in lines):
        return ReplyCapture(text=text, tasks=(), warnings=())

    tasks: list[Task] = []
    out_lines: list[str] = []
    for line in lines:
        if line.task is None:
            out_lines.append(line.text)
            continue
        task, mirror = capture_task(
            workspace,
            line.task.argument,
            type=line.task.suffix,
            source=source,
            source_id=source_id,
        )
        tasks.append(task)
        out_lines.append(mirror)

    return ReplyCapture(text="\n".join(out_lines), tasks=tuple(tasks), warnings=())


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
