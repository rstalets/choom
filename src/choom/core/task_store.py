"""Where a task record lives, and how it gets there (019-completed-tasks-partition).

`choom.core.tasks` knows what a task line *is* -- the parser, the renderer, the
body span. This module knows *where a record lives and how it gets there*: the
done-store path for a completion date, the three store-wide reads (`load_tasks`
stays tasks.md-only; `load_done_tasks` and `load_task_store` are new), the move
itself in both directions, the refresh-tick stat fingerprint, and the optional
sweep. `task_store` imports `tasks`, never the reverse -- `tasks.get_task`,
`tasks.delete_task`, and `tasks.set_task_state` reach back into this module
through a function-local import instead, to avoid a circular import at load
time while keeping the boundary one-directional in spirit (see plan.md,
Structure Decision).
"""

from __future__ import annotations

import os
import re
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from choom.core.atomic_write import write_text_atomic
from choom.core.errors import NotFoundError, WorkspaceError
from choom.core.models import ParsedTasks, ScanWarning, Task, TaskBodySpan, TidySummary, Workspace
from choom.core.tasks import (
    _TASK_LINE,
    _display_path,
    _duplicate_id_error,
    _load_and_backfill,
    _read_text,
    load_tasks,
    parse_tasks,
)
from choom.core.text import _split_terminator

#: The two `parse_tasks` warning reasons that mean a line was skipped without
#: producing a `Task` at all (mirrors.py carries the same set, for the same
#: reason: neither of these can ever be a candidate for anything that resolves
#: by id, since no `Task` was ever built).
_UNREADABLE_TASK_REASONS = frozenset({"task_unterminated_comment", "task_malformed_comment"})

_COMPLETED_TOKEN_RE = re.compile(r" completed:\S+")


def done_file_for(workspace: Workspace, on: date) -> Path:
    """The day file for a completion date (C1). Pure: opens nothing, creates
    nothing, never raises."""
    return workspace.done_dir / f"{on:%Y}" / f"{on:%m}" / f"{on:%Y-%m-%d}-done.md"


def iter_done_files(workspace: Workspace) -> list[Path]:
    """Every `*.md` file under `tasks/done/`, newest day first, by lexical
    sort of the path descending (C2). Walks the tree on every call; there is
    no manifest. `[]` when the root does not exist. Never raises -- an
    unreadable directory yields the files it could enumerate (`os.walk`'s
    default `onerror=None` silently skips what it cannot list)."""
    root = workspace.done_dir
    if not root.is_dir():
        return []
    paths: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".md"):
                paths.append(Path(dirpath) / name)
    paths.sort(key=lambda p: p.as_posix(), reverse=True)
    return paths


def load_done_tasks(workspace: Workspace) -> tuple[list[Task], list[ScanWarning]]:
    """Parse every file `iter_done_files` finds with `tasks.parse_tasks` (C3).

    Each returned `Task` carries `source` set to the file it came from and
    `completed` from its own field. An unreadable or unparseable file
    produces one warning naming it and does not stop the rest (FR-022).
    Missing ids are backfilled in place, best-effort, on the same terms
    `load_tasks` uses for `tasks.md` (research R13). Never raises.
    """
    tasks: list[Task] = []
    warnings: list[ScanWarning] = []
    for path in iter_done_files(workspace):
        display_name = _display_path(workspace, path)
        try:
            file_tasks, file_warnings = _load_and_backfill(path, display_name=display_name)
        except WorkspaceError as exc:
            warnings.append(
                ScanWarning(
                    path=path,
                    reason="task_unreadable_file",
                    message=f"{display_name}: could not be read: {exc}",
                )
            )
            continue
        tasks.extend(file_tasks)
        warnings.extend(file_warnings)
    return tasks, warnings


def load_task_store(workspace: Workspace) -> tuple[list[Task], list[ScanWarning]]:
    """`load_tasks` then `load_done_tasks`, concatenated in that order,
    warnings merged (C4) -- the union `task list --done`/`--all`, `get_task`,
    `delete_task`, and `resolve_id`'s escalation all read. Never raises."""
    open_tasks, open_warnings = load_tasks(workspace)
    done_tasks, done_warnings = load_done_tasks(workspace)
    return open_tasks + done_tasks, open_warnings + done_warnings


# --- The two splices (research R2, contracts/task-store-format.md F4) ----------


def _set_state_char(content: str, done: bool) -> str:
    """The identical one-character splice `tasks.set_task_state` already
    performs, generalized to a line that is not necessarily in `tasks.md`."""
    match = _TASK_LINE.match(content)
    assert match is not None  # content is a checkbox line's content, by construction
    start, end = match.span("state")
    new_char = "x" if done else " "
    return content[:start] + new_char + content[end:]


