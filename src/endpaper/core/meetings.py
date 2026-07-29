from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import date, datetime

from endpaper.core.errors import UsageError
from endpaper.core.frontmatter import FrontmatterError, read_frontmatter, render_frontmatter
from endpaper.core.models import Meeting, MeetingFilter, ScanWarning, Workspace
from endpaper.core.text import new_meeting_id, parse_tags, slugify

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def _validate_token(value: str, flag: str) -> str:
    if not _TOKEN_PATTERN.match(value):
        raise UsageError(f"--{flag} may not contain '/', '\\', '.', or start with '-'")
    return value.lower()


def create_meeting(
    workspace: Workspace,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Meeting:
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

    meeting_id = new_meeting_id(when.date())
    timestamp = when.replace(microsecond=0).isoformat()
    slug = slugify(title)
    date_str = when.strftime("%Y-%m-%d")
    stem = "-".join([date_str, *([normalized_type] if normalized_type else []), slug])

    meetings_dir = workspace.meetings_dir
    meetings_dir.mkdir(parents=True, exist_ok=True)

    partial = Meeting(
        id=meeting_id,
        path=meetings_dir / f"{stem}.md",
        title=title,
        type=normalized_type,
        tags=tuple(merged_tags),
        created=timestamp,
        updated=timestamp,
    )
    content = render_frontmatter(partial)

    suffix = 1
    while True:
        filename = f"{stem}.md" if suffix == 1 else f"{stem}-{suffix}.md"
        candidate = meetings_dir / filename
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            suffix += 1
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return replace(partial, path=candidate)


def scan_meetings(workspace: Workspace) -> tuple[list[Meeting], list[ScanWarning]]:
    meetings: list[Meeting] = []
    warnings: list[ScanWarning] = []

    meetings_dir = workspace.meetings_dir
    if not meetings_dir.is_dir():
        return meetings, warnings

    for path in sorted(meetings_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")

        if not text.startswith("---\n"):
            warnings.append(
                ScanWarning(
                    path=path,
                    reason="no_frontmatter",
                    message=f"{path.name}: does not start with a frontmatter block",
                )
            )
            continue

        terminator = text.find("\n---", 3)
        if terminator == -1:
            warnings.append(
                ScanWarning(
                    path=path,
                    reason="unterminated_frontmatter",
                    message=f"{path.name}: frontmatter block is never terminated",
                )
            )
            continue

        block = text[4 : terminator + 1]
        try:
            data = read_frontmatter(block)
        except FrontmatterError as exc:
            warnings.append(
                ScanWarning(path=path, reason=exc.reason, message=f"{path.name}: {exc.message}")
            )
            continue

        type_value = str(data["type"])
        tag_values = [str(t) for t in data["tags"]]

        if type_value and not _TOKEN_PATTERN.match(type_value):
            warnings.append(
                ScanWarning(
                    path=path,
                    reason="invalid_value",
                    message=f"{path.name}: invalid type {type_value!r}",
                )
            )
            continue
        if any(not _TOKEN_PATTERN.match(tag) for tag in tag_values):
            warnings.append(
                ScanWarning(
                    path=path,
                    reason="invalid_value",
                    message=f"{path.name}: invalid tag in {tag_values!r}",
                )
            )
            continue

        meetings.append(
            Meeting(
                id=str(data["id"]),
                path=path,
                title=str(data["title"]),
                type=type_value,
                tags=tuple(tag_values),
                created=str(data["created"]),
                updated=str(data["updated"]),
            )
        )

    meetings.sort(key=lambda m: str(m.path))
    meetings.sort(key=lambda m: m.created, reverse=True)
    return meetings, warnings


def filter_meetings(meetings: Iterable[Meeting], f: MeetingFilter) -> list[Meeting]:
    results: list[Meeting] = []
    for meeting in meetings:
        if f.type is not None and meeting.type.lower() != f.type.lower():
            continue
        if f.tags:
            meeting_tags = {tag.lower() for tag in meeting.tags}
            if not all(tag.lower() in meeting_tags for tag in f.tags):
                continue
        if f.since is not None:
            created_date = date.fromisoformat(meeting.created[:10])
            if created_date < f.since:
                continue
        results.append(meeting)
    return results


def match_meeting(meeting: Meeting, query: str) -> bool:
    haystack = " ".join([meeting.title, meeting.type, *meeting.tags]).lower()
    return query.lower() in haystack
