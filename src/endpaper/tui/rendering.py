from __future__ import annotations

from endpaper.core.models import Meeting


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def render_preview_markdown(meeting: Meeting) -> str:
    """Build the markdown shown in the preview panes: a heading and metadata line,
    never the raw frontmatter block (which is not valid standalone markdown and
    collapses into a single paragraph if rendered directly)."""
    text = meeting.path.read_text(encoding="utf-8", errors="replace")
    body = _strip_frontmatter(text)

    meta_parts = [meeting.created[:10]]
    if meeting.type:
        meta_parts.append(meeting.type)
    if meeting.tags:
        meta_parts.append(", ".join(f"#{tag}" for tag in meeting.tags))
    meta = " · ".join(meta_parts)

    heading = f"# {meeting.title}" if meeting.title else "# (untitled)"
    if body:
        return f"{heading}\n\n*{meta}*\n\n{body}"
    return f"{heading}\n\n*{meta}*\n"
