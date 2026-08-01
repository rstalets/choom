from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from endpaper.core.documents import _TOKEN_PATTERN, _validate_token
from endpaper.core.errors import NotFoundError, UsageError, WorkspaceError
from endpaper.core.models import ParsedTasks, ScanWarning, Task, TaskFilter, Workspace
from endpaper.core.text import new_task_id, parse_tags

_TASK_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>[-*+])[ \t]+\[(?P<state>[ xX])\][ \t]+(?P<rest>.*)$"
)
_IDVAL = re.compile(r"^[A-Za-z0-9_-]+$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RECOGNIZED_KEYS = frozenset({"id", "type", "tags", "links", "created"})
_TERMINATORS = ("\r\n", "\n", "\r")

TASKS_PATH = Path("tasks.md")


def _split_terminator(line: str) -> tuple[str, str]:
    for terminator in _TERMINATORS:
        if line.endswith(terminator):
            return line[: -len(terminator)], terminator
    return line, ""


def _split_comment(rest: str) -> tuple[str, str | None, bool]:
    """Locate the last ``<!-- ... -->`` on the line, if any.

    Returns (text_before, body, unterminated). `body` is None when there is no
    `<!--` at all. `unterminated` is True when a `<!--` is opened but never closed.
    """
    idx = rest.rfind("<!--")
    if idx == -1:
        return rest, None, False
    end = rest.find("-->", idx + 4)
    if end == -1:
        return rest, None, True
    return rest[:idx], rest[idx + 4 : end], False


def _classify_body(body: str) -> tuple[str, dict[str, str]]:
    """Classify a closed comment's contents as bare / malformed / task."""
    tokens = body.split()
    fields: dict[str, str] = {}
    has_recognized = False
    has_unknown = False

    for token in tokens:
        key, sep, value = token.partition(":")
        if sep and key in _RECOGNIZED_KEYS:
            has_recognized = True
            fields[key] = value
        else:
            has_unknown = True

    if not has_recognized:
        return "bare", {}
    if has_unknown:
        return "malformed", {}

    if "id" in fields and not _IDVAL.match(fields["id"]):
        return "malformed", {}
    if "type" in fields and not _TOKEN_PATTERN.match(fields["type"]):
        return "malformed", {}
    if "tags" in fields:
        tag_values = fields["tags"].split(",") if fields["tags"] else []
        if not tag_values or any(not _TOKEN_PATTERN.match(tag) for tag in tag_values):
            return "malformed", {}
    if "links" in fields:
        link_values = fields["links"].split(",") if fields["links"] else []
        if not link_values or any(not _IDVAL.match(link) for link in link_values):
            return "malformed", {}

    return "task", fields


def parse_tasks(text: str) -> ParsedTasks:
    """Classify every line of a tasks.md document.

    Never raises. Malformed lines become warnings, not exceptions.
    ``"".join(result.lines) == text`` for any input.
    """
    raw_lines = text.splitlines(keepends=True)
    tasks: list[Task] = []
    warnings: list[ScanWarning] = []
    needs_id: list[int] = []

    for idx, raw_line in enumerate(raw_lines):
        line_no = idx + 1
        content, _terminator = _split_terminator(raw_line)

        match = _TASK_LINE.match(content)
        if match is None:
            continue

        rest = match.group("rest")
        done = match.group("state") in ("x", "X")

        before, body, unterminated = _split_comment(rest)

        if body is None and not unterminated:
            tasks.append(
                Task(
                    id=None,
                    text=rest.rstrip(),
                    done=done,
                    type="",
                    tags=(),
                    created=None,
                    line=line_no,
                )
            )
            needs_id.append(idx)
            continue

        if unterminated:
            warnings.append(
                ScanWarning(
                    path=TASKS_PATH,
                    reason="task_unterminated_comment",
                    message=f"tasks.md:{line_no}: unterminated comment on a task line",
                )
            )
            continue

        assert body is not None
        classification, fields = _classify_body(body)

        if classification == "bare":
            tasks.append(
                Task(
                    id=None,
                    text=rest.rstrip(),
                    done=done,
                    type="",
                    tags=(),
                    created=None,
                    line=line_no,
                )
            )
            needs_id.append(idx)
            continue

        if classification == "malformed":
            warnings.append(
                ScanWarning(
                    path=TASKS_PATH,
                    reason="task_malformed_comment",
                    message=f"tasks.md:{line_no}: malformed metadata comment on a task line",
                )
            )
            continue

        task_id = fields.get("id")
        task_type = fields.get("type", "")
        tags_raw = fields.get("tags", "")
        tags = tuple(tags_raw.split(",")) if tags_raw else ()
        links_raw = fields.get("links", "")
        links = tuple(links_raw.split(",")) if links_raw else ()

        created_raw = fields.get("created")
        created_value: date | None = None
        if created_raw:
            if _ISO_DATE.match(created_raw):
                try:
                    created_value = date.fromisoformat(created_raw)
                except ValueError:
                    created_value = None
            if created_value is None:
                warnings.append(
                    ScanWarning(
                        path=TASKS_PATH,
                        reason="task_invalid_value",
                        message=f"tasks.md:{line_no}: invalid created date {created_raw!r}",
                    )
                )

        tasks.append(
            Task(
                id=task_id,
                text=before.rstrip(),
                done=done,
                type=task_type,
                tags=tags,
                links=links,
                created=created_value,
                line=line_no,
            )
        )

    return ParsedTasks(
        tasks=tuple(tasks),
        warnings=tuple(warnings),
        lines=tuple(raw_lines),
        needs_id=tuple(needs_id),
    )


def _render_comment(
    *,
    id: str,
    type: str = "",
    tags: Sequence[str] = (),
    links: Sequence[str] = (),
    created: date | None = None,
) -> str:
    fields = [f"id:{id}"]
    if type:
        fields.append(f"type:{type}")
    if tags:
        fields.append(f"tags:{','.join(tags)}")
    if links:
        fields.append(f"links:{','.join(links)}")
    if created is not None:
        fields.append(f"created:{created.isoformat()}")
    return f"<!-- {' '.join(fields)} -->"


def render_task_line(
    text: str,
    *,
    done: bool = False,
    id: str,
    type: str = "",
    tags: Sequence[str] = (),
    links: Sequence[str] = (),
    created: date | None = None,
) -> str:
    """Render one task line, without a terminator.

    Fields appear in the order id, type, tags, links, created; empty ones are
    omitted. Raises UsageError if `text` is empty after stripping.
    """
    stripped = text.strip()
    if not stripped:
        raise UsageError("task text must not be empty")
    checkbox = "x" if done else " "
    comment = _render_comment(id=id, type=type, tags=tags, links=links, created=created)
    return f"- [{checkbox}] {stripped} {comment}"


def filter_tasks(tasks: Iterable[Task], f: TaskFilter) -> list[Task]:
    """Conjunctive filter. Sorts oldest-first, undated last, stable within a date.

    `only_done=True` selects completed tasks only and overrides `include_done`.
    """
    results: list[Task] = []
    for task in tasks:
        if f.only_done:
            if not task.done:
                continue
        elif not f.include_done and task.done:
            continue
        if f.type is not None and task.type.lower() != f.type.lower():
            continue
        if f.tags:
            task_tags = {tag.lower() for tag in task.tags}
            if not all(tag.lower() in task_tags for tag in f.tags):
                continue
        results.append(task)
    return sorted(results, key=lambda t: (t.created is None, t.created or date.min))


def match_task(task: Task, query: str) -> bool:
    """Case-insensitive substring over text, type, and tags. For the TUI's live filter."""
    haystack = " ".join([task.text, task.type, *task.tags]).lower()
    return query.lower() in haystack


def _atomic_write(path: Path, lines: Sequence[str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                fh.write("".join(lines))
            os.replace(tmp_path, path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
    except (PermissionError, OSError) as exc:
        raise WorkspaceError(f"could not write {path}: {exc}") from exc


def _read_text(path: Path) -> str:
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except OSError as exc:
        raise WorkspaceError(f"could not read {path}: {exc}") from exc


def load_tasks(workspace: Workspace) -> tuple[list[Task], list[ScanWarning]]:
    """Read tasks.md, backfill missing identifiers in place, return records.

    A missing tasks.md is an empty list, not an error. Backfill is best-effort: if
    the file cannot be written, the affected tasks are returned with id=None plus
    a warning, and the read still succeeds (FR-038).
    """
    path = workspace.tasks_file
    if not path.exists():
        return [], []

    text = _read_text(path)
    parsed = parse_tasks(text)
    warnings = [replace(w, path=path) for w in parsed.warnings]
    tasks = list(parsed.tasks)

    if not parsed.needs_id:
        return tasks, warnings

    taken = {t.id for t in tasks if t.id is not None}
    lines = list(parsed.lines)
    id_map: dict[int, str] = {}
    for idx in parsed.needs_id:
        new_id = new_task_id(taken)
        taken.add(new_id)
        id_map[idx] = new_id
        content, terminator = _split_terminator(lines[idx])
        lines[idx] = f"{content} <!-- id:{new_id} -->{terminator}"

    try:
        _atomic_write(path, lines)
    except WorkspaceError as exc:
        warnings.append(
            ScanWarning(
                path=path,
                reason="task_invalid_value",
                message=f"could not backfill task ids: {exc}",
            )
        )
        return tasks, warnings

    return [
        replace(task, id=id_map[task.line - 1]) if (task.line - 1) in id_map else task
        for task in tasks
    ], warnings


def add_task(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Task:
    """Append one task to tasks.md and return it.

    Parses inline #tags out of `description` and merges them after `tags`, exactly
    as create_document does. Creates tasks.md if absent. Every pre-existing byte is
    preserved; if the file did not end with a newline, the terminator is added.
    """
    when = now or datetime.now()
    title, inline_tags = parse_tags(description)
    if not title:
        raise UsageError("description must not be empty after removing #tag tokens")

    normalized_type = _validate_token(type, "type") if type else ""
    merged_tags: list[str] = []
    for tag in (*tags, *inline_tags):
        normalized = _validate_token(tag, "tag")
        if normalized not in merged_tags:
            merged_tags.append(normalized)

    path = workspace.tasks_file
    existing_text = _read_text(path) if path.exists() else ""
    parsed = parse_tasks(existing_text)
    taken = {t.id for t in parsed.tasks if t.id is not None}
    new_id = new_task_id(taken)

    rendered = render_task_line(
        title,
        done=False,
        id=new_id,
        type=normalized_type,
        tags=tuple(merged_tags),
        created=when.date(),
    )

    lines = list(parsed.lines)
    if lines:
        last_content, last_terminator = _split_terminator(lines[-1])
        if not last_terminator:
            lines[-1] = last_content + "\n"
    lines.append(rendered + "\n")

    _atomic_write(path, lines)

    return Task(
        id=new_id,
        text=title,
        done=False,
        type=normalized_type,
        tags=tuple(merged_tags),
        created=when.date(),
        line=len(lines),
    )


def _format_line_numbers(numbers: Sequence[int]) -> str:
    if len(numbers) == 2:
        return f"{numbers[0]} and {numbers[1]}"
    return ", ".join(str(n) for n in numbers[:-1]) + f", and {numbers[-1]}"


def set_task_state(workspace: Workspace, task_id: str, *, done: bool) -> Task:
    """Set one task's checkbox and return the task as it now stands.

    Re-reads and re-parses before writing; locates by id, never by a cached line
    number. Changes exactly one character on that line. No-op (no write) if the
    task already has the requested state.
    """
    path = workspace.tasks_file
    if not path.exists():
        raise NotFoundError(f"no task with id {task_id!r}")

    text = _read_text(path)
    parsed = parse_tasks(text)
    matches = [t for t in parsed.tasks if t.id == task_id]

    if not matches:
        raise NotFoundError(f"no task with id {task_id!r}")
    if len(matches) > 1:
        line_numbers = _format_line_numbers([t.line for t in matches])
        raise UsageError(
            f"id {task_id!r} appears on lines {line_numbers}; "
            "edit tasks.md to give one of them a different id"
        )

    task = matches[0]
    if task.done == done:
        return task

    lines = list(parsed.lines)
    idx = task.line - 1
    content, terminator = _split_terminator(lines[idx])
    match = _TASK_LINE.match(content)
    assert match is not None
    state_start, state_end = match.span("state")
    new_char = "x" if done else " "
    lines[idx] = content[:state_start] + new_char + content[state_end:] + terminator

    _atomic_write(path, lines)

    return replace(task, done=done)
