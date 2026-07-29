from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import date

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TAG_TOKEN = re.compile(r"#([A-Za-z0-9][A-Za-z0-9_-]*)")
_WHITESPACE = re.compile(r"\s+")


def slugify(text: str, *, max_length: int = 40) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    casefolded = without_marks.casefold()
    collapsed = _NON_ALNUM.sub("-", casefolded)
    stripped = collapsed.strip("-")
    truncated = stripped[:max_length].rstrip("-")
    return truncated or "untitled"


def parse_tags(description: str) -> tuple[str, tuple[str, ...]]:
    tags: list[str] = []
    for match in _TAG_TOKEN.finditer(description):
        tag = match.group(1).lower()
        if tag not in tags:
            tags.append(tag)

    title = _TAG_TOKEN.sub(" ", description)
    title = _WHITESPACE.sub(" ", title).strip()
    return title, tuple(tags)


def new_meeting_id(when: date) -> str:
    return f"m_{when:%Y%m%d}_{secrets.token_hex(4)}"
