from __future__ import annotations

import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from endpaper.core.errors import UsageError
from endpaper.core.frontmatter import FrontmatterError, read_frontmatter, render_frontmatter
from endpaper.core.models import Collection, Document, DocumentFilter, ScanWarning, Workspace
from endpaper.core.text import new_document_id, parse_tags, slugify

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def _validate_token(value: str, flag: str) -> str:
    if not _TOKEN_PATTERN.match(value):
        raise UsageError(f"--{flag} may not contain '/', '\\', '.', or start with '-'")
    return value.lower()


def create_document(
    workspace: Workspace,
    collection: Collection,
    description: str,
    *,
    type: str = "",
    tags: Sequence[str] = (),
    now: datetime | None = None,
) -> Document:
    when = now or datetime.now()
    title, inline_tags = parse_tags(description)
    if not title:
        raise UsageError("description must not be empty after removing #tag tokens")

    normalized_type = _validate_token(type, "type") if type else ""
    if normalized_type in collection.reserved_types:
        raise UsageError(
            f"type '{normalized_type}' is reserved; use 'endpaper note today' for the daily note"
        )

    merged_tags: list[str] = []
    for tag in (*tags, *inline_tags):
        normalized = _validate_token(tag, "tag")
        if normalized not in merged_tags:
            merged_tags.append(normalized)

    document_id = new_document_id(when.date(), collection.id_prefix)
    timestamp = when.replace(microsecond=0).isoformat()
    slug = slugify(title)
    date_str = when.strftime("%Y-%m-%d")
    stem = "-".join([date_str, *([normalized_type] if normalized_type else []), slug])

    create_dir = workspace.root / collection.create_dir
    create_dir.mkdir(parents=True, exist_ok=True)

    partial = Document(
        id=document_id,
        path=create_dir / f"{stem}.md",
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
        candidate = create_dir / filename
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            suffix += 1
            continue
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return replace(partial, path=candidate)


def _parse_document(text: str, path: Path) -> tuple[Document | None, ScanWarning | None]:
    """Parse one file's already-read text. Returns (document, None) on success or
    (None, warning) on any structural problem -- never raises."""
    if not text.startswith("---\n"):
        return None, ScanWarning(
            path=path,
            reason="no_frontmatter",
            message=f"{path.name}: does not start with a frontmatter block",
        )

    terminator = text.find("\n---", 3)
    if terminator == -1:
        return None, ScanWarning(
            path=path,
            reason="unterminated_frontmatter",
            message=f"{path.name}: frontmatter block is never terminated",
        )

    block = text[4 : terminator + 1]
    try:
        data = read_frontmatter(block)
    except FrontmatterError as exc:
        return None, ScanWarning(
            path=path, reason=exc.reason, message=f"{path.name}: {exc.message}"
        )

    type_value = str(data["type"])
    tag_values = [str(t) for t in data["tags"]]

    if type_value and not _TOKEN_PATTERN.match(type_value):
        return None, ScanWarning(
            path=path, reason="invalid_value", message=f"{path.name}: invalid type {type_value!r}"
        )
    if any(not _TOKEN_PATTERN.match(tag) for tag in tag_values):
        return None, ScanWarning(
            path=path,
            reason="invalid_value",
            message=f"{path.name}: invalid tag in {tag_values!r}",
        )

    document = Document(
        id=str(data["id"]),
        path=path,
        title=str(data["title"]),
        type=type_value,
        tags=tuple(tag_values),
        created=str(data["created"]),
        updated=str(data["updated"]),
    )
    return document, None


def _read_document(path: Path) -> Document | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    document, _ = _parse_document(text, path)
    return document


def scan_documents(
    workspace: Workspace,
    collection: Collection,
) -> tuple[list[Document], list[ScanWarning]]:
    documents: list[Document] = []
    warnings: list[ScanWarning] = []

    for scan_dir in collection.scan_dirs:
        directory = workspace.root / scan_dir
        if not directory.is_dir():
            continue

        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            document, warning = _parse_document(text, path)
            if document is not None:
                documents.append(document)
            else:
                assert warning is not None
                warnings.append(warning)

    documents.sort(key=lambda d: str(d.path))
    documents.sort(key=lambda d: d.created, reverse=True)
    return documents, warnings


def filter_documents(documents: Iterable[Document], f: DocumentFilter) -> list[Document]:
    results: list[Document] = []
    for document in documents:
        if f.type is not None and document.type.lower() != f.type.lower():
            continue
        if f.tags:
            document_tags = {tag.lower() for tag in document.tags}
            if not all(tag.lower() in document_tags for tag in f.tags):
                continue
        if f.since is not None:
            created_date = date.fromisoformat(document.created[:10])
            if created_date < f.since:
                continue
        results.append(document)
    return results


def match_document(document: Document, query: str) -> bool:
    haystack = " ".join([document.title, document.type, *document.tags]).lower()
    return query.lower() in haystack
