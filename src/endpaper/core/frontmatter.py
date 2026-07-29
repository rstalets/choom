from __future__ import annotations

import json

import yaml

from endpaper.core.models import Meeting, ScanWarningReason

REQUIRED_KEYS = frozenset({"id", "type", "title", "tags", "created", "updated"})

_KEY_ORDER = ("id", "type", "title", "tags", "created", "updated")


class FrontmatterError(Exception):
    """Internal. Raised on a structural frontmatter problem; never escapes scan_meetings."""

    def __init__(self, reason: ScanWarningReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _construct_scalar_as_str(loader: yaml.SafeLoader, node: yaml.Node) -> str:
    return str(loader.construct_scalar(node))  # type: ignore[arg-type]


class _TolerantLoader(yaml.SafeLoader):
    """Leaves YAML 1.1's bool/timestamp/float/int/null coercions as their original scalar text."""


for _tag in (
    "tag:yaml.org,2002:bool",
    "tag:yaml.org,2002:timestamp",
    "tag:yaml.org,2002:float",
    "tag:yaml.org,2002:int",
    "tag:yaml.org,2002:null",
):
    _TolerantLoader.add_constructor(_tag, _construct_scalar_as_str)


def read_frontmatter(text: str) -> dict[str, str | list[str]]:
    try:
        data = yaml.load(text, Loader=_TolerantLoader)
    except yaml.YAMLError as exc:
        raise FrontmatterError("malformed_yaml", f"invalid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise FrontmatterError("not_a_mapping", "frontmatter is not a mapping")

    keys = set(data)
    extra = keys - REQUIRED_KEYS
    missing = REQUIRED_KEYS - keys
    if extra:
        raise FrontmatterError("unexpected_fields", f"unexpected fields: {sorted(extra)}")
    if missing:
        raise FrontmatterError("missing_fields", f"missing fields: {sorted(missing)}")

    result: dict[str, str | list[str]] = {}
    for key, value in data.items():
        if key == "tags":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise FrontmatterError("invalid_value", "tags must be a list of strings")
            result[key] = list(value)
        else:
            if not isinstance(value, str):
                raise FrontmatterError("invalid_value", f"{key} must be a scalar string")
            result[key] = value
    return result


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_frontmatter(meeting: Meeting) -> str:
    type_field = _quoted(meeting.type) if meeting.type else '""'
    tags_field = "[" + ", ".join(_quoted(tag) for tag in meeting.tags) + "]"
    lines = [
        "---",
        f"id: {meeting.id}",
        f"type: {type_field}",
        f"title: {_quoted(meeting.title)}",
        f"tags: {tags_field}",
        f"created: {meeting.created}",
        f"updated: {meeting.updated}",
        "---",
        "",
    ]
    return "\n".join(lines) + "\n"