def _comment_span(content: str) -> tuple[int, int] | None:
    """The inner body of the last `<!-- ... -->` on `content`, as character
    offsets excluding the delimiters. `None` when there is none or it is
    unterminated -- unreachable in practice here, since a line with no valid
    comment never yields a matchable id (research R2)."""
    idx = content.rfind("<!--")
    if idx == -1:
        return None
    end = content.find("-->", idx + 4)
    if end == -1:
        return None
    return idx + 4, end


def _with_completed(content: str, on: date) -> str:
    """Insert `completed:<ISO>` into the last comment on `content`, after
    whatever the user's own fields already end with (data-model.md §4)."""
    span = _comment_span(content)
    assert span is not None
    start, end = span
    body = content[start:end]
    trailing_ws = body[len(body.rstrip()) :]
    new_body = f"{body.rstrip()} completed:{on.isoformat()}{trailing_ws or ' '}"
    return content[:start] + new_body + content[end:]


def _without_completed(content: str) -> str:
    """Drop the first `completed:...` token and the one space preceding it
    from the last comment on `content` (data-model.md §4)."""
    span = _comment_span(content)
    assert span is not None
    start, end = span
    body = content[start:end]
    new_body = _COMPLETED_TOKEN_RE.sub("", body, count=1)
    return content[:start] + new_body + content[end:]


def _destination_newline(lines: list[str]) -> str:
    """The line-ending convention already in force at the end of `lines`
    (F4: "the destination file's own convention on the written block"),
    walking backward past any line with no terminator at all. `"\\n"` when
    `lines` carries no terminator anywhere -- a brand new file, or one whose
    only line has none."""
    for line in reversed(lines):
        _content, terminator = _split_terminator(line)
        if terminator:
            return terminator
    return "\n"


def _remove_span(lines: list[str], span: TaskBodySpan) -> list[str]:
    """`lines` with the checkbox line at `span.start - 1` and its whole body
    span removed, restoring the file's own trailing-newline state on
    whatever remains -- `tasks.delete_task`'s own removal, generalized to an
    arbitrary already-parsed `lines`/`span` pair rather than re-reading a
    fixed path, so `move_record` and `tidy_completed` share it instead of
    each re-implementing the same rule."""
    checkbox_idx = span.start - 1
    tail = lines[span.end :]
    newline = next((t for line in lines if (t := _split_terminator(line)[1])), "\n")
    original_trailing = bool(lines) and _split_terminator(lines[-1])[1] != ""
    new_lines = lines[:checkbox_idx] + tail
    if not tail and new_lines:
        last_content, _terminator = _split_terminator(new_lines[-1])
        new_lines[-1] = last_content + (newline if original_trailing else "")
    return new_lines


def _write_move(
    workspace: Workspace,
    *,
    source_path: Path,
    source_parsed: ParsedTasks,
    index: int,
    dest_path: Path,
    new_checkbox_content: str,
) -> int:
    """The write-ordering mechanics shared by `move_record` (a real state
    transition, whose caller has already computed `new_checkbox_content`
    with both splices applied) and `tidy_completed` (a verbatim relocation,
    which passes the checkbox line's content through unchanged): append the
    checkbox line and its whole body span to `dest_path`, then remove that
    span from `source_path`. Every body line is copied byte-for-byte, with
    only its line terminator re-set to `dest_path`'s own convention (F4).

    Destination first, source second -- always. See `move_record`'s own
    comment at its call site for why; this is not a style preference.

    Returns the new 1-based line number of the checkbox line in `dest_path`.

    Raises:
        WorkspaceError: either write failed. If the destination write
            failed, `source_path` is untouched. If the source write failed,
            the record now exists in both files.
    """
    span = source_parsed.bodies[index]
    lines = list(source_parsed.lines)
    body_lines = lines[span.start : span.end]

    dest_text = _read_text(dest_path) if dest_path.exists() else ""
    dest_lines = dest_text.splitlines(keepends=True)
    dest_newline = _destination_newline(dest_lines) if dest_lines else "\n"

    if dest_lines:
        last_content, last_terminator = _split_terminator(dest_lines[-1])
        if not last_terminator:
            dest_lines[-1] = last_content + dest_newline

    new_line_number = len(dest_lines) + 1
    dest_lines.append(new_checkbox_content + dest_newline)
    for body_line in body_lines:
        body_content, _terminator = _split_terminator(body_line)
        dest_lines.append(body_content + dest_newline)

    source_lines = _remove_span(lines, span)

    try:
        write_text_atomic(dest_path, "".join(dest_lines))
    except WorkspaceError as exc:
        raise WorkspaceError(
            f"could not write {_display_path(workspace, dest_path)}: {exc}; "
            f"{_display_path(workspace, source_path)} was not touched, nothing moved"
        ) from exc

    try:
        write_text_atomic(source_path, "".join(source_lines))
    except WorkspaceError as exc:
        raise WorkspaceError(
            f"{_display_path(workspace, dest_path)} was written but "
            f"{_display_path(workspace, source_path)} could not be updated: {exc}; "
            "the record now exists in both files -- remove one copy by hand"
        ) from exc

    return new_line_number


