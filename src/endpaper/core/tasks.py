from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from endpaper.core.atomic_write import write_text_atomic
from endpaper.core.documents import _TOKEN_PATTERN, _validate_token
from endpaper.core.errors import NotFoundError, UsageError, WorkspaceError
from endpaper.core.models import ParsedTasks, ScanWarning, Task, TaskBodySpan, TaskFilter, Workspace
from endpaper.core.text import _split_terminator, matches_terms, new_task_id, parse_tags

_TASK_LINE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>[-*+])[ \t]+\[(?P<state>[ xX])\][ \t]+(?P<rest>.*)$"
)
_IDVAL = re.compile(r"^[A-Za-z0-9_-]+$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RECOGNIZED_KEYS = frozenset({"id", "type", "tags", "links", "created"})

TASKS_PATH = Path("tasks.md")


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


def _is_checkbox_line(content: str) -> bool:
    return _TASK_LINE.match(content) is not None


def _line_indent(content: str) -> str:
    stripped = content.lstrip(" \t")
    return content[: len(content) - len(stripped)]


def _common_indent(lines: Sequence[str]) -> str:
    """Longest common leading-whitespace prefix across `lines`' non-blank content.

    Returns "" when there are no non-blank lines, or when the non-blank lines
    share no common prefix at all -- e.g. one starts with a space and another
    with a tab. That empty result is the signal a caller uses to skip dedenting
    rather than strip a prefix that was never really there (research R2).
    """
    prefixes: list[str] = []
    for line in lines:
        content, _terminator = _split_terminator(line)
        if content.strip() == "":
            continue
        prefixes.append(_line_indent(content))

    if not prefixes:
        return ""

    common = prefixes[0]
    for prefix in prefixes[1:]:
        limit = min(len(common), len(prefix))
        matched = 0
        while matched < limit and common[matched] == prefix[matched]:
            matched += 1
        common = common[:matched]
        if not common:
            break
    return common


def _body_span(lines: Sequence[str], task_index: int) -> TaskBodySpan:
    """Compute the body span for the task whose checkbox line is `lines[task_index]`.

    The span starts on the line after the checkbox line and runs through the last
    indented, non-blank line before a terminator: a checkbox line at any indent, or a
    non-blank line with no leading whitespace (research R1). Blank lines are kept when
    more indented content follows and dropped when they only trail. Never raises and
    never looks past the end of `lines`.
    """
    n = len(lines)
    start = task_index + 1
    committed_end = start
    idx = start

    while idx < n:
        content, _terminator = _split_terminator(lines[idx])
        if content.strip() == "":
            idx += 1
            continue
        if _is_checkbox_line(content) or not content[0].isspace():
            break
        idx += 1
        committed_end = idx

    indent = _common_indent(lines[start:committed_end]) or "  "
    return TaskBodySpan(start=start, end=committed_end, indent=indent)


def _dedent_body(lines: Sequence[str], span: TaskBodySpan) -> str:
    """Render a span's lines as the body text handed to editors and the CLI.

    The longest common leading-whitespace prefix is stripped; when the span's lines
    share none (mixed tabs and spaces at column zero), nothing is stripped and the
    original depth is preserved verbatim rather than guessed at (research R2). Leading
    and trailing blank lines are dropped so the round-trip through `set_task_body` is
    stable (research R4). Returns "" for an empty span.
    """
    span_lines = lines[span.start : span.end]
    raw_common = _common_indent(span_lines)

    body_lines: list[str] = []
    for line in span_lines:
        content, _terminator = _split_terminator(line)
        if raw_common and content.startswith(raw_common):
            content = content[len(raw_common) :]
        body_lines.append(content)

    while body_lines and body_lines[0] == "":
        body_lines.pop(0)
    while body_lines and body_lines[-1] == "":
        body_lines.pop()

    return "\n".join(body_lines)


def parse_tasks(text: str) -> ParsedTasks:
    """Classify every line of a tasks.md document.

    Never raises. Malformed lines become warnings, not exceptions.
    ``"".join(result.lines) == text`` for any input. Populates `Task.body` and
    `ParsedTasks.bodies` (positionally aligned with `tasks`) from each task's
    indented continuation lines, per contracts/task-file-format.md.
    """
    raw_lines = text.splitlines(keepends=True)
    tasks: list[Task] = []
    bodies: list[TaskBodySpan] = []
    warnings: list[ScanWarning] = []
    needs_id: list[int] = []

    def _append_task(
        *,
        id: str | None,
        text: str,
        done: bool,
        type: str,
        tags: tuple[str, ...],
        created: date | None,
        line: int,
        idx: int,
        links: tuple[str, ...] = (),
    ) -> None:
        span = _body_span(raw_lines, idx)
        tasks.append(
            Task(
                id=id,
                text=text,
                done=done,
                type=type,
                tags=tags,
                links=links,
                created=created,
                line=line,
                body=_dedent_body(raw_lines, span),
            )
        )
        bodies.append(span)

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
            _append_task(
                id=None,
                text=rest.rstrip(),
                done=done,
                type="",
                tags=(),
                created=None,
                line=line_no,
                idx=idx,
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
            _append_task(
                id=None,
                text=rest.rstrip(),
                done=done,
                type="",
                tags=(),
                created=None,
                line=line_no,
                idx=idx,
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

        _append_task(
            id=task_id,
            text=before.rstrip(),
            done=done,
            type=task_type,
            tags=tags,
            links=links,
            created=created_value,
            line=line_no,
            idx=idx,
        )

    return ParsedTasks(
        tasks=tuple(tasks),
        warnings=tuple(warnings),
        lines=tuple(raw_lines),
        needs_id=tuple(needs_id),
        bodies=tuple(bodies),
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
    """Case-insensitive over text, type, and tags; every term must appear, order
    irrelevant. For the TUI's live filter."""
    return matches_terms(" ".join([task.text, task.type, *task.tags]), query)


def _atomic_write(path: Path, lines: Sequence[str]) -> None:
    """Thin wrapper kept for tasks.py's own call sites, which all already hold
    a list of lines rather than one string -- the shared primitive itself only
    knows how to write text."""
    write_text_atomic(path, "".join(lines))


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


def get_task(workspace: Workspace, task_id: str) -> Task:
    """Return one task with its body, located by id.

    Raises:
        NotFoundError: no task has `task_id`.
        UsageError: more than one task has `task_id` (names the conflicting lines).
    """
    tasks, _warnings = load_tasks(workspace)
    matches = [t for t in tasks if t.id == task_id]

    if not matches:
        raise NotFoundError(f"no task with id {task_id!r}")
    if len(matches) > 1:
        line_numbers = _format_line_numbers([t.line for t in matches])
        raise UsageError(
            f"id {task_id!r} appears on lines {line_numbers}; "
            "edit tasks.md to give one of them a different id"
        )

    return matches[0]


def set_task_body(workspace: Workspace, task_id: str, body: str) -> Task:
    """Replace one task's body span and return the task as it now stands.

    Re-reads and re-parses before writing; locates by id, never by a cached line
    number. Returns without writing at all when `body` already matches what's on
    disk (research R3) -- the byte-identical no-op save. A non-empty `body` is
    re-indented by the span's observed prefix, with one blank line written between
    the checkbox line and the first body line so the file stays valid CommonMark
    (research R4). An empty `body` removes the span entirely, leaving a lone
    checkbox line with no residual blank or indented lines. Every line outside the
    span is byte-identical; the file's line-ending convention and trailing-newline
    state are preserved.

    Raises:
        NotFoundError: no task has `task_id`.
        UsageError: more than one task has `task_id` (names the conflicting lines).
        WorkspaceError: the file cannot be written.
    """
    path = workspace.tasks_file
    if not path.exists():
        raise NotFoundError(f"no task with id {task_id!r}")

    text = _read_text(path)
    parsed = parse_tasks(text)
    matching_indices = [i for i, t in enumerate(parsed.tasks) if t.id == task_id]

    if not matching_indices:
        raise NotFoundError(f"no task with id {task_id!r}")
    if len(matching_indices) > 1:
        line_numbers = _format_line_numbers([parsed.tasks[i].line for i in matching_indices])
        raise UsageError(
            f"id {task_id!r} appears on lines {line_numbers}; "
            "edit tasks.md to give one of them a different id"
        )

    index = matching_indices[0]
    task = parsed.tasks[index]
    if body == task.body:
        return task

    span = parsed.bodies[index]
    lines = list(parsed.lines)
    checkbox_idx = span.start - 1
    checkbox_content, checkbox_terminator = _split_terminator(lines[checkbox_idx])
    tail = lines[span.end :]

    newline = next((t for line in lines if (t := _split_terminator(line)[1])), "\n")
    original_trailing = bool(lines) and _split_terminator(lines[-1])[1] != ""

    body_block: list[str] = []
    if body:
        body_block.append("")
        body_block.extend(f"{span.indent}{line}" if line else "" for line in body.split("\n"))

    if body_block and not checkbox_terminator:
        # The checkbox line was the last line of the file with no body -- now
        # something follows it, so it needs the file's own line ending.
        checkbox_terminator = newline

    new_block = [checkbox_content + checkbox_terminator]
    new_block.extend(content + newline for content in body_block)

    if not tail:
        # What we just wrote is now the end of the file -- restore the file's
        # own trailing-newline state on its new last line, whichever one that is.
        last_content, _terminator = _split_terminator(new_block[-1])
        new_block[-1] = last_content + (newline if original_trailing else "")

    new_lines = lines[:checkbox_idx] + new_block + tail
    _atomic_write(path, new_lines)

    return replace(task, body=body)
