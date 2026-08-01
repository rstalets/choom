from __future__ import annotations

from pathlib import Path

from endpaper.core.models import Document, Link, LinkStatus, LinkTarget

_KIND_LABEL = {"meeting": "meetings", "note": "notes", "task": "tasks"}


def render_link_row(
    link: Link, status: LinkStatus, target: LinkTarget | None, *, direction: str
) -> str:
    """One line in the preview's Links section (contracts/tui.md -> Rendering).

    A dead link shows its unresolvable id rather than being hidden -- the user
    wrote it, and it stays visible (Principle IV).
    """
    arrow = "→" if direction == "out" else "←"
    if target is None:
        unresolved = link.target_id or link.path or "?"
        return f"⚠ (unresolved) {unresolved}"
    kind = _KIND_LABEL[target.kind]
    return f"{arrow} {target.title}   {kind}"


NO_OUTBOUND_LINKS = "(this record points at nothing)"
NO_INBOUND_LINKS = "(nothing points at this record)"


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def render_preview_markdown(path: Path, document: Document | None) -> str:
    """Build the markdown shown in the preview panes: a heading and metadata line,
    never the raw frontmatter block (which is not valid standalone markdown and
    collapses into a single paragraph if rendered directly).

    When `document` is None (an existing file whose frontmatter does not parse),
    falls back to a filename heading with no metadata line -- nothing is invented
    for fields that could not be read."""
    text = path.read_text(encoding="utf-8", errors="replace")
    body = _strip_frontmatter(text)

    if document is None:
        heading = f"# {path.name}"
        return f"{heading}\n\n{body}" if body else f"{heading}\n"

    meta_parts = [document.created[:10]]
    if document.type:
        meta_parts.append(document.type)
    if document.tags:
        meta_parts.append(", ".join(f"#{tag}" for tag in document.tags))
    meta = " · ".join(meta_parts)

    heading = f"# {document.title}" if document.title else "# (untitled)"
    if body:
        return f"{heading}\n\n*{meta}*\n\n{body}"
    return f"{heading}\n\n*{meta}*\n"