def _locate_in_store(workspace: Workspace, task_id: str) -> list[Task]:
    """Every record carrying `task_id`, found by a read-only scan of the
    whole store -- `tasks.md` first, then every done-store file this process
    can open, in `iter_done_files`'s order. Never writes, not even a
    best-effort id backfill: unlike `load_task_store`, this is used by a
    caller that must locate a record without having any side effect on an
    unrelated line -- `mirrors.plan_mirror_deletion` makes the same choice
    for the same reason (research R6, 017 FR-014), and `delete_task` needs
    it here so that deleting one record never silently backfills an id onto
    a different, untouched line elsewhere in the store.

    A done-store file this process cannot open is skipped rather than
    aborting the search -- an unrelated broken day file must not become a
    standing veto on an operation that has nothing to do with it.
    """
    matches: list[Task] = []

    open_path = workspace.tasks_file
    if open_path.exists():
        for candidate in parse_tasks(_read_text(open_path)).tasks:
            if candidate.id == task_id:
                matches.append(replace(candidate, source=open_path))

    for path in iter_done_files(workspace):
        try:
            text = _read_text(path)
        except WorkspaceError:
            continue
        for candidate in parse_tasks(text).tasks:
            if candidate.id == task_id:
                matches.append(replace(candidate, source=path))

    return matches


def move_record(
    workspace: Workspace, task_id: str, *, done: bool, now: datetime | None = None
) -> Task:
    """Move one task record between the open list and the done store (C5).

    Locates `task_id` across the whole store, `tasks.md` first, then
    re-reads and re-parses the file that holds it immediately before
    writing -- never trusts a cached line number. No-op (writes nothing, in
    either file) when the record already has the requested state, including
    when it currently sits in the "wrong" file for that state (FR-005) --
    only a real transition moves anything, preserving `set_task_state`'s
    existing no-op contract exactly.

    `now` is injectable (Principle VI); defaults to `datetime.now()`.

    Raises:
        NotFoundError: no record in either half of the store carries `task_id`.
        UsageError: more than one does. Names every `<file>:<line>` (research R7).
        WorkspaceError: either write failed. See `_write_move`.
    """
    when = now or datetime.now()
    open_path = workspace.tasks_file

    matches = _locate_in_store(workspace, task_id)
    if not matches:
        raise NotFoundError(f"no task with id {task_id!r}")
    if len(matches) > 1:
        raise _duplicate_id_error(workspace, task_id, matches)

    source_path = matches[0].source
    assert source_path is not None  # every match from _locate_in_store carries one
    source_text = _read_text(source_path) if source_path.exists() else ""
    source_parsed = parse_tasks(source_text)
    index = next(i for i, t in enumerate(source_parsed.tasks) if t.id == task_id)
    task = replace(source_parsed.tasks[index], source=source_path)

    if task.done == done:
        return task

    span = source_parsed.bodies[index]
    checkbox_content, checkbox_terminator = _split_terminator(source_parsed.lines[span.start - 1])
    new_content = _set_state_char(checkbox_content, done)
    new_content = (
        _with_completed(new_content, when.date()) if done else _without_completed(new_content)
    )

    dest_path = done_file_for(workspace, when.date()) if done else open_path

    if dest_path == source_path:
        # Reopening a record that never left tasks.md (FR-037/FR-039): a
        # completed task sitting in tasks.md today -- from before this
        # feature shipped, or hand-ticked -- already lives in the open
        # list's own file, so "moving" it there is an in-place splice, not
        # a relocation. Only a *later* completion actually crosses files.
        # One write, not two -- there is no destination/source pair here.
        lines = list(source_parsed.lines)
        checkbox_idx = span.start - 1
        lines[checkbox_idx] = new_content + checkbox_terminator
        write_text_atomic(source_path, "".join(lines))
        return replace(
            task,
            done=done,
            completed=when.date() if done else None,
            source=source_path,
            line=task.line,
        )

    # CRITICAL -- destination first, source second, in *both* directions.
    # There are only two possible orderings and exactly one of them can
    # never lose a line (research R3, contracts/core-api.md C5):
    #
    #   source first, destination second: if the destination write then
    #     fails, the record is gone from *both* files -- silent data loss.
    #   destination first, source second: if the source write then fails,
    #     the record exists in *both* files -- loud, and already the
    #     defined duplicate-id state that every read/write path in this
    #     tree already refuses to act on (resolve_id -> link_ambiguous;
    #     get_task / set_task_state / delete_task -> UsageError;
    #     plan_mirror_deletion -> ambiguous_id). A duplicate is recoverable
    #     by hand; a dropped line is not. Do not invert this order.
    new_line_number = _write_move(
        workspace,
        source_path=source_path,
        source_parsed=source_parsed,
        index=index,
        dest_path=dest_path,
        new_checkbox_content=new_content,
    )

    return replace(
        task,
        done=done,
        completed=when.date() if done else None,
        source=dest_path,
        line=new_line_number,
    )


