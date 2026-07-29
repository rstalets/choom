from __future__ import annotations

import json
import sys
from collections.abc import Iterable

from endpaper.core.models import Meeting, Workspace


def relative_path(workspace: Workspace, meeting: Meeting) -> str:
    return meeting.path.relative_to(workspace.root).as_posix()


def print_meeting_line(workspace: Workspace, meeting: Meeting) -> None:
    print(
        "\t".join(
            [
                meeting.created[:10],
                meeting.type,
                meeting.title,
                ",".join(meeting.tags),
            ]
        )
    )


def print_meetings_table(workspace: Workspace, meetings: Iterable[Meeting]) -> None:
    for meeting in meetings:
        print_meeting_line(workspace, meeting)


def print_meetings_json(workspace: Workspace, meetings: Iterable[Meeting]) -> None:
    records = [
        {
            "id": meeting.id,
            "path": relative_path(workspace, meeting),
            "title": meeting.title,
            "type": meeting.type,
            "tags": list(meeting.tags),
            "created": meeting.created,
            "updated": meeting.updated,
        }
        for meeting in meetings
    ]
    print(json.dumps(records, ensure_ascii=False))


def print_error(message: str) -> None:
    print(f"endpaper: {message}", file=sys.stderr)