def store_fingerprint(workspace: Workspace) -> tuple[tuple[str, int, int], ...]:
    """`(posix_path, st_mtime_ns, st_size)` per done-store day file, sorted
    (C6). One directory walk; opens no file -- `Path.stat()` reads metadata
    only. Never raises; an entry this process cannot stat is omitted. Held
    in memory by the caller only (plan.md, Complexity Tracking); never
    written to disk and never persisted between processes.

    A matching fingerprint is *not* proof the store is unchanged. Filesystem
    timestamp granularity (1 s on HFS+/ext3, 2 s on FAT/exFAT) can swallow a
    write, and a size-preserving edit -- a `[x]` <-> `[ ]` toggle changes no
    byte count -- leaves the tuple identical even though the file changed.
    Because the comparison callers use is tuple *inequality*, not "is newer",
    a miss like this is **permanent**: every later sample recomputes the same
    tuple, so it is missed again and again, unlike a tick that just reads
    stale data once. Callers MUST bound that staleness with a forced full
    re-read on a wall-clock interval (`tui/list_screen.py`'s 30 s bound,
    T037) rather than trust this alone indefinitely.
    """
    root = workspace.done_dir
    if not root.is_dir():
        return ()
    entries: list[tuple[str, int, int]] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".md"):
                continue
            full_path = Path(dirpath) / name
            try:
                info = full_path.stat()
            except OSError:
                continue
            entries.append((_display_path(workspace, full_path), info.st_mtime_ns, info.st_size))
    entries.sort()
    return tuple(entries)


def tidy_completed(workspace: Workspace, *, now: datetime | None = None) -> TidySummary:
    """Move every parseable completed record out of `tasks.md` into the done
    store (C7, P3, droppable). Never prompts, never runs implicitly -- the
    caller is the only thing that ever invokes this.

    Each record moves one at a time under `_write_move`'s ordering. A
    record's destination day is its own `completed:` field if it carries a
    valid one, else its `created` date (US6 acceptance scenario 2, since
    that is the only date such a record carries), else `now`. The checkbox
    line's bytes are relocated verbatim -- this never splices a `completed:`
    field onto a record that does not already have one, since data-model.md
    §2 says omitting it is legal, not an error to correct.

    A write failure partway through leaves every record moved so far moved,
    stops there, and is reported in `warnings`; every completed record still
    left in `tasks.md` afterward -- whether the loop stopped early or a line
    could never be parsed into a record at all -- is counted in `left`.
    """
    when = now or datetime.now()
    moved = 0
    warnings: list[ScanWarning] = []

    while True:
        text = _read_text(workspace.tasks_file) if workspace.tasks_file.exists() else ""
        parsed = parse_tasks(text)
        index = next((i for i, t in enumerate(parsed.tasks) if t.done and t.id is not None), None)
        if index is None:
            break

        task = parsed.tasks[index]
        target_date = task.completed or task.created or when.date()
        dest_path = done_file_for(workspace, target_date)
        span = parsed.bodies[index]
        checkbox_content, _terminator = _split_terminator(parsed.lines[span.start - 1])

        try:
            _write_move(
                workspace,
                source_path=workspace.tasks_file,
                source_parsed=parsed,
                index=index,
                dest_path=dest_path,
                new_checkbox_content=checkbox_content,
            )
        except WorkspaceError as exc:
            warnings.append(
                ScanWarning(
                    path=workspace.tasks_file,
                    reason="task_invalid_value",
                    message=f"could not move task {task.id!r}: {exc}",
                )
            )
            break

        moved += 1

    final_text = _read_text(workspace.tasks_file) if workspace.tasks_file.exists() else ""
    final_parsed = parse_tasks(final_text)
    left = sum(1 for t in final_parsed.tasks if t.done)
    left += sum(1 for w in final_parsed.warnings if w.reason in _UNREADABLE_TASK_REASONS)

    return TidySummary(moved=moved, left=left, warnings=tuple(warnings))
